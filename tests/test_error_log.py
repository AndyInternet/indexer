"""Tests for automatic error logging."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from indexer.config import ERROR_LOG_NAME, INDEXER_DIR
from indexer.error_log import ErrorLoggingGroup

# Re-enable real error logging for all tests in this module.
pytestmark = pytest.mark.usefixtures("enable_error_log")


def _make_failing_cli() -> click.Group:
    """Create a minimal CLI with a command that always raises."""

    @click.group(cls=ErrorLoggingGroup)
    def cli():
        pass

    @cli.command()
    @click.option("--path", "-p", default=".")
    def boom(path: str):
        """A command that always fails."""
        raise RuntimeError("something broke")

    return cli


def test_error_logged_on_command_failure(tmp_path: Path):
    """An unhandled exception in a command is logged to errors.log."""
    runner = CliRunner()
    cli = _make_failing_cli()

    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        result = runner.invoke(cli, ["boom"])
        assert result.exit_code != 0

        log_path = Path(td) / INDEXER_DIR / ERROR_LOG_NAME
        assert log_path.exists()

        line = log_path.read_text().strip()
        entry = json.loads(line)
        assert entry["error_type"] == "RuntimeError"
        assert entry["error_message"] == "something broke"
        assert "timestamp" in entry
        assert "traceback" in entry
        assert "RuntimeError" in entry["traceback"]


def test_indexer_dir_created_if_missing(tmp_path: Path):
    """.indexer/ is created when it doesn't exist yet."""
    runner = CliRunner()
    cli = _make_failing_cli()

    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        indexer_dir = Path(td) / INDEXER_DIR
        assert not indexer_dir.exists()

        runner.invoke(cli, ["boom"])
        assert indexer_dir.exists()
        assert (indexer_dir / ERROR_LOG_NAME).exists()


def test_multiple_errors_append(tmp_path: Path):
    """Successive errors produce multiple JSONL lines."""
    runner = CliRunner()
    cli = _make_failing_cli()

    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        runner.invoke(cli, ["boom"])
        runner.invoke(cli, ["boom"])

        log_path = Path(td) / INDEXER_DIR / ERROR_LOG_NAME
        lines = [ln for ln in log_path.read_text().splitlines() if ln.strip()]
        assert len(lines) == 2
        for line in lines:
            entry = json.loads(line)
            assert entry["error_type"] == "RuntimeError"


def test_logging_failure_does_not_mask_original_error(tmp_path: Path):
    """If logging itself fails, the original error still propagates."""
    runner = CliRunner()
    cli = _make_failing_cli()

    with patch("builtins.open", side_effect=PermissionError("denied")):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["boom"])
            # Original error should still propagate (non-zero exit)
            assert result.exit_code != 0


def test_log_error_uses_path_option(tmp_path: Path):
    """log_error resolves .indexer dir from the --path option."""
    project = tmp_path / "myproject"
    project.mkdir()

    runner = CliRunner()
    cli = _make_failing_cli()

    result = runner.invoke(cli, ["boom", "--path", str(project)])
    assert result.exit_code != 0

    log_path = project / INDEXER_DIR / ERROR_LOG_NAME
    assert log_path.exists()
    entry = json.loads(log_path.read_text().strip())
    assert entry["command"] == "boom"


def test_log_entry_fields(tmp_path: Path):
    """All expected fields are present and have correct types."""
    runner = CliRunner()
    cli = _make_failing_cli()

    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        runner.invoke(cli, ["boom"])

        log_path = Path(td) / INDEXER_DIR / ERROR_LOG_NAME
        entry = json.loads(log_path.read_text().strip())

        assert isinstance(entry["timestamp"], str)
        assert isinstance(entry["command"], str)
        assert isinstance(entry["args"], list)
        assert isinstance(entry["error_type"], str)
        assert isinstance(entry["error_message"], str)
        assert isinstance(entry["traceback"], str)
