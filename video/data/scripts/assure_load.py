"""As-of reader for the assurance screens (assurance / policies / provenance).

Reads the consumer fleet tree (contract phalanx.ground_decoder_contract 0.2.0) file by file, rejects any file whose
schema metadata carries a different contract hash, decodes record ids to hex, adds IST *_dt columns and dedupes by
the scoped key (tail_no / target_tail_no, record_id), keeping the earliest t_ingest. Never touches _restricted_labels/.
"""
import glob
import pyarrow as pa, pyarrow.parquet as pq, pandas as pd, numpy as np  # noqa: F401

ROOT = "/Users/abishaikc/Downloads/phalanx_data_layer_preview/data/v0.9/"
B = ROOT + "fleet/"
IST = "Asia/Kolkata"
CONTRACT_HASH = "a4396f1d5482ce7816354ed7c9b040179d3c1467a7ca6e75b21fd71e1a904566"
DICT_HASH = "9428d30f578f0318161737a6e6235f332632b2827b76eb6d853064544e7fbc8b"
SNAP = pd.Timestamp("2026-06-22 06:00", tz=IST)
OUT = "/Users/abishaikc/Phalanx-Solution/video/data/"


def files(topic):
    assert "_restricted" not in topic
    return sorted(glob.glob(B + topic + "/**/*.parquet", recursive=True))


def rd(topic):
    tabs = []
    for f in files(topic):
        t = pq.read_table(f)
        h = (t.schema.metadata or {}).get(b"phalanx.contract_hash", b"").decode()
        if h != CONTRACT_HASH:
            raise ValueError(f"contract hash mismatch in {f}: {h}")
        tabs.append(t.replace_schema_metadata(None))
    tb = pa.concat_tables(tabs, promote_options="default")
    for i, f in enumerate(tb.schema):
        if pa.types.is_list(f.type) and pa.types.is_fixed_size_binary(f.type.value_type):
            tb = tb.set_column(i, f.name, tb.column(i).cast(pa.list_(pa.binary())))
    df = tb.to_pandas()
    df["rid"] = df.record_id.apply(lambda b: bytes(b).hex())
    key = "target_tail_no" if "target_tail_no" in df else ("tail_no" if "tail_no" in df else None)
    tcol = next(c for c in ("t_ingest", "t_issued", "t_status") if c in df)
    df = df.sort_values([tcol, "rid"], kind="mergesort")
    df = df.drop_duplicates(([key] if key else []) + ["rid"])
    for c in list(df.columns):
        if c.startswith("t_") and not c.endswith("_dt") and pd.api.types.is_numeric_dtype(df[c]):
            df[c + "_dt"] = pd.to_datetime(df[c].astype("Int64"), unit="ns", utc=True).dt.tz_convert(IST)
    df["t_avail_dt"] = df[tcol + "_dt"]
    return df.reset_index(drop=True)


def asof(df, t=SNAP):
    return df[df.t_avail_dt <= t]
