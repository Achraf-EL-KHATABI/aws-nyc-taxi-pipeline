"""
Shared pytest fixtures and configuration.

This file is auto-discovered by pytest and applies to all tests in this directory.
"""
import pytest


@pytest.fixture
def aws_region():
    """Default AWS region for tests."""
    return "eu-west-3"


@pytest.fixture
def raw_bucket():
    """Test raw bucket name."""
    return "nyc-taxi-pipeline-raw-test"


@pytest.fixture
def sample_taxi_data():
    """Sample valid taxi trip record (matching NYC TLC schema)."""
    return {
        "vendorid": 2,
        "tpep_pickup_datetime": "2024-01-15T08:30:00",
        "tpep_dropoff_datetime": "2024-01-15T08:55:00",
        "passenger_count": 1,
        "trip_distance": 2.5,
        "fare_amount": 12.50,
        "tip_amount": 2.00,
        "total_amount": 15.30,
    }