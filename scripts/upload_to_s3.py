"""
NYC Taxi Data Ingestion Script

Downloads NYC TLC taxi trip records (Parquet format) from the official source
and uploads them to the project's raw S3 bucket with Hive-style partitioning.

Usage:
    python scripts/upload_to_s3.py --year 2024 --months 1
    python scripts/upload_to_s3.py --year 2024 --months 1 2 3
    python scripts/upload_to_s3.py --taxi-type green --year 2024 --months 1
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import boto3
import requests
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from tqdm import tqdm

# ============================================
# Configuration
# ============================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

NYC_TLC_BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
DOWNLOAD_DIR = Path(__file__).parent.parent / "data"
DOWNLOAD_DIR.mkdir(exist_ok=True)


# ============================================
# Functions
# ============================================
def get_s3_client(region: str):
    """Initialize and return a boto3 S3 client."""
    return boto3.client("s3", region_name=region)


def build_filename(taxi_type: str, year: int, month: int) -> str:
    """Build the official NYC TLC filename for a given period."""
    return f"{taxi_type}_tripdata_{year}-{month:02d}.parquet"


def download_file(url: str, dest_path: Path) -> bool:
    """Download a file with a progress bar. Returns True if successful."""
    if dest_path.exists():
        logger.info(f"Already downloaded: {dest_path.name} (skipping)")
        return True

    logger.info(f"Downloading from {url}")
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))

        with open(dest_path, "wb") as f, tqdm(
            desc=dest_path.name,
            total=total_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                bar.update(len(chunk))

        logger.info(f"Downloaded: {dest_path}")
        return True

    except requests.RequestException as e:
        logger.error(f"Download failed: {e}")
        if dest_path.exists():
            dest_path.unlink()  # cleanup partial file
        return False


def upload_to_s3(s3_client, local_path: Path, bucket: str, s3_key: str) -> bool:
    """Upload a local file to S3 with progress bar."""
    file_size = local_path.stat().st_size
    logger.info(f"Uploading to s3://{bucket}/{s3_key}")

    try:
        with tqdm(
            desc=local_path.name,
            total=file_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            s3_client.upload_file(
                str(local_path),
                bucket,
                s3_key,
                Callback=lambda chunk: bar.update(chunk),
            )
        logger.info(f"Uploaded: s3://{bucket}/{s3_key}")
        return True

    except ClientError as e:
        logger.error(f"Upload failed: {e}")
        return False


def ingest(taxi_type: str, year: int, month: int, bucket: str, s3_client) -> bool:
    """Full ingestion pipeline for one taxi_type/year/month combination."""
    filename = build_filename(taxi_type, year, month)
    url = f"{NYC_TLC_BASE_URL}/{filename}"
    local_path = DOWNLOAD_DIR / filename

    # Hive-style partitioning: enables Glue/Athena auto partition discovery
    s3_key = f"taxi_type={taxi_type}/year={year}/month={month:02d}/{filename}"

    if not download_file(url, local_path):
        return False

    if not upload_to_s3(s3_client, local_path, bucket, s3_key):
        return False

    return True


# ============================================
# CLI
# ============================================
def parse_args():
    parser = argparse.ArgumentParser(description="Ingest NYC Taxi data into S3.")
    parser.add_argument(
        "--taxi-type",
        choices=["yellow", "green", "fhv", "fhvhv"],
        default="yellow",
        help="Taxi type (default: yellow)",
    )
    parser.add_argument("--year", type=int, required=True, help="Year (e.g., 2024)")
    parser.add_argument(
        "--months",
        type=int,
        nargs="+",
        required=True,
        help="One or more months (e.g., --months 1 2 3)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    region = os.getenv("AWS_REGION")
    bucket = os.getenv("RAW_BUCKET")

    if not region or not bucket:
        logger.error(
            "Missing AWS_REGION or RAW_BUCKET in environment. "
            "Did you create a .env file?"
        )
        sys.exit(1)

    logger.info(f"Target: s3://{bucket} ({region})")
    logger.info(
        f"Ingesting {args.taxi_type} taxi data for {args.year}, "
        f"months {args.months}"
    )

    s3 = get_s3_client(region)

    successes, failures = 0, 0
    for month in args.months:
        ok = ingest(args.taxi_type, args.year, month, bucket, s3)
        successes += int(ok)
        failures += int(not ok)

    logger.info(f"Done. Success: {successes}, Failures: {failures}")
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
