# src/normalizer.py
import pandas as pd
from typing import List, Dict, Any

def flatten_items_to_df(items: List[Dict[str,Any]]) -> pd.DataFrame:
    # pandas.json_normalize is super helpful
    df = pd.json_normalize(items, sep='_')
    return df