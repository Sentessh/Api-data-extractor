# src/run_sync.py
import os
import json
import logging
from dotenv import load_dotenv
from src.http_client import HTTPClient
from src.extractor import Extractor
from src.normalizer import flatten_items_to_df
from src.storage import save_parquet, upsert_postgres

logging.basicConfig(level=logging.INFO)
load_dotenv()

API_BASE = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
RATE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
OUT = os.getenv("OUTPUT_DIR", "./data")
PG = os.getenv("POSTGRES_URL")

headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}

client = HTTPClient(API_BASE, headers=headers, rate_per_minute=RATE)
extractor = Extractor(client, page_param=os.getenv("PAGE_PARAM","page"), size_param=os.getenv("PAGE_SIZE_PARAM","limit"), page_size=int(os.getenv("PAGE_SIZE","100")))

def main():
    all_items = []
    for item in extractor.extract_paginated("/v1/resources", params={"some_filter":"value"}, item_key="data"):
        all_items.append(item)
    if not all_items:
        print("No items found")
        return
    df = flatten_items_to_df(all_items)
    save_parquet(df, f"{OUT}/resources.parquet")
    if PG:
        upsert_postgres(df, "resources", PG)
    print("Done. Saved", len(df), "rows")

if __name__ == "__main__":
    main()