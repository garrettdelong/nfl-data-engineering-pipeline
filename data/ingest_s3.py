import boto3
import requests
#import os
from datetime import datetime

s3 = boto3.client("s3")
BUCKET_NAME = "nfl-pipeline-raw"
S3_PREFIX = "pbp/"  # folder inside bucket

current_year = datetime.now().year

years = list(range(2000, current_year + 1))
base_url = "https://github.com/nflverse/nflverse-data/releases/download/pbp"

for year in years:
    url = f"{base_url}/play_by_play_{year}.parquet"
    s3_key = f"{S3_PREFIX}play_by_play_{year}.parquet"

    print(f"Downloading {year} from {url} and uploading to s3://{BUCKET_NAME}/{s3_key}")

    response = requests.get(url, stream=True)

    if response.status_code != 200:
        print(f"⚠️ Year {year} not available (status {response.status_code}), skipping.")
        continue
    else:
        # Stream response content directly into S3
        s3.upload_fileobj(response.raw, BUCKET_NAME, s3_key)

print("✅ All available files uploaded directly to S3.")
