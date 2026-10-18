"""M01 Parameter dictionary and provenance registry (architecture §6 M01, AD-14).

The single source of truth for every channel, scaling, rate, bus address, limit, code table and evidence tag.
YAML sources per subsystem (``configs/<platform>/dictionary/``) compile to a canonical, versioned,
blake2b-hashed ``dictionary.<ver>.json``; generators produce the TMATS stub, the SYNTHETIC Phalanx ICD, the
parameter table and the assumption rows. See ``README.md`` in this package.

Public API::

    from phalanx.dictionary import load_dictionary
    d = load_dictionary()            # current tejas sources (or "0.1.3", a .json path, a config dir)
    d.dict_version, d.dict_hash
    d.channel("ENG.N1.V"); d.param("ENG.N1"); d.by_lru("FADEC"); d.by_rate_group("AV25", stage="bus")
    d.by_bus_address("AV-MUX-2", rt=5, sa=1); d.units_map(); d.param_set("channel_reference")
    d.eu_to_si("ENG.N1.V", pct_n1)   # -> rad/s;  d.si_to_eu("AD.HP", metres) -> ft
"""

from .compiler import (
    CompiledDictionary,
    CompileError,
    SourceBundle,
    compile_bundle,
    compile_dictionary,
    load_bundle,
    read_compiled,
    write_compiled,
)
from .eu import EUConversion, EUConversionError
from .generators import build, register_generator, resolve_generator, run_generators
from .model import DEFAULT_CONFIG_ROOT, Dictionary, DictionaryVersionError, config_dir_for, load_dictionary

__all__ = [
    "DEFAULT_CONFIG_ROOT",
    "CompileError",
    "CompiledDictionary",
    "Dictionary",
    "DictionaryVersionError",
    "EUConversion",
    "EUConversionError",
    "SourceBundle",
    "build",
    "compile_bundle",
    "compile_dictionary",
    "config_dir_for",
    "load_bundle",
    "load_dictionary",
    "read_compiled",
    "register_generator",
    "resolve_generator",
    "run_generators",
    "write_compiled",
]
