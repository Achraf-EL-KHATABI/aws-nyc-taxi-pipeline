"""
Unit tests for scripts/upload_to_s3.py

Tests cover pure functions (no I/O) and the CLI argument parser.
Download/upload functions involve I/O and are tested with mocks.
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts/ to path so we can import upload_to_s3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from upload_to_s3 import (  # noqa: E402
    build_filename,
    download_file,
    ingest,
    parse_args,
    upload_to_s3,
)


# ============================================
# build_filename — pure function tests
# ============================================
class TestBuildFilename:
    """The official NYC TLC filename pattern: <taxi_type>_tripdata_<year>-<MM>.parquet"""

    def test_yellow_january_2024(self):
        assert build_filename("yellow", 2024, 1) == "yellow_tripdata_2024-01.parquet"

    def test_green_december_2023(self):
        assert build_filename("green", 2023, 12) == "green_tripdata_2023-12.parquet"

    def test_single_digit_month_is_zero_padded(self):
        result = build_filename("yellow", 2024, 3)
        assert "2024-03" in result
        assert "2024-3" not in result  # ensure no unpadded version

    def test_all_taxi_types_supported(self):
        for taxi_type in ["yellow", "green", "fhv", "fhvhv"]:
            result = build_filename(taxi_type, 2024, 1)
            assert result.startswith(taxi_type)
            assert result.endswith(".parquet")


# ============================================
# parse_args — CLI argument tests
# ============================================
class TestParseArgs:
    def test_valid_minimal_args(self):
        test_args = ["upload_to_s3.py", "--year", "2024", "--months", "1"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
        assert args.year == 2024
        assert args.months == [1]
        assert args.taxi_type == "yellow"  # default

    def test_multiple_months(self):
        test_args = ["upload_to_s3.py", "--year", "2024", "--months", "1", "2", "3"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
        assert args.months == [1, 2, 3]

    def test_custom_taxi_type(self):
        test_args = [
            "upload_to_s3.py",
            "--taxi-type", "green",
            "--year", "2024",
            "--months", "1",
        ]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
        assert args.taxi_type == "green"

    def test_invalid_taxi_type_rejected(self):
        test_args = [
            "upload_to_s3.py",
            "--taxi-type", "purple",  # not in choices
            "--year", "2024",
            "--months", "1",
        ]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit):
                parse_args()

    def test_missing_required_args_rejected(self):
        test_args = ["upload_to_s3.py", "--year", "2024"]  # missing --months
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit):
                parse_args()


# ============================================
# download_file — tests with mocked HTTP
# ============================================
class TestDownloadFile:
    def test_skip_if_already_downloaded(self, tmp_path):
        """If the destination file already exists, do not re-download."""
        dest = tmp_path / "existing.parquet"
        dest.write_bytes(b"existing data")

        with patch("upload_to_s3.requests.get") as mock_get:
            result = download_file("https://fake.url/file.parquet", dest)

        assert result is True
        mock_get.assert_not_called()  # no HTTP call should be made

    @patch("upload_to_s3.requests.get")
    def test_download_success(self, mock_get, tmp_path):
        """Successful HTTP response should write the file and return True."""
        # Mock response with iterable chunks
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "13"}
        mock_response.iter_content.return_value = [b"hello world!\n"]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        dest = tmp_path / "new.parquet"
        result = download_file("https://fake.url/file.parquet", dest)

        assert result is True
        assert dest.exists()
        assert dest.read_bytes() == b"hello world!\n"

    @patch("upload_to_s3.requests.get")
    def test_download_failure_cleans_up(self, mock_get, tmp_path):
        """A network error should clean up any partial file and return False."""
        import requests as _requests
        mock_get.side_effect = _requests.RequestException("Network error")

        dest = tmp_path / "failed.parquet"
        result = download_file("https://fake.url/file.parquet", dest)

        assert result is False
        assert not dest.exists()


# ============================================
# upload_to_s3 — tests with mocked boto3 client
# ============================================
class TestUploadToS3:
    def test_upload_success(self, tmp_path):
        """A successful upload should call S3 client and return True."""
        # Create a local file to "upload"
        local = tmp_path / "data.parquet"
        local.write_bytes(b"fake parquet data")

        mock_s3 = MagicMock()
        # upload_file calls the Callback to update progress
        mock_s3.upload_file.side_effect = lambda *a, **kw: kw["Callback"](len(b"fake parquet data"))

        result = upload_to_s3(mock_s3, local, "my-bucket", "key/path.parquet")

        assert result is True
        mock_s3.upload_file.assert_called_once()
        call_args = mock_s3.upload_file.call_args
        assert call_args[0][1] == "my-bucket"
        assert call_args[0][2] == "key/path.parquet"

    def test_upload_failure_returns_false(self, tmp_path):
        """Boto3 ClientError should be caught and return False."""
        from botocore.exceptions import ClientError

        local = tmp_path / "data.parquet"
        local.write_bytes(b"x" * 100)

        mock_s3 = MagicMock()
        mock_s3.upload_file.side_effect = ClientError(
            error_response={"Error": {"Code": "AccessDenied", "Message": "Denied"}},
            operation_name="PutObject",
        )

        result = upload_to_s3(mock_s3, local, "my-bucket", "key.parquet")
        assert result is False


# ============================================
# ingest — integration with mocked downstream
# ============================================
class TestIngest:
    @patch("upload_to_s3.upload_to_s3", return_value=True)
    @patch("upload_to_s3.download_file", return_value=True)
    def test_full_pipeline_success(self, mock_download, mock_upload):
        """ingest() should call download then upload and return True on success."""
        mock_s3 = MagicMock()
        result = ingest("yellow", 2024, 1, "raw-bucket", mock_s3)

        assert result is True
        mock_download.assert_called_once()
        mock_upload.assert_called_once()

        # Verify Hive partitioning in the S3 key
        upload_call_args = mock_upload.call_args[0]
        # signature: upload_to_s3(s3_client, local_path, bucket, s3_key)
        s3_key = upload_call_args[3]
        assert "taxi_type=yellow" in s3_key
        assert "year=2024" in s3_key
        assert "month=01" in s3_key

    @patch("upload_to_s3.download_file", return_value=False)
    def test_download_failure_skips_upload(self, mock_download):
        """If download fails, upload should not be attempted."""
        mock_s3 = MagicMock()
        with patch("upload_to_s3.upload_to_s3") as mock_upload:
            result = ingest("yellow", 2024, 1, "raw-bucket", mock_s3)

        assert result is False
        mock_upload.assert_not_called()