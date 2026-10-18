"""Data foundation (G0 gate, as-of store, ingest, telemetry health) for the v0.9 release.

Never opens anything under _restricted_labels/ (paths are denied before any open; only MANIFEST metadata
about them is counted). Reads consumer trees: fleet/, telemetry/, telemetry_full_path/, ch10/, _runs/.
Writes video/data/data_foundation_asof_20260622.json and video/screens/assets/data-data.js.
Run: <venv>/bin/python video/data/scripts/data_foundation.py
"""
import os, sys, json, hashlib, base64, collections, time, random
import numpy as np, pandas as pd
import pyarrow as pa, pyarrow.parquet as pq, pyarrow.dataset as pds, pyarrow.compute as pc

ROOT = "/Users/abishaikc/Downloads/phalanx_data_layer_preview/"
DATA = ROOT + "data/v0.9/"
ARROW = ROOT + "code/docs/contract/contract/v0/arrow/"
SPEC = ROOT + "code/src/phalanx/dictionary/contract/spec/v0/contract.yaml"
V = "/Users/abishaikc/Phalanx-Solution/video/data/"
IST = "Asia/Kolkata"
T = pd.Timestamp("2026-06-22 06:00", tz=IST); T_NS = T.value
ALLOW = {"a4396f1d5482ce7816354ed7c9b040179d3c1467a7ca6e75b21fd71e1a904566"}
OUT = {}
t_start = time.time()

# ------------------------------------------------------------------ deny-list (rule 3) — enforced before any open
class DeniedPath(PermissionError): pass
def guarded(path):
    rel = os.path.relpath(path, DATA)
    if rel.split(os.sep)[0] == "_restricted_labels" or "labels.truth" in rel:
        raise DeniedPath(rel)
    return path
deny_ok = False
try:
    guarded(DATA + "_restricted_labels/fleet/labels.truth/x.parquet")
except DeniedPath:
    deny_ok = True

# ------------------------------------------------------------------ release identity
mpath = guarded(DATA + "MANIFEST.json")
mbytes = open(mpath, "rb").read()
M = json.loads(mbytes)
files = M["files"]
restricted_entries = [k for k in files if k.startswith("_restricted_labels/")]
OUT["release"] = dict(
    release_id=hashlib.sha256(mbytes).hexdigest(), manifest_bytes=len(mbytes), manifest_entries=len(files),
    contract=M["contract_version"], contract_hash=M["contract_hash"], schema_hash=M["schema_hash"],
    code_commit=M["code_commit"], seeds=M["seeds"],
    leak_audit={k: len(v) for k, v in M["validation"]["leak_audit_findings"].items()},
    determinism=M["runs"]["determinism"][0],
    restricted_manifest_entries=len(restricted_entries),
    restricted_rows_declared={k: v for k, v in M["validation"]["trees"].items() if k.startswith("_restricted")},
    deny_list_test=deny_ok)

# schema hash recomputed from the pinned Arrow schemas (contract docs), same algorithm as the data layer
def rt(t):
    ch = lambda f: f"{f.name}: {rt(f.type)}" + ("" if f.nullable else " not null")
    if pa.types.is_list(t): return f"list<{ch(t.value_field)}>"
    if pa.types.is_struct(t): return "struct<" + ", ".join(ch(t.field(i)) for i in range(t.num_fields)) + ">"
    return str(t)
def rf(f):
    md = sorted((k.decode(), v.decode()) for k, v in (f.metadata or {}).items()); t = f.type; c = []
    if pa.types.is_list(t): c = [rf(t.value_field)]
    elif pa.types.is_struct(t): c = [rf(t.field(i)) for i in range(t.num_fields)]
    return [f.name, rt(t), f.nullable, md, c]
order = [l.strip()[len("- topics/"):-5] for l in open(SPEC).read().split("topics:\n")[-1].splitlines() if l.strip().startswith("- topics/")]
load_schema = lambda name: pa.ipc.read_schema(pa.py_buffer(base64.b64decode(open(ARROW + name + ".schema.b64").read())))
doc = []
for tp in order:
    s = load_schema(tp); md = sorted((k.decode(), v.decode()) for k, v in (s.metadata or {}).items())
    doc.append([tp, [rf(f) for f in s], md])
OUT["release"]["schema_hash_recomputed"] = hashlib.blake2b(json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(), digest_size=32).hexdigest()
PINNED = {tp: load_schema(tp + ".consumer") for tp in order if tp != "labels.truth"}

# ------------------------------------------------------------------ G0 gate over every consumer file
CONSUMER_ROOTS = ["fleet", "telemetry", "telemetry_full_path", "ch10", "_runs"]
disk = []
for r in CONSUMER_ROOTS:
    for dp, dn, fn in os.walk(DATA + r):
        for f in fn:
            disk.append(os.path.relpath(os.path.join(dp, f), DATA))
gate = collections.OrderedDict()
def topic_of(rel):
    p = rel.split("/")
    if p[0] in ("fleet", "telemetry", "telemetry_full_path"): return p[0] + "/" + p[1]
    return p[0]
for rel in sorted(disk):
    tp = topic_of(rel)
    g = gate.setdefault(tp, dict(files=0, bytes=0, sha_ok=0, sha_bad=0, not_in_manifest=0, contract_ok=0, schema_ok=0, parquet=0))
    g["files"] += 1
    path = guarded(DATA + rel)
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""): h.update(chunk)
    g["bytes"] += os.path.getsize(path)
    ent = files.get(rel)
    if ent is None: g["not_in_manifest"] += 1
    elif ent["sha256"] == h.hexdigest(): g["sha_ok"] += 1
    else: g["sha_bad"] += 1
    if rel.endswith(".parquet"):
        g["parquet"] += 1
        s = pq.read_schema(path); md = {k.decode(): v.decode() for k, v in (s.metadata or {}).items()}
        if md.get("phalanx.contract_hash") in ALLOW: g["contract_ok"] += 1
        topic = md.get("phalanx.topic")
        if topic in PINNED and s.equals(PINNED[topic], check_metadata=True): g["schema_ok"] += 1
consumer_manifest = [k for k in files if not k.startswith("_restricted_labels/")]
OUT["gate_files"] = gate
OUT["gate_summary"] = dict(discovered=len(disk), manifest_consumer_entries=len(consumer_manifest),
                           missing_on_disk=len(set(consumer_manifest) - set(disk)),
                           sha_ok=sum(g["sha_ok"] for g in gate.values()), sha_bad=sum(g["sha_bad"] for g in gate.values()),
                           parquet=sum(g["parquet"] for g in gate.values()), contract_ok=sum(g["contract_ok"] for g in gate.values()),
                           schema_ok=sum(g["schema_ok"] for g in gate.values()), bytes=sum(g["bytes"] for g in gate.values()))
print("gate files done", round(time.time() - t_start, 1), "s", flush=True)

# ------------------------------------------------------------------ row invariants per topic (fleet + telemetry events/manifest)
def read_tree(tree, topic):
    d = pds.dataset(guarded(DATA + tree + "/" + topic), format="parquet", partitioning=None)
    tb = d.to_table()
    for i, f in enumerate(tb.schema):
        if pa.types.is_list(f.type) and pa.types.is_fixed_size_binary(f.type.value_type):
            tb = tb.set_column(i, f.name, tb.column(i).cast(pa.list_(pa.binary())))
    return tb
rows = collections.OrderedDict()
FT = {}
for tree, topic in [("fleet", "maint.records"), ("fleet", "events.bit_faults"), ("fleet", "events.cautions"),
                    ("fleet", "usage.counters"), ("fleet", "orders.commands"), ("fleet", "orders.status"),
                    ("telemetry", "events.bit_faults"), ("telemetry", "events.cautions"), ("telemetry", "events.exceedances"),
                    ("telemetry", "sortie.manifest"), ("telemetry_full_path", "sortie.manifest")]:
    tb = read_tree(tree, topic)
    md = {k.decode(): v.decode() for k, v in tb.schema.metadata.items()}
    et, it = md["phalanx.event_time"], md["phalanx.ingest_time"]
    n = tb.num_rows
    ing_lt = int(pc.sum(pc.less(tb[it], tb[et])).as_py() or 0)
    flags_bad = int(pc.sum(pc.not_equal(pc.bit_wise_and(tb["quality_flags"], pa.scalar(0xFFFFF800, pa.uint32())), 0)).as_py() or 0) if "quality_flags" in tb.column_names else 0
    nan = 0
    for f in tb.schema:
        if pa.types.is_floating(f.type):
            c = tb[f.name]; nan += int(pc.sum(pc.is_nan(c)).as_py() or 0) + int(pc.sum(pc.is_inf(c)).as_py() or 0)
    dv = sorted(set(tb["dict_version"].to_pylist())); dh = sorted(set(tb["dict_hash"].to_pylist()))
    df = tb.to_pandas() if n < 50000 else None
    rid = [bytes(b).hex() for b in tb["record_id"].to_pylist()]
    scope_col = "target_tail_no" if "target_tail_no" in tb.column_names else ("tail_no" if "tail_no" in tb.column_names else None)
    scope = tb[scope_col].to_pylist() if scope_col else [None] * n
    glob_dup = n - len(set(rid))
    # scoped identity. Rows without tail_no are linked to a world where the records allow it:
    #   SHOP_FINDING  -> the world whose COMPONENT_LIFE REMOVE has the same job_no + serial_no
    #   SUPPLY_DEMAND -> the world holding a record with exactly the same t_event
    #   orders.status -> the world of the orders.commands row with that order_id (if unique)
    link = {}
    if topic == "maint.records":
        p = tb.select(["record_type", "job_no", "serial_no", "tail_no", "install_action", "t_event"]).to_pandas()
        rem = p[(p.record_type == "COMPONENT_LIFE") & (p.install_action == "REMOVE")]
        idx = rem.groupby(["job_no", "serial_no"]).tail_no.apply(lambda s: sorted(set(s))).to_dict()
        tev = p[p.tail_no.notna() & (p.record_type != "SUPPLY_DEMAND")].groupby("t_event").tail_no.apply(lambda s: sorted(set(s))).to_dict()
        for rtype, fn in (("SHOP_FINDING", lambda i: idx.get((p.job_no.iat[i], p.serial_no.iat[i]), [])),
                          ("SUPPLY_DEMAND", lambda i: tev.get(p.t_event.iat[i], []))):
            sel = np.where((p.record_type.values == rtype) & p.tail_no.isna().values)[0]
            ok = 0
            for i in sel:
                w = fn(i)
                if len(w) == 1: scope[i] = w[0]; ok += 1
                else: scope[i] = "base"
            link[rtype] = dict(rows=int(len(sel)), linked=ok, unlinked=int(len(sel) - ok))
    if topic == "orders.status":
        oc = pds.dataset(guarded(DATA + "fleet/orders.commands"), format="parquet", partitioning=None).to_table(columns=["order_id", "target_tail_no"]).to_pandas()
        om = oc.groupby("order_id").target_tail_no.apply(lambda s: sorted(set(s))).to_dict()
        oids = tb["order_id"].to_pylist(); ok = 0
        for i, o in enumerate(oids):
            w = om.get(o, [])
            if len(w) == 1: scope[i] = w[0]; ok += 1
            else: scope[i] = "base"
        link["ORDER_STATUS"] = dict(rows=n, linked=ok, unlinked=n - ok)
    keys = list(zip(scope, rid))
    scoped_dup = n - len(set(keys))
    conflicts = 0; idem = 0; conflict_rows = 0; conflict_types = collections.Counter()
    if scoped_dup:
        pdf = tb.to_pandas()
        pdf["_k"] = keys
        for k, g in pdf[pdf.duplicated("_k", keep=False)].groupby("_k"):
            sig = set(json.dumps({c: (v.tolist() if hasattr(v, "tolist") else (list(map(lambda x: bytes(x).hex() if isinstance(x, (bytes, bytearray)) else str(x), v)) if isinstance(v, (list, np.ndarray)) else (bytes(v).hex() if isinstance(v, (bytes, bytearray)) else v))) for c, v in r.items() if c not in ("_k", "t_ingest")}, default=str, sort_keys=True) for _, r in g.iterrows())
            if len(sig) > 1:
                conflicts += 1; conflict_rows += len(g)
                conflict_types[g["record_type"].iloc[0] if "record_type" in g else topic] += len(g)
            else: idem += 1
    ing = pd.to_datetime(np.asarray(tb[it].to_numpy(zero_copy_only=False)), utc=True)
    evt = pd.to_datetime(np.asarray(tb[et].to_numpy(zero_copy_only=False)), utc=True)
    vis = int((ing <= T).sum())
    late = int(((evt <= T) & (ing > T)).sum())
    key = f"{tree}/{topic}"
    rows[key] = dict(rows=n, ingest_before_event=ing_lt, reserved_flag_bits=flags_bad, nan_inf=nan, dict_version=dv, dict_hash=dh,
                     record_id_unique_global=len(set(rid)), global_duplicates=glob_dup, scoped_duplicates=scoped_dup,
                     scoped_conflicts=conflicts, scoped_conflict_rows=conflict_rows, conflict_types=dict(conflict_types), link=link,
                     scoped_idempotent=idem, visible_asof=vis, late_after_snapshot=late,
                     event_time=et, ingest_time=it)
    FT[key] = tb
print("row invariants done", round(time.time() - t_start, 1), "s", flush=True)

# ------------------------------------------------------------------ telemetry param.samples (streamed per file)
FLAG = dict(SENTINEL=0, GATED=1, HELD_STALE=2, DUPLICATE_POLL=3, SUBSTITUTED=4, VOTED_OUT=5, OUT_OF_RANGE=6, CLOCK_SUSPECT=7,
            TIME_SOURCE_INTERNAL=8, DUPLICATE_DOWNLOAD=9, DECODER_INTERPOLATED=10)
tel = {}
CACHE = V + "data_foundation_telemetry_scan.json"
if os.path.exists(CACHE) and "--full" not in sys.argv:
    tel = json.load(open(CACHE))
for tree in [x for x in ("telemetry", "telemetry_full_path") if x not in tel]:
    agg = dict(rows=0, ingest_before_event=0, reserved_flag_bits=0, nan_inf=0, flags={k: 0 for k in FLAG}, sentinel_and_oor=0,
               any_flag=0, validity=collections.Counter(), params=set(), lrus=set(), param_lru=set(), per_sortie=collections.defaultdict(lambda: dict(rows=0, params=set(), oor=0, sent=0, t0=None, t1=None)),
               rid_dups=0, dict=set())
    rid_prefix = collections.defaultdict(list)
    for dp, dn, fn in os.walk(DATA + tree + "/param.samples"):
        for f in sorted(fn):
            if not f.endswith(".parquet"): continue
            path = guarded(os.path.join(dp, f))
            tb = pq.read_table(path, columns=["record_id", "param_id", "source_lru", "sortie_id", "t_sample", "t_ingest", "value_eu", "validity", "quality_flags", "dict_version", "dict_hash"])
            n = tb.num_rows; agg["rows"] += n
            agg["ingest_before_event"] += int(pc.sum(pc.less(tb["t_ingest"], tb["t_sample"])).as_py() or 0)
            qf = tb["quality_flags"]
            agg["reserved_flag_bits"] += int(pc.sum(pc.not_equal(pc.bit_wise_and(qf, pa.scalar(0xFFFFF800, pa.uint32())), 0)).as_py() or 0)
            agg["nan_inf"] += int(pc.sum(pc.is_nan(tb["value_eu"])).as_py() or 0) + int(pc.sum(pc.is_inf(tb["value_eu"])).as_py() or 0)
            q = qf.to_numpy()
            for k, b in FLAG.items(): agg["flags"][k] += int(((q >> b) & 1).sum())
            agg["sentinel_and_oor"] += int((((q & 1) > 0) & ((q & 64) > 0)).sum())
            agg["any_flag"] += int((q != 0).sum())
            for v, c in zip(*np.unique(np.asarray(tb["validity"].to_pylist(), dtype=object).astype(str), return_counts=True)): agg["validity"][v] += int(c)
            pid = pc.unique(tb["param_id"]).to_pylist(); agg["params"].update(pid)
            agg["lrus"].update(pc.unique(tb["source_lru"]).to_pylist())
            pl = pc.unique(pc.binary_join_element_wise(tb["param_id"], tb["source_lru"], "|")).to_pylist(); agg["param_lru"].update(pl)
            agg["dict"].update(set(zip(pc.unique(tb["dict_version"]).to_pylist(), pc.unique(tb["dict_hash"]).to_pylist())))
            sid = tb["sortie_id"][0].as_py()
            ps = agg["per_sortie"][sid]; ps["rows"] += n; ps["params"].update(pid)
            ps["oor"] += int(((q >> 6) & 1).sum()); ps["sent"] += int((q & 1).sum())
            ts = tb["t_sample"].to_numpy(); ps["t0"] = int(ts.min()) if ps["t0"] is None else min(ps["t0"], int(ts.min())); ps["t1"] = int(ts.max()) if ps["t1"] is None else max(ps["t1"], int(ts.max()))
            raw = tb["record_id"].combine_chunks()
            buf = np.frombuffer(raw.buffers()[1], dtype=np.uint8)[raw.offset * 16:(raw.offset + len(raw)) * 16].reshape(-1, 16)
            rid_prefix[sid].append(buf[:, :8].copy().view(np.uint64).ravel())
    for sid, parts in rid_prefix.items():
        a = np.concatenate(parts); agg["rid_dups"] += int(len(a) - len(np.unique(a)))
    tel[tree] = dict(rows=agg["rows"], ingest_before_event=agg["ingest_before_event"], reserved_flag_bits=agg["reserved_flag_bits"],
                     nan_inf=agg["nan_inf"], flags=agg["flags"], sentinel_and_oor=agg["sentinel_and_oor"], any_flag=agg["any_flag"],
                     validity=dict(agg["validity"]), params=len(agg["params"]), lrus=sorted(agg["lrus"]),
                     params_per_lru=dict(collections.Counter(x.split("|")[1] for x in agg["param_lru"])),
                     rid_dup_prefix=agg["rid_dups"], dict=sorted(agg["dict"]),
                     per_sortie={k: dict(rows=v["rows"], params=len(v["params"]), oor=v["oor"], sentinel=v["sent"],
                                         recorded_s=round((v["t1"] - v["t0"]) / 1e9, 1)) for k, v in agg["per_sortie"].items()})
    print(tree, "param.samples done", round(time.time() - t_start, 1), "s", flush=True)
json.dump(tel, open(CACHE, "w"), indent=1, default=str)
OUT["telemetry"] = tel

# sortie manifests + run outcomes (consumer-side _runs metadata)
sm = FT["telemetry/sortie.manifest"].to_pandas()
runs = {r["sortie_id"]: r for r in M["runs"]["telemetry"]}
sorties = []
for _, r in sm.sort_values("sortie_id").iterrows():
    run = runs.get(r.sortie_id, {})
    sorties.append(dict(sortie=r.sortie_id, tail=r.tail_no, mission=r.mission_type,
                        t_start=pd.Timestamp(r.t_start, tz="UTC").tz_convert(IST).strftime("%d %b %H:%M"),
                        t_end=pd.Timestamp(r.t_end, tz="UTC").tz_convert(IST).strftime("%d %b %H:%M"),
                        landing=None if pd.isna(r.t_landing) else pd.Timestamp(int(r.t_landing), tz="UTC").tz_convert(IST).strftime("%H:%M"),
                        t_ingest=pd.Timestamp(r.t_ingest, tz="UTC").tz_convert(IST).strftime("%d %b %H:%M"),
                        download_lag_h=round((r.t_ingest - r.t_end) / 3.6e12, 2), recorded_s=round((r.t_end - r.t_start) / 1e9, 0),
                        completed=bool(run.get("completed")), run_end=(run.get("abort") or {}).get("phase"),
                        samples=tel["telemetry"]["per_sortie"].get(r.sortie_id, {}).get("rows"),
                        params=tel["telemetry"]["per_sortie"].get(r.sortie_id, {}).get("params"),
                        oor=tel["telemetry"]["per_sortie"].get(r.sortie_id, {}).get("oor"),
                        sentinel=tel["telemetry"]["per_sortie"].get(r.sortie_id, {}).get("sentinel")))
OUT["sorties"] = sorties
OUT["full_path"] = dict(rows=tel["telemetry_full_path"]["rows"], ch10_bytes=M["runs"]["full_path"][0]["ch10_bytes"],
                        window_s=M["runs"]["full_path"][0]["window_s"], sortie=M["runs"]["full_path"][0]["sortie_id"],
                        determinism=M["runs"]["determinism"][0])
OUT["row_invariants"] = rows

# ------------------------------------------------------------------ ingest timeline (epochs 06:00 → 06:00) and hour-of-day
def ing_series(key):
    tb = FT[key]; it = rows[key]["ingest_time"]
    return pd.to_datetime(np.asarray(tb[it].to_numpy(zero_copy_only=False)), utc=True).tz_convert(IST)
groups = {"Maintenance records": ["fleet/maint.records"], "Usage counters": ["fleet/usage.counters"],
          "BIT and cautions": ["fleet/events.bit_faults", "fleet/events.cautions"], "Orders": ["fleet/orders.commands", "fleet/orders.status"]}
epochs = pd.date_range(T - pd.Timedelta(days=59), T, freq="D")          # 60 cut-offs, each 06:00
tl = {}
hour = {}
for g, keys in groups.items():
    s = pd.concat([pd.Series(ing_series(k)) for k in keys])
    s = s[s <= T]
    # epoch e collects (e-24h, e]
    ns = s.apply(lambda x: x.value).values
    ep_ns = np.array([e.value for e in epochs])
    idx = np.searchsorted(ep_ns, ns, side="left")
    keep = ns > ep_ns[0] - 86400 * 10**9
    cnt = np.bincount(idx[keep], minlength=len(epochs))
    tl[g] = cnt.tolist()
    hour[g] = np.bincount(s.dt.hour.values, minlength=24).tolist()
OUT["timeline"] = dict(epochs=[e.strftime("%d %b") for e in epochs], series=tl, hour=hour,
                       total_60=int(sum(sum(v) for v in tl.values())))
# lags
lag = {}
for key, label in [("fleet/events.bit_faults", "BIT events"), ("fleet/events.cautions", "Cautions"), ("fleet/usage.counters", "Usage counters")]:
    tb = FT[key]; et, it = rows[key]["event_time"], rows[key]["ingest_time"]
    a = (tb[it].to_numpy() - tb[et].to_numpy()) / 3.6e12
    msk = tb[it].to_numpy() <= T_NS
    a = a[msk]
    lag[label] = dict(n=int(len(a)), p10=round(float(np.quantile(a, .1)), 2), median=round(float(np.median(a)), 2), p90=round(float(np.quantile(a, .9)), 2), max=round(float(a.max()), 2),
                      hist=np.histogram(a, bins=np.arange(0, 3.01, 0.1))[0].tolist())
mr = FT["fleet/maint.records"].to_pandas()
mr = mr[mr.t_ingest <= T_NS]
mr["lag_h"] = (mr.t_ingest - mr.t_event) / 3.6e12
lag_mr = {}
for rt_, g in mr.groupby("record_type"):
    a = g.lag_h.values
    lag_mr[rt_] = dict(n=int(len(a)), median=round(float(np.median(a)), 2), p90=round(float(np.quantile(a, .9)), 1), max=round(float(a.max()), 1),
                       same_hour=round(float((a <= 1).mean()), 4), over24=int((a > 24).sum()))
a = mr.lag_h.values
lag["Maintenance records"] = dict(n=int(len(a)), median=round(float(np.median(a)), 2), p90=round(float(np.quantile(a, .9)), 2),
                                  same_hour=round(float((a <= 1).mean()), 4), over24=int((a > 24).sum()), over7d=int((a > 168).sum()), max=round(float(a.max()), 1))
OUT["lag"] = lag; OUT["lag_maint"] = lag_mr

# ------------------------------------------------------------------ as-of store tests
mrr = FT["fleet/maint.records"].to_pandas()
mrr["rid"] = mrr.record_id.apply(lambda b: bytes(b).hex())
evr = FT["fleet/events.bit_faults"].to_pandas()
def as_of(df, t_ns, key=("tail_no", "record_type", "record_key")):
    v = df[df.t_ingest <= t_ns]
    return v.sort_values(["record_version", "t_ingest"]).drop_duplicates(list(key), keep="last")
def features(t_ns, mdf, edf):
    v = as_of(mdf, t_ns)
    av = v[v.record_type == "AVAILABILITY_STATE"].sort_values("t_event").groupby("tail_no").availability_state.last().to_dict()
    jobs = v[(v.record_type == "DEFECT_WO") & (v.status != "CLOSED")].groupby("tail_no").size().to_dict()
    dem = v[(v.record_type == "SUPPLY_DEMAND") & (v.status != "CLOSED")].groupby(["tail_no", "priority"]).size().to_dict()
    e = edf[edf.t_ingest <= t_ns]
    codes = e.groupby(["tail_no", "event_code"]).size().to_dict()
    fh = round(float(v[v.record_type == "SORTIE"].flight_hours.sum()), 6)
    return json.dumps(dict(av=av, jobs=jobs, dem={str(k): x for k, x in dem.items()}, codes={str(k): x for k, x in codes.items()}, fh=fh), sort_keys=True, default=str)
rng = np.random.default_rng(20260622)
def perturb_future(df, t_ns, cols):
    d = df.copy(); fut = np.where(d.t_ingest.values > t_ns)[0]
    for c in cols:
        if c in d.columns and len(fut) > 1:
            d.iloc[fut, d.columns.get_loc(c)] = d.iloc[fut][c].values[rng.permutation(len(fut))]
    if len(fut):
        d.iloc[fut, d.columns.get_loc("t_event")] = d.iloc[fut].t_event.values - rng.integers(0, 90 * 86400 * 10**9, len(fut))
    return d
cuts = [e.value for e in epochs]
passed = 0; changed_rows = 0
for c in cuts:
    f0 = features(c, mrr, evr)
    mp = perturb_future(mrr, c, ["availability_state", "status", "tail_no", "record_key", "flight_hours", "priority", "record_version"])
    ep = perturb_future(evr.rename(columns={"t_occurrence": "t_event"}), c, ["event_code", "tail_no"]).rename(columns={"t_event": "t_occurrence"})
    changed_rows += int((mrr.t_ingest > c).sum())
    if features(c, mp, ep) == f0: passed += 1
# negative control: an event-time read (t_event <= t) must differ for at least one cut — proves the test can fail
def features_event_time(t_ns, mdf, edf):
    v = mdf[mdf.t_event <= t_ns].sort_values(["record_version", "t_ingest"]).drop_duplicates(["tail_no", "record_type", "record_key"], keep="last")
    return json.dumps(dict(n=len(v), fh=round(float(v[v.record_type == "SORTIE"].flight_hours.sum()), 6),
                           dem=int(((v.record_type == "SUPPLY_DEMAND") & (v.status != "CLOSED")).sum())), sort_keys=True)
neg = sum(1 for c in cuts if features_event_time(c, mrr, evr) != features_event_time(c, perturb_future(mrr, c, ["status", "flight_hours"]), evr))
OUT["asof_tests"] = dict(cuts=len(cuts), shuffle_future_passed=passed, first_cut=epochs[0].strftime("%d %b %H:%M"), last_cut=epochs[-1].strftime("%d %b %H:%M"),
                         event_time_read_detected=neg, perturbed_row_cut_pairs=changed_rows)
# visible vs total per topic, plus the newest record each topic contributes to the snapshot
vis = {}
for key in FT:
    tb = FT[key]; it = rows[key]["ingest_time"]; a = tb[it].to_numpy()
    newest = a[a <= T_NS].max() if (a <= T_NS).any() else None
    vis[key] = dict(total=int(len(a)), visible=int((a <= T_NS).sum()), late=rows[key]["late_after_snapshot"],
                    newest=pd.Timestamp(int(newest), tz="UTC").tz_convert(IST).strftime("%d %b %H:%M") if newest is not None else None)
OUT["visible"] = vis
OUT["elapsed_s"] = round(time.time() - t_start, 1)

json.dump(OUT, open(V + "data_foundation_asof_20260622.json", "w"), indent=1, default=str)
import copy
UI = copy.deepcopy(OUT)
for k in UI["release"]["seeds"].values(): k.pop("scenario", None)   # scenario names are internal, not shown
open("/Users/abishaikc/Phalanx-Solution/video/screens/assets/data-data.js", "w").write(
    "/* computed by video/data/scripts/data_foundation.py — release v0.9, snapshot 22 Jun 2026 06:00 IST */\nwindow.PHX_DF = " + json.dumps(UI, default=str) + ";\n")
print(json.dumps(OUT, indent=1, default=str))
