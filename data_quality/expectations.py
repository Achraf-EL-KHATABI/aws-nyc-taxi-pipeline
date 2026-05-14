"""
Data Quality Expectations for the NYC Taxi pipeline.

Defines business rules that must hold for every batch of curated data.
If any of these break, the pipeline should fail fast and alert the team.

Two suites are defined:
1. raw_layer_suite      — minimal sanity checks on raw ingest
2. curated_layer_suite  — full business rules on transformed data

These are the contracts the pipeline guarantees to downstream consumers.
"""
from typing import Dict, List


# ============================================
# CURATED LAYER — Business rules
# ============================================
# These rules encode our understanding of "valid taxi trip data".
# Each rule documents a business expectation, not just a technical schema.


def get_curated_expectations() -> List[Dict]:
    """
    Returns the list of expectations for the curated yellow_taxi table.

    Format: each expectation is a dict with:
    - expectation_type: GE method name
    - kwargs: parameters for that expectation
    - meta: human-readable description (for reports)

    These are designed to be re-run on every batch in CI/CD.
    """
    return [
        # -----------------------------------------------------------------
        # SCHEMA: required columns must exist
        # -----------------------------------------------------------------
        {
            "type": "expect_column_to_exist",
            "kwargs": {"column": "vendorid"},
            "meta": {"description": "Vendor ID is the primary identifier of every trip"},
        },
        {
            "type": "expect_column_to_exist",
            "kwargs": {"column": "tpep_pickup_datetime"},
            "meta": {"description": "Pickup timestamp is required for time-series analytics"},
        },
        {
            "type": "expect_column_to_exist",
            "kwargs": {"column": "trip_duration_minutes"},
            "meta": {"description": "Derived column from ETL — must be present after transform"},
        },
        {
            "type": "expect_column_to_exist",
            "kwargs": {"column": "pickup_period"},
            "meta": {"description": "Derived bucket: morning/afternoon/evening/night"},
        },
        {
            "type": "expect_column_to_exist",
            "kwargs": {"column": "is_weekend"},
            "meta": {"description": "Derived boolean for weekend vs weekday analytics"},
        },

        # -----------------------------------------------------------------
        # COMPLETENESS: critical columns must not be null
        # -----------------------------------------------------------------
        {
            "type": "expect_column_values_to_not_be_null",
            "kwargs": {"column": "vendorid"},
            "meta": {"description": "Every trip must have a vendor — no anonymous trips"},
        },
        {
            "type": "expect_column_values_to_not_be_null",
            "kwargs": {"column": "tpep_pickup_datetime"},
            "meta": {"description": "Without pickup time, the record has no temporal anchor"},
        },
        {
            "type": "expect_column_values_to_not_be_null",
            "kwargs": {"column": "fare_amount"},
            "meta": {"description": "Fare is required for revenue analytics"},
        },

        # -----------------------------------------------------------------
        # BUSINESS RULES: value ranges
        # -----------------------------------------------------------------
        {
            "type": "expect_column_values_to_be_between",
            "kwargs": {
                "column": "trip_duration_minutes",
                "min_value": 0,
                "max_value": 1440,  # max 24h (= 1440 min) per ETL filter
                "strict_min": True,
            },
            "meta": {"description": "Trip duration must be positive and < 24h (ETL contract)"},
        },
        {
            "type": "expect_column_values_to_be_between",
            "kwargs": {
                "column": "trip_distance",
                "min_value": 0,
                "max_value": 200,  # max 200 miles per ETL filter
                "strict_min": True,
            },
            "meta": {"description": "Distance must be positive and realistic (< 200 miles)"},
        },
        {
            "type": "expect_column_values_to_be_between",
            "kwargs": {
                "column": "passenger_count",
                "min_value": 1,
                "max_value": 9,
            },
            "meta": {"description": "Passenger count: 1-9 (ETL contract)"},
        },
        {
            "type": "expect_column_values_to_be_between",
            "kwargs": {
                "column": "fare_amount",
                "min_value": 0,
                "max_value": 1000,  # extreme upper bound for outliers
            },
            "meta": {"description": "Fare must be non-negative; cap protects against bad records"},
        },

        # -----------------------------------------------------------------
        # CATEGORICAL CONSISTENCY: enumerated values
        # -----------------------------------------------------------------
        {
            "type": "expect_column_values_to_be_in_set",
            "kwargs": {
                "column": "pickup_period",
                "value_set": ["morning", "afternoon", "evening", "night"],
            },
            "meta": {"description": "Pickup period must be one of 4 enumerated buckets"},
        },
        {
            "type": "expect_column_values_to_be_in_set",
            "kwargs": {
                "column": "is_weekend",
                "value_set": [True, False, 0, 1, "true", "false"],
            },
            "meta": {"description": "is_weekend is a boolean — typed as bool or int post-Parquet"},
        },

        # -----------------------------------------------------------------
        # TEMPORAL CONSISTENCY: dates must be sensible
        # -----------------------------------------------------------------
        # This is the assertion that catches the "2002/2009 in 2024" outliers
        # we saw during the QuickSight phase and confirmed in this run.
        # GE v1.x parses datetime columns automatically — no parse_strings_as_datetimes flag.
        {
            "type": "expect_column_values_to_be_between",
            "kwargs": {
                "column": "tpep_pickup_datetime",
                "min_value": "2020-01-01T00:00:00",
                "max_value": "2030-12-31T23:59:59",
            },
            "meta": {
                "description": (
                    "Pickup dates must be in the modern era. "
                    "Catches outlier records with legacy 2002/2009 timestamps "
                    "(known NYC TLC dataset quirk: malformed upstream records)."
                )
            },
        },

        # -----------------------------------------------------------------
        # DATA VOLUME: sanity on row count
        # -----------------------------------------------------------------
        {
            "type": "expect_table_row_count_to_be_between",
            "kwargs": {
                "min_value": 1,           # at least one row
                "max_value": 50_000_000,  # max ~50M for safety
            },
            "meta": {
                "description": (
                    "Row count sanity check: batch must contain data, "
                    "and not exceed 50M rows (would indicate runaway load)."
                )
            },
        },
    ]


# ============================================
# RAW LAYER — minimal sanity checks
# ============================================


def get_raw_expectations() -> List[Dict]:
    """Minimal validations on raw layer — just verifies the ingest worked."""
    return [
        {
            "type": "expect_column_to_exist",
            "kwargs": {"column": "VendorID"},  # raw uses original NYC TLC casing
            "meta": {"description": "Raw layer preserves original NYC TLC schema"},
        },
        {
            "type": "expect_column_to_exist",
            "kwargs": {"column": "tpep_pickup_datetime"},
            "meta": {"description": "Pickup timestamp required even in raw"},
        },
        {
            "type": "expect_table_row_count_to_be_between",
            "kwargs": {"min_value": 1, "max_value": 50_000_000},
            "meta": {"description": "Raw batch must not be empty"},
        },
    ]