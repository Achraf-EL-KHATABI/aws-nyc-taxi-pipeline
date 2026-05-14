"""
Validate the curated layer against the data quality expectations.

Usage:
    python data_quality/validate_curated.py
    python data_quality/validate_curated.py --layer raw
    python data_quality/validate_curated.py --layer curated --max-files 5

Reads Parquet files directly from S3 (no Spark needed — uses pandas + pyarrow).
Exits with code 0 if all expectations pass, 1 otherwise.

Designed to run in CI or as a Step Functions task after the ETL job.
"""
import argparse
import logging
import os
import sys
from pathlib import Path

import boto3
import great_expectations as gx
import pandas as pd
import pyarrow.parquet as pq
from dotenv import load_dotenv

# Add this directory to path so we can import expectations
sys.path.insert(0, str(Path(__file__).parent))
from expectations import get_curated_expectations, get_raw_expectations  # noqa: E402

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


# ============================================
# S3 helpers
# ============================================
def list_parquet_files(bucket: str, prefix: str, s3_client, max_files: int = 10) -> list:
    """List Parquet files under a prefix, sampling across all partitions.
    
    Instead of returning the first N files (which biases toward early partitions
    like outliers), we collect ALL files and return a representative sample.
    """
    paginator = s3_client.get_paginator("list_objects_v2")
    all_files = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                all_files.append(obj["Key"])

    if not all_files:
        return []

    logger.info(f"Total Parquet files found under prefix: {len(all_files)}")

    # If we have more files than requested, sample evenly across them
    if len(all_files) <= max_files:
        return all_files

    # Even-distribution sampling: take every Nth file
    step = len(all_files) // max_files
    sampled = [all_files[i * step] for i in range(max_files)]
    logger.info(f"Sampling {len(sampled)} files evenly distributed across partitions")
    return sampled


def load_parquet_sample(bucket: str, keys: list, s3_client) -> pd.DataFrame:
    """Load a sample of Parquet files from S3 into a single DataFrame.
    
    S3 streaming bodies aren't seekable, so we read the full bytes into
    BytesIO before letting pyarrow parse them.
    """
    import io
    
    dfs = []
    for key in keys:
        logger.info(f"Loading s3://{bucket}/{key}")
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        body_bytes = obj["Body"].read()
        df = pd.read_parquet(io.BytesIO(body_bytes))
        dfs.append(df)

    if not dfs:
        logger.warning("No data loaded — empty layer?")
        return pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)
    logger.info(f"Loaded {len(combined):,} rows from {len(keys)} file(s)")
    return combined


# ============================================
# Great Expectations runner
# ============================================
def validate_dataframe(df: pd.DataFrame, expectations: list, suite_name: str) -> dict:
    """
    Run all expectations against a DataFrame.

    Returns:
        dict with 'success' (bool), 'passed' (int), 'failed' (int), 'details' (list)
    """
    if df.empty:
        return {
            "success": False,
            "passed": 0,
            "failed": 0,
            "details": [{"error": "Empty dataset — nothing to validate"}],
        }

    # GE v1.x ephemeral context — no project setup needed
    context = gx.get_context(mode="ephemeral")

    # Register the dataframe as a data source
    data_source = context.data_sources.add_pandas(name="taxi_data_source")
    data_asset = data_source.add_dataframe_asset(name=suite_name)
    batch_definition = data_asset.add_batch_definition_whole_dataframe(name="batch")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    # Run each expectation
    details = []
    passed, failed = 0, 0

    for exp_def in expectations:
        exp_type = exp_def["type"]
        kwargs = exp_def["kwargs"]
        description = exp_def.get("meta", {}).get("description", "")

        try:
            # Build expectation object dynamically
            ExpectationClass = getattr(gx.expectations, _to_camel(exp_type))
            expectation = ExpectationClass(**kwargs)
            result = batch.validate(expectation)

            success = result.success
            if success:
                passed += 1
                logger.info(f"PASS | {exp_type} on {kwargs.get('column', 'table')}")
            else:
                failed += 1
                logger.error(f"FAIL | {exp_type} on {kwargs.get('column', 'table')}")
                logger.error(f"       Description: {description}")
                # Include unexpected count if available
                if hasattr(result, "result") and result.result:
                    unexpected_count = result.result.get("unexpected_count", "?")
                    element_count = result.result.get("element_count", "?")
                    logger.error(f"       {unexpected_count}/{element_count} rows failed")

            details.append({
                "expectation": exp_type,
                "column": kwargs.get("column", "(table-level)"),
                "success": success,
                "description": description,
            })

        except Exception as e:
            failed += 1
            logger.error(f"ERROR | {exp_type}: {e}")
            details.append({
                "expectation": exp_type,
                "column": kwargs.get("column", "(table-level)"),
                "success": False,
                "error": str(e),
            })

    return {
        "success": failed == 0,
        "passed": passed,
        "failed": failed,
        "total": passed + failed,
        "details": details,
    }


def _to_camel(snake: str) -> str:
    """Convert expect_column_values_to_be_between → ExpectColumnValuesToBeBetween."""
    return "".join(word.capitalize() for word in snake.split("_"))


# ============================================
# CLI
# ============================================
def parse_args():
    parser = argparse.ArgumentParser(description="Validate NYC Taxi data quality.")
    parser.add_argument(
        "--layer",
        choices=["raw", "curated"],
        default="curated",
        help="Which layer to validate (default: curated)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=5,
        help="Max number of Parquet files to sample (default: 5)",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="S3 prefix filter (default: depends on layer)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    region = os.getenv("AWS_REGION")
    if not region:
        logger.error("Missing AWS_REGION in environment.")
        sys.exit(1)

    if args.layer == "raw":
        bucket = os.getenv("RAW_BUCKET")
        prefix = args.prefix or "taxi_type=yellow/"
        expectations = get_raw_expectations()
        suite_name = "raw_yellow_taxi"
    else:
        bucket = os.getenv("CURATED_BUCKET")
        prefix = args.prefix or "yellow_taxi/"
        expectations = get_curated_expectations()
        suite_name = "curated_yellow_taxi"

    if not bucket:
        logger.error(f"Missing bucket env var for layer={args.layer}")
        sys.exit(1)

    logger.info(f"Validating {args.layer} layer at s3://{bucket}/{prefix}")
    logger.info(f"Running {len(expectations)} expectations on suite: {suite_name}")
    logger.info("=" * 70)

    s3 = boto3.client("s3", region_name=region)

    # List & sample files
    keys = list_parquet_files(bucket, prefix, s3, max_files=args.max_files)
    if not keys:
        logger.error(f"No Parquet files found at s3://{bucket}/{prefix}")
        sys.exit(1)

    df = load_parquet_sample(bucket, keys, s3)
    logger.info("=" * 70)

    # Validate
    report = validate_dataframe(df, expectations, suite_name)

    # Summary
    logger.info("=" * 70)
    logger.info(f"VALIDATION SUMMARY — {suite_name}")
    logger.info(f"  Total expectations : {report['total']}")
    logger.info(f"  Passed             : {report['passed']}")
    logger.info(f"  Failed             : {report['failed']}")
    logger.info("=" * 70)

    if report["success"]:
        logger.info("✅ All data quality expectations passed!")
        sys.exit(0)
    else:
        logger.error("❌ Some expectations FAILED — data quality contract breached")
        sys.exit(1)


if __name__ == "__main__":
    main()