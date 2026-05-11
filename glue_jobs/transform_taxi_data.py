"""
Glue ETL Job: NYC Taxi raw → curated

Reads partitioned Parquet from the raw bucket, applies data quality filters,
derives analytics-ready columns, and writes optimized Parquet to the curated
bucket, partitioned by year/month/day for efficient downstream queries.

Job arguments expected:
    --JOB_NAME             : Glue job name (auto-injected)
    --raw_database         : Glue database holding the raw table
    --raw_table            : Source table name (raw)
    --curated_bucket       : Target S3 bucket name (no s3:// prefix)
    --curated_path         : Sub-path inside curated bucket (e.g. yellow_taxi)
    --taxi_type_filter     : Filter raw data on this taxi_type (e.g. yellow)
"""

import sys
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType

# ============================================
# Setup
# ============================================
args = getResolvedOptions(
    sys.argv,
    [
        "JOB_NAME",
        "raw_database",
        "raw_table",
        "curated_bucket",
        "curated_path",
        "taxi_type_filter",
    ],
)

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args["JOB_NAME"], args)

logger = glue_context.get_logger()
logger.info(f"Starting ETL job for taxi_type={args['taxi_type_filter']}")

# ============================================
# Read from Glue Catalog (raw layer)
# ============================================
raw_dyf = glue_context.create_dynamic_frame.from_catalog(
    database=args["raw_database"],
    table_name=args["raw_table"],
    transformation_ctx="raw_dyf",  # required for job bookmarks
    push_down_predicate=f"taxi_type = '{args['taxi_type_filter']}'",
)

raw_df = raw_dyf.toDF()
input_count = raw_df.count()
logger.info(f"Input row count: {input_count}")

if input_count == 0:
    logger.warn("No data to process. Exiting cleanly.")
    job.commit()
    sys.exit(0)

# ============================================
# Data Quality filters
# ============================================
# Standardize column names to lowercase (some Parquet files have mixed case)
clean_df = raw_df.toDF(*[c.lower() for c in raw_df.columns])

# Compute trip duration in minutes (used in filters and as derived col)
clean_df = clean_df.withColumn(
    "trip_duration_minutes",
    (
        F.unix_timestamp("tpep_dropoff_datetime")
        - F.unix_timestamp("tpep_pickup_datetime")
    )
    / 60.0,
)

# Filter rules — these are documented & easy to tune
quality_filters = (
    (F.col("tpep_pickup_datetime").isNotNull())
    & (F.col("tpep_dropoff_datetime").isNotNull())
    & (F.col("trip_duration_minutes") > 0)
    & (F.col("trip_duration_minutes") < 24 * 60)  # < 24h
    & (F.col("trip_distance") > 0)
    & (F.col("trip_distance") < 200)  # < 200 miles (NYC sanity)
    & (F.col("fare_amount") >= 0)
    & (F.col("total_amount") >= 0)
    & (F.col("passenger_count").isNotNull())
    & (F.col("passenger_count") > 0)
    & (F.col("passenger_count") <= 9)
)

filtered_df = clean_df.filter(quality_filters)
filtered_count = filtered_df.count()
removed = input_count - filtered_count
removal_rate = (removed / input_count) * 100 if input_count > 0 else 0
logger.info(
    f"Quality filtering: {filtered_count} rows kept, "
    f"{removed} removed ({removal_rate:.2f}%)"
)

# ============================================
# Derived columns (analytics-ready)
# ============================================
enriched_df = (
    filtered_df
    # Date components for partitioning & analysis
    .withColumn("pickup_date", F.to_date("tpep_pickup_datetime"))
    .withColumn("pickup_year", F.year("tpep_pickup_datetime").cast(IntegerType()))
    .withColumn("pickup_month", F.month("tpep_pickup_datetime").cast(IntegerType()))
    .withColumn("pickup_day", F.dayofmonth("tpep_pickup_datetime").cast(IntegerType()))
    .withColumn("pickup_hour", F.hour("tpep_pickup_datetime").cast(IntegerType()))
    .withColumn(
        "pickup_dayofweek", F.dayofweek("tpep_pickup_datetime").cast(IntegerType())
    )
    # Business-friendly flags
    .withColumn(
        "is_weekend",
        F.when(F.dayofweek("tpep_pickup_datetime").isin([1, 7]), True).otherwise(False),
    )
    .withColumn(
        "pickup_period",
        F.when(
            (F.hour("tpep_pickup_datetime") >= 6)
            & (F.hour("tpep_pickup_datetime") < 12),
            "morning",
        )
        .when(
            (F.hour("tpep_pickup_datetime") >= 12)
            & (F.hour("tpep_pickup_datetime") < 18),
            "afternoon",
        )
        .when(
            (F.hour("tpep_pickup_datetime") >= 18)
            & (F.hour("tpep_pickup_datetime") < 22),
            "evening",
        )
        .otherwise("night"),
    )
    # Economic metrics
    .withColumn(
        "fare_per_mile",
        F.when(
            F.col("trip_distance") > 0,
            F.round(F.col("fare_amount") / F.col("trip_distance"), 2),
        ).otherwise(None),
    )
    .withColumn(
        "tip_percentage",
        F.when(
            F.col("fare_amount") > 0,
            F.round((F.col("tip_amount") / F.col("fare_amount")) * 100, 2),
        ).otherwise(None),
    )
)

# ============================================
# Write to curated bucket (Parquet + Snappy + partitioned)
# ============================================
output_path = f"s3://{args['curated_bucket']}/{args['curated_path']}/"
logger.info(f"Writing to {output_path}")

(
    enriched_df.repartition("pickup_year", "pickup_month", "pickup_day")
    .write.mode("append")
    .partitionBy("pickup_year", "pickup_month", "pickup_day")
    .option("compression", "snappy")
    .parquet(output_path)
)

logger.info(f"Wrote {filtered_count} rows to curated layer")
job.commit()
