import boto3
import requests
from datetime import datetime
import argparse

def table_by_year_ingest(BUCKET_NAME, s3, base_url, years, table_name, folder):
    for year in years:
        url = f"{base_url}/{folder}/{table_name}_{year}.parquet"
        s3_key = f"{folder}/{table_name}_{year}.parquet"

        print(f"Downloading {year} from {url} and uploading to s3://{BUCKET_NAME}/{s3_key}")

        response = requests.get(url, stream=True)

        if response.status_code != 200:
            print(f"⚠️ Year {year} not available (status {response.status_code}), skipping.")
            continue
        else:
            # Stream response content directly into S3
            s3.upload_fileobj(response.raw, BUCKET_NAME, s3_key)

    print("✅ All available files uploaded directly to S3.")

def table_single_file_ingest(BUCKET_NAME, s3, base_url, table_name, folder):
    url = f"{base_url}/{folder}/{table_name}.parquet"
    s3_key = f"{folder}/{table_name}.parquet"

    print(f"Downloading {table_name} from {url} and uploading to s3://{BUCKET_NAME}/{s3_key}")

    response = requests.get(url, stream=True)

    if response.status_code != 200:
        print(f"⚠️ {table_name} not available (status {response.status_code}), skipping.")
    else:
        # Stream response content directly into S3
        s3.upload_fileobj(response.raw, BUCKET_NAME, s3_key)

    print("✅ All available files uploaded directly to S3.")

INGEST_FUNCTIONS = {
    "pbp": "play_by_play",
    "schedules": "games",
    "teams": "teams_colors_logos",
    "player_stats": "player_stats",
    "weekly_rosters": "roster_weekly",
    "stats_player": "stats_player_week",
    "stats_team": "stats_team_week",
    "all": None
}

def main():
    
    #S3_PREFIX = "pbp/"  # folder inside bucket
    s3 = boto3.client("s3")
    base_url = "https://github.com/nflverse/nflverse-data/releases/download"
    BUCKET_NAME = "nfl-pipeline-raw"

    current_year = datetime.now().year
    years = list(range(2000, current_year + 1))

    parser = argparse.ArgumentParser(description="Get which data I want to ingest to S3")
    parser.add_argument(
        "--table", 
        type=str, 
        required=True,
        choices=INGEST_FUNCTIONS.keys(), 
        help="Which table to ingest")
    
    args = parser.parse_args()
    
    if args.table == "all":
        for folder, table_name in INGEST_FUNCTIONS.items():
            if folder == 'all':
                continue
            elif folder in ["schedules", "teams"]: 
                table_single_file_ingest(BUCKET_NAME, s3, base_url, table_name, folder)
            else:
                table_by_year_ingest(BUCKET_NAME, s3, base_url, years, table_name, folder)
    else:
        table = INGEST_FUNCTIONS[args.table]
        if args.table in ["schedules", "teams"]:
            table_single_file_ingest(BUCKET_NAME, s3, base_url, table, args.table)
        else:
            table_by_year_ingest(BUCKET_NAME, s3, base_url, years, table, args.table)

if __name__ == "__main__":
    main()
