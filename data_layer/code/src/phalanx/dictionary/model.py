"""Read-only view of a compiled dictionary and ``load_dictionary`` (the M01 public API for consumers).

Consumers (W0.4 contract, W1 modules) never read YAML sources; they call :func:`load_dictionary` and use the
lookups on :class:`Dictionary`. Every object handed out is deeply immutable (mappings are
``MappingProxyType``, sequences are tuples), so no consumer can change the dictionary behind another
consumer's back.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .codes import code_from_eu, code_to_eu, eu_from_word, word_from_eu
from .compiler import CompiledDictionary, compile_dictionary, read_compiled
from .eu import EUConversion, EUConversionError, build_conversions
from .yamlio import blake2b_hex, load_yaml

__all__ = [
    "DEFAULT_CONFIG_ROOT",
    "Dictionary",
    "DictionaryVersionError",
    "config_dir_for",
    "load_dictionary",
]

#: <repo>/configs, located from this file (src/phalanx/dictionary/model.py)
DEFAULT_CONFIG_ROOT = Path(__file__).resolve().parents[3] / "configs"
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class DictionaryVersionError(LookupError):
    """The requested dictionary version is unknown, or the sources do not hash to the released hash."""


def _freeze(obj: Any) -> Any:
    if isinstance(obj, dict):
        return MappingProxyType({k: _freeze(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return tuple(_freeze(v) for v in obj)
    return obj


class Dictionary:
    """A compiled, hashed dictionary with lookups by parameter, channel, LRU, bus address and rate group."""

    def __init__(self, compiled: CompiledDictionary):
        self._compiled = compiled
        c = compiled.content
        self._content = _freeze(c)
        self._channels: Mapping[str, Mapping[str, Any]] = self._content["channels"]
        self._params: Mapping[str, Mapping[str, Any]] = self._content["parameters"]
        by_lru: dict[str, list[str]] = {}
        by_group: dict[str, list[str]] = {}
        by_addr: dict[tuple, list[str]] = {}
        by_measurand: dict[str, list[str]] = {}
        for cid, ch in c["channels"].items():
            for lru in {ch["source_lru"], ch["acq_lru"], ch["transport"].get("rt_lru")} - {None}:
                by_lru.setdefault(lru, []).append(cid)
            groups = {g for g in ch["rates"].values() if g} | {s["group"] for s in ch["sinks"] if s["group"]}
            for g in groups:
                by_group.setdefault(g, []).append(cid)
            key = self._address_key(ch["transport"])
            if key is not None:
                by_addr.setdefault(key, []).append(cid)
            by_measurand.setdefault(ch["measurand_id"], []).append(cid)
        self._by_lru = {k: tuple(sorted(v)) for k, v in by_lru.items()}
        self._by_group = {k: tuple(sorted(v)) for k, v in by_group.items()}
        self._by_addr = {k: tuple(sorted(v)) for k, v in by_addr.items()}
        self._by_measurand = {k: tuple(sorted(v)) for k, v in by_measurand.items()}
        # EU <-> SI maps, one per channel (immutable; built once from the compiled content)
        self._eu = MappingProxyType(build_conversions(c))

    # ---- identity ------------------------------------------------------------------------------------------
    @property
    def dict_version(self) -> str:
        return self._compiled.dict_version

    @property
    def dict_hash(self) -> str:
        return self._compiled.dict_hash

    @property
    def platform(self) -> str:
        return self._compiled.platform

    @property
    def synthetic_label(self) -> str:
        return self._content["synthetic_label"]

    @property
    def compiled(self) -> CompiledDictionary:
        """The underlying compiled dictionary (plain JSON-model content, canonical bytes, hash)."""
        return self._compiled

    @property
    def content(self) -> Mapping[str, Any]:
        """The full compiled content (read-only)."""
        return self._content

    def to_bytes(self) -> bytes:
        """Canonical file bytes (content + dict_hash)."""
        return self._compiled.to_bytes()

    def __repr__(self) -> str:
        n = len(self._channels)
        return f"Dictionary({self.platform} {self.dict_version} {self.dict_hash[:12]}..., {n} channels)"

    # ---- parameters and channels ---------------------------------------------------------------------------
    def param_ids(self) -> tuple[str, ...]:
        return tuple(self._params)

    def param(self, param_id: str) -> Mapping[str, Any]:
        """Logical parameter (inventory row): evidence, inventory text, channel ids."""
        try:
            return self._params[param_id]
        except KeyError:
            raise KeyError(f"unknown param_id {param_id!r}") from None

    def channel_ids(self) -> tuple[str, ...]:
        return tuple(self._channels)

    def channel(self, channel_id: str) -> Mapping[str, Any]:
        """One physical channel (lane, unit or component of a parameter)."""
        try:
            return self._channels[channel_id]
        except KeyError:
            raise KeyError(f"unknown channel_id {channel_id!r}") from None

    def channels(self) -> Iterator[Mapping[str, Any]]:
        """All channels, sorted by channel id."""
        return iter(self._channels.values())

    def channels_for_param(self, param_id: str) -> tuple[Mapping[str, Any], ...]:
        return tuple(self._channels[c] for c in self.param(param_id)["channel_ids"])

    def channels_for_measurand(self, measurand_id: str) -> tuple[Mapping[str, Any], ...]:
        """Channels (lanes) of one measurand (the contract's ``param_id``; see README)."""
        return tuple(self._channels[c] for c in self._by_measurand.get(measurand_id, ()))

    def measurand_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_measurand))

    # ---- lookups -------------------------------------------------------------------------------------------
    def by_lru(self, lru: str) -> tuple[Mapping[str, Any], ...]:
        """Channels produced, digitised or transmitted by ``lru``."""
        if lru not in self._content["lrus"]:
            raise KeyError(f"unknown LRU {lru!r}")
        return tuple(self._channels[c] for c in self._by_lru.get(lru, ()))

    def by_rate_group(self, group: str, *, stage: str | None = None) -> tuple[Mapping[str, Any], ...]:
        """Channels using ``group``; ``stage`` in {acquisition, bus, producer, record} narrows the match."""
        if group not in self._content["rate_groups"]:
            raise KeyError(f"unknown rate group {group!r}")
        out = []
        for cid in self._by_group.get(group, ()):
            ch = self._channels[cid]
            if stage is None:
                out.append(ch)
            elif stage == "record":
                if any(s["group"] == group for s in ch["sinks"]):
                    out.append(ch)
            elif ch["rates"].get(stage) == group:
                out.append(ch)
        return tuple(out)

    @staticmethod
    def _address_key(t: Mapping[str, Any]) -> tuple | None:
        if t["type"] == "mil1553" and "sa" in t:
            return ("mil1553", t["bus"], t["rt"], t["tr"], t["sa"])
        if t["type"] in ("mil1553_status", "mil1553_modecode"):
            return (t["type"], t["bus"], t["rt"])
        if t["type"] == "arinc429" and "label" in t:
            return ("arinc429", t["link"], t["label"], t["sdi"])
        if t["type"] == "fti_pcm" and "word" in t:
            return ("fti_pcm", t["stream"], t["word"])
        return None

    def by_bus_address(
        self,
        bus_or_link: str,
        *,
        rt: int | None = None,
        tr: str = "T",
        sa: int | None = None,
        word: int | None = None,
        label: int | None = None,
        sdi: int = 0,
    ) -> tuple[Mapping[str, Any], ...]:
        """Channels at a bus address.

        - 1553 data: ``by_bus_address("AV-MUX-2", rt=5, sa=1)`` (whole message) or with ``word=`` (the item
          covering that data word);
        - ARINC-429: ``by_bus_address("RADALT-OAC", label=0o100)``;
        - FTI PCM: ``by_bus_address("FTI-PCM", word=3)``.
        """
        if label is not None:
            cids = self._by_addr.get(("arinc429", bus_or_link, label, sdi), ())
        elif rt is not None and sa is not None:
            cids = self._by_addr.get(("mil1553", bus_or_link, rt, tr, sa), ())
            if word is not None:
                cids = tuple(
                    c
                    for c in cids
                    if self._channels[c]["transport"]["word"]
                    <= word
                    < self._channels[c]["transport"]["word"] + self._channels[c]["transport"]["words"]
                )
        elif word is not None:
            cids = self._by_addr.get(("fti_pcm", bus_or_link, word), ())
        else:
            raise ValueError("give rt and sa (1553), label (ARINC-429) or word (FTI PCM)")
        return tuple(self._channels[c] for c in cids)

    def rt_status_channel(self, bus: str, rt: int) -> Mapping[str, Any] | None:
        cids = self._by_addr.get(("mil1553_status", bus, rt), ())
        return self._channels[cids[0]] if cids else None

    # ---- tables --------------------------------------------------------------------------------------------
    def rate_hz(self, group: str) -> float | None:
        """Nominal rate of a periodic rate group (None for event/sortie/per-LRU groups)."""
        return self._content["rate_groups"][group].get("rate_hz")

    def acquisition_rate_hz(self, channel_id: str) -> float | None:
        """Nominal acquisition rate of a channel (resolves per-LRU frame groups)."""
        ch = self.channel(channel_id)
        g = self._content["rate_groups"][ch["rates"]["acquisition"]]
        if g["kind"] == "lru_frame":
            return self._content["lrus"][ch["acq_lru"]].get("frame_hz")
        return g.get("rate_hz")

    def lru(self, lru: str) -> Mapping[str, Any]:
        return self._content["lrus"][lru]

    def code_table(self, name: str) -> Mapping[str, Any]:
        return self._content["code_tables"][name]

    def rule(self, rule_id: str) -> Mapping[str, Any]:
        return self._content["rules"][rule_id]

    def constants(self, name: str) -> Mapping[str, Any]:
        """A scalar parameter set as written (``constants`` table): {name: {value, units, evidence, ...}}."""
        return self._content["constants"][name]

    def param_set(self, name: str) -> Any:
        """The ``constants`` set ``name`` as a core-kernel ``ParamSet`` (values converted to coherent SI,
        evidence tags parsed by ``EvidenceTag``, PROXY flags carried), ready for a module's ``init``
        (architecture
        §5.5)."""
        from phalanx.core.module import Param, ParamSet
        from phalanx.core.units import ureg

        params = {}
        for key, c in self._content["constants"][name].items():
            q = ureg().Quantity(c["value"], c["units"]).to_base_units()
            value = q.magnitude if isinstance(q.magnitude, int) else float(q.magnitude)
            params[key] = Param(
                value=value,
                unit=str(q.units),
                tag=c["evidence"]["tag"],
                source=c["evidence"]["source"],
                proxy=bool(c.get("proxy", False)),
                note=f"{c['description']} [{c['value']} {c['units']}; dictionary {self.dict_version}]",
            )
        return ParamSet(f"{self.platform}.{name}", params)

    def field_evidence(self, channel_id: str, field: str) -> Mapping[str, Any]:
        """Evidence behind one channel field: {ref, tag (EvidenceTag-parsable), source, proxy}.

        ``field`` is a provenance key (``range``, ``recorder_lsb``, ``rates.bus``, ...). A ref ``inv``
        resolves to the parameter's ``core_tag`` and inventory source; a rule ref to the rule's tag and
        source.
        """
        ch = self.channel(channel_id)
        ref = ch["prov"].get(field)
        if ref is None:
            raise KeyError(f"{channel_id}: no provenance for field {field!r}")
        if ref == "inv":
            ev = self.param(ch["param_id"])["evidence"]
            return MappingProxyType(
                {"ref": ref, "tag": ev.get("core_tag", ev["tag"]), "source": ev["source"], "proxy": False}
            )
        rule = self.rule(ref)
        return MappingProxyType(
            {
                "ref": ref,
                "tag": rule["tag"],
                "source": rule["source"],
                "proxy": bool(rule.get("proxy", False)),
            }
        )

    def units_map(self) -> dict[str, str]:
        """{measurand_id: engineering units} for the contract fast path (W0.4)."""
        return {m: self._channels[cids[0]]["units"] for m, cids in sorted(self._by_measurand.items())}

    def contract_location(self, channel_id: str) -> Mapping[str, Any]:
        """The contract (W0.4 ``param.samples``) identity of a channel.

        ``param_id`` = measurand_id; ``source_lru`` = the acquiring LRU; ``lane`` = lane or None; ``bus`` =
        1553 bus, ARINC-429 link or FTI stream name (None off-bus); ``label_sdi`` = 'Looo/SDIn';
        ``rt_sa_word`` = 'RTnn/SAnn/Wnn' where Wnn is the contract's **0-based data-word index** (the
        dictionary and TMATS number data words from 1, so Wnn = word - 1 of the first word). RT status words
        map to SA00/W00 and the mode-code-19 BIT word to SA31/W00 (mode-code subaddresses 0 and 31; data
        messages use SA 1-30).
        """
        ch = self.channel(channel_id)
        t = ch["transport"]
        bus = rt_sa_word = label_sdi = None
        if t["type"] == "mil1553":
            bus, rt_sa_word = t["bus"], f"RT{t['rt']:02d}/SA{t['sa']:02d}/W{t['word'] - 1:02d}"
        elif t["type"] == "mil1553_status":
            bus, rt_sa_word = t["bus"], f"RT{t['rt']:02d}/SA00/W00"
        elif t["type"] == "mil1553_modecode":
            bus, rt_sa_word = t["bus"], f"RT{t['rt']:02d}/SA31/W00"
        elif t["type"] == "arinc429":
            bus, label_sdi = t["link"], f"L{t['label']:03o}/SDI{t['sdi']}"
        elif t["type"] == "fti_pcm":
            bus = t["stream"]
        return MappingProxyType(
            {
                "param_id": ch["measurand_id"],
                "source_lru": ch["acq_lru"],
                "lane": ch["lane"] or None,
                "bus": bus,
                "rt_sa_word": rt_sa_word,
                "label_sdi": label_sdi,
                "units": ch["units"],
            }
        )

    def proxy_items(self) -> tuple[str, ...]:
        return self._content["proxy_items"]

    # ---- unified BIT/fault codes and code words (0.1.2) ----------------------------------------------------
    def bit_codes(self) -> tuple[str, ...]:
        """Every code of the unified ``bit_codes`` table in index order (``bit_code(c)["index"]`` = its
        position)."""
        codes = self._content["code_tables"]["bit_codes"]["codes"]
        return tuple(sorted(codes, key=lambda c: codes[c]["index"]))

    def bit_code(self, code: str) -> Mapping[str, Any]:
        """One row of ``bit_codes`` (desc, sev, list, mech, lru, lane, src, legend, voice, monitor) plus its
        ``group``."""
        table = self._content["code_tables"]["bit_codes"]
        row = table["codes"][code]
        return MappingProxyType({**row, "group": table["groups"][code.split("-")[0]]})

    def translate_bit_code(self, code: str, legacy: str) -> str:
        """The unified code of ``code`` from a module's earlier list (``legacy`` = e.g. ``"M08"``)."""
        return self._content["code_tables"]["bit_codes"]["legacy"][legacy]["codes"][code]

    def code_word_eu(self, channel_id: str, code: str | None) -> int:
        """EU value of an SSS-NNN code on a ``code_word`` channel (``k * 1000 + NNN``; None -> 0)."""
        if code is None:
            return 0
        layout = self._content["code_tables"]["bit_code_format"]["word_layout"]
        return code_to_eu(code, self._code_prefixes(channel_id), int(layout["eu_prefix_scale"]))

    def code_word_code(self, channel_id: str, value: int) -> str | None:
        """SSS-NNN code of an EU value on a ``code_word`` channel (None for 0 = no active code)."""
        layout = self._content["code_tables"]["bit_code_format"]["word_layout"]
        return code_from_eu(value, self._code_prefixes(channel_id), int(layout["eu_prefix_scale"]))

    def code_word_bits(self, value: int) -> int:
        """16-bit bus word of a code-word EU value (``bit_code_format.word_layout``, rule R-CODE-WORD)."""
        return word_from_eu(value, self._content["code_tables"]["bit_code_format"]["word_layout"])

    def code_word_value(self, word: int) -> int:
        """EU value of a 16-bit code word (inverse of :meth:`code_word_bits`)."""
        return eu_from_word(word, self._content["code_tables"]["bit_code_format"]["word_layout"])

    def _code_prefixes(self, channel_id: str) -> tuple[str, ...]:
        enc = self.channel(channel_id)["encoding"]
        if enc.get("type") != "code_word":
            raise ValueError(f"{channel_id} is not a code_word channel")
        return tuple(enc["prefixes"])

    # ---- recorder setup (0.1.2) ----------------------------------------------------------------------------
    def recorder_setup(self) -> Mapping[str, Any]:
        """The recorder setup (``buses.recorder``): id, recording events, event attributes, time index."""
        return self._content["buses"]["recorder"]

    def recording_events(self) -> tuple[Mapping[str, Any], ...]:
        """Recording-event types in TMATS order (event number = position + 1)."""
        return tuple(self._content["buses"]["recorder"]["events"])

    # ---- engineering units <-> SI --------------------------------------------------------------------------
    def eu_conversion(self, channel_id: str) -> EUConversion:
        """The channel's affine map ``si = eu * scale + offset`` (SI unit, scale, offset, reference speed).

        Raises EUConversionError for channels with no numeric SI form (text, media, % of rated speed with no
        public reference speed) and KeyError for an unknown channel.
        """
        if channel_id not in self._eu:
            raise KeyError(f"unknown channel {channel_id!r}")
        conv = self._eu[channel_id]
        if isinstance(conv, EUConversionError):
            raise conv
        return conv

    def eu_to_si(self, channel_id: str, values: Any) -> Any:
        """Engineering-unit values of ``channel_id`` -> coherent SI (float64 scalars or arrays, shape kept).

        Units follow the channel: ft -> m, knot -> m/s, psi/bar/mbar -> Pa, degC/degF -> K, lb/hr -> kg/s,
        deg -> rad, % -> fraction, %N1/%N2 -> rad/s via the ``channel_reference`` speeds, codes unchanged.
        """
        return self.eu_conversion(channel_id).to_si(values)

    def si_to_eu(self, channel_id: str, values: Any) -> Any:
        """Coherent SI values -> the engineering units of ``channel_id`` (inverse of :meth:`eu_to_si`)."""
        return self.eu_conversion(channel_id).to_eu(values)


def config_dir_for(platform: str, config_root: str | Path | None = None) -> Path:
    """``<config_root>/<platform>/dictionary``."""
    return Path(config_root or DEFAULT_CONFIG_ROOT) / platform / "dictionary"


def _sources_digest(config_dir: Path) -> str:
    """Digest of every file the compiler reads (cache key: recompiles whenever any source changes)."""
    files = [config_dir / "dictionary.yaml"]
    manifest = load_yaml(files[0])
    files += [config_dir / rel for _, rel in sorted(manifest["tables"].items())]
    files += sorted((config_dir / manifest.get("sources_dir", "sources")).glob("*.yaml"))
    h = b"".join(p.name.encode() + b"\0" + p.read_bytes() + b"\0" for p in files)
    return blake2b_hex(h)


@lru_cache(maxsize=8)
def _compile_cached(config_dir: str, digest: str) -> CompiledDictionary:  # digest: cache key only
    return compile_dictionary(config_dir)


def load_dictionary(
    version_or_path: str | Path | None = None,
    *,
    platform: str = "tejas",
    config_root: str | Path | None = None,
) -> Dictionary:
    """Load a dictionary.

    - ``None``: compile the current sources of ``platform``;
    - a semantic version (``"0.1.0"``): compile the current sources, require that version, and check the
      compiled hash against ``releases.yaml`` (DictionaryVersionError on any mismatch);
    - a path to a compiled ``dictionary.<ver>.json``: read it and verify its hash;
    - a path to a platform dictionary directory: compile it.
    """
    if version_or_path is not None and (
        isinstance(version_or_path, Path) or not _SEMVER.match(str(version_or_path))
    ):
        p = Path(version_or_path)
        if p.is_file():
            return Dictionary(read_compiled(p))
        if p.is_dir():
            return Dictionary(_compile_cached(str(p.resolve()), _sources_digest(p)))
        raise FileNotFoundError(f"no dictionary at {p}")
    cdir = config_dir_for(platform, config_root)
    compiled = _compile_cached(str(cdir.resolve()), _sources_digest(cdir))
    if version_or_path is None:
        return Dictionary(compiled)
    version = str(version_or_path)
    if version != compiled.dict_version:
        raise DictionaryVersionError(
            f"{platform} sources are dictionary {compiled.dict_version}, not {version}; "
            "older versions are loaded "
            "from their compiled dictionary.<ver>.json (build output or git history)"
        )
    releases = load_yaml(cdir / "releases.yaml").get("releases") or {}
    released = releases.get(version, {}).get("dict_hash")
    if released != compiled.dict_hash:
        raise DictionaryVersionError(
            f"{platform} {version}: compiled hash {compiled.dict_hash} does not match the released hash "
            f"{released}; "
            "bump dict_version and record the new hash in releases.yaml"
        )
    return Dictionary(compiled)
