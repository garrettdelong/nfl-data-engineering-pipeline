#import pandas as pd
#import pyarrow.parquet as pq
import requests
import os
from datetime import datetime

current_year = datetime.now().year

years = list(range(2000, current_year + 1))
base_url = "https://github.com/nflverse/nflverse-data/releases/download/pbp"

# Create local data folder
os.makedirs("data/play_by_play", exist_ok=True) 

for year in years:
    url = f"{base_url}/play_by_play_{year}.parquet"
    print(f"Downloading {year}...")
    
    r = requests.get(url)

    if r.status_code != 200:
        print(f"⚠️ Year {year} not available (status {r.status_code}), skipping.")
        continue

    open(f"data/play_by_play/play_by_play_{year}.parquet", "wb").write(r.content)