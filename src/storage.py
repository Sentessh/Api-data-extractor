# src/storage.py
import os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
from typing import Tuple

def save_parquet(df: pd.DataFrame, path: str, engine='pyarrow') -> Tuple[str, str]:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(path, index=False, engine=engine)
        print(f"[OK] Parquet salvo em: {path}")
        return path, "parquet"
    except Exception as e:
        csv_path = os.path.splitext(path)[0] + ".csv"
        df.to_csv(csv_path, index=False)
        print(f"[WARN] Parquet indisponível ({e}). Salvei CSV em: {csv_path}")
        return csv_path, "csv"

def save_csv(df: pd.DataFrame, path: str) -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path

def upsert_postgres(df: pd.DataFrame, table_name: str, pg_url: str, if_exists='append'):
    engine = create_engine(pg_url)
    df.to_sql(table_name, con=engine, if_exists=if_exists, index=False, method='multi')