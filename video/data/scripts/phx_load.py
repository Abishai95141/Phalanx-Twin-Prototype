import pyarrow.dataset as ds, pyarrow as pa, pandas as pd, numpy as np
B="/Users/abishaikc/Downloads/phalanx_data_layer_preview/data/v0.9/fleet/"
IST="Asia/Kolkata"
def rd(t):
    d=ds.dataset(B+t,format="parquet",partitioning=None)
    tb=d.to_table()
    for i,f in enumerate(tb.schema):
        if pa.types.is_list(f.type) and pa.types.is_fixed_size_binary(f.type.value_type): tb=tb.set_column(i,f.name,tb.column(i).cast(pa.list_(pa.binary())))
    df=tb.to_pandas()
    df["rid"]=df.record_id.apply(lambda b: bytes(b).hex())
    key="target_tail_no" if "target_tail_no" in df else "tail_no"
    df=df.sort_values("t_ingest" if "t_ingest" in df else "t_issued").drop_duplicates([key,"rid"])
    for c in df.columns:
        if c.startswith("t_") and not c.endswith("_dt") and pd.api.types.is_numeric_dtype(df[c]):
            df[c+"_dt"]=pd.to_datetime(df[c].astype("Int64"),unit="ns",utc=True).dt.tz_convert(IST)
    return df
