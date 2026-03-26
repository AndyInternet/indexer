"""Integration tests for the CLI using Click's CliRunner."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from indexer.cli import main


def _init_project(runner: CliRunner, project_path: str) -> None:
    """Helper to initialize an index for a project."""
    result = runner.invoke(main, ["init", project_path])
    assert result.exit_code == 0, result.output


def test_init_creates_index(tmp_project: Path):
    """init creates .indexer/index.db."""
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(tmp_project)])
    assert result.exit_code == 0
    assert (tmp_project / ".indexer" / "index.db").exists()


def test_init_reports_stats(tmp_project: Path):
    """init output contains file and symbol counts."""
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(tmp_project)])
    assert "files" in result.output.lower()
    assert "symbols" in result.output.lower()


def test_update_no_changes(tmp_project: Path):
    """update after init with no file changes reports 0 changes."""
    runner = CliRunner()
    _init_project(runner, str(tmp_project))
    result = runner.invoke(main, ["update", str(tmp_project)])
    assert result.exit_code == 0
    assert "0 added" in result.output


def test_update_detects_new_file(tmp_project: Path):
    """Adding a file and running update detects it."""
    runner = CliRunner()
    _init_project(runner, str(tmp_project))
    (tmp_project / "new_module.py").write_text("def new_func(): pass\n")
    result = runner.invoke(main, ["update", str(tmp_project)])
    assert result.exit_code == 0
    assert "1 added" in result.output


def test_stats_output(tmp_project: Path):
    """stats shows all count categories."""
    runner = CliRunner()
    _init_project(runner, str(tmp_project))
    result = runner.invoke(main, ["stats", "--path", str(tmp_project)])
    assert result.exit_code == 0
    assert "Files:" in result.output
    assert "Symbols:" in result.output
    assert "References:" in result.output
    assert "Skeletons:" in result.output


def test_search_finds_symbol(tmp_project: Path):
    """search finds a known symbol."""
    runner = CliRunner()
    _init_project(runner, str(tmp_project))
    result = runner.invoke(main, ["search", "Greeter", "--path", str(tmp_project)])
    assert result.exit_code == 0
    assert "Greeter" in result.output


def test_search_no_results(tmp_project: Path):
    """search for nonexistent symbol reports nothing."""
    runner = CliRunner()
    _init_project(runner, str(tmp_project))
    result = runner.invoke(
        main, ["search", "zzz_nonexistent", "--path", str(tmp_project)]
    )
    assert "No symbols matching" in result.output


def test_impl_shows_source(tmp_project: Path):
    """impl prints source lines of a symbol."""
    runner = CliRunner()
    _init_project(runner, str(tmp_project))
    result = runner.invoke(main, ["impl", "helper", "--path", str(tmp_project)])
    assert result.exit_code == 0
    assert "def helper" in result.output or "helper" in result.output


def test_skeleton_single_file(tmp_project: Path):
    """skeleton for a single file shows its skeleton."""
    runner = CliRunner()
    _init_project(runner, str(tmp_project))
    result = runner.invoke(main, ["skeleton", "main.py", "--path", str(tmp_project)])
    assert result.exit_code == 0
    assert "class Greeter" in result.output or "def helper" in result.output


def test_map_produces_output(tmp_project: Path):
    """map produces non-empty output."""
    runner = CliRunner()
    _init_project(runner, str(tmp_project))
    result = runner.invoke(
        main, ["map", "--tokens", "2048", "--path", str(tmp_project)]
    )
    assert result.exit_code == 0
    assert len(result.output.strip()) > 0


def test_find_by_pattern(tmp_project: Path):
    """find locates files matching a glob."""
    runner = CliRunner()
    _init_project(runner, str(tmp_project))
    result = runner.invoke(main, ["find", "*.py", "--path", str(tmp_project)])
    assert result.exit_code == 0
    assert "main.py" in result.output


def test_tree_output(tmp_project: Path):
    """tree shows directory structure."""
    runner = CliRunner()
    _init_project(runner, str(tmp_project))
    result = runner.invoke(main, ["tree", "--path", str(tmp_project)])
    assert result.exit_code == 0
    assert "main.py" in result.output


def test_grep_finds_pattern(tmp_project: Path):
    """grep finds text matches."""
    runner = CliRunner()
    _init_project(runner, str(tmp_project))
    result = runner.invoke(main, ["grep", "class", "--path", str(tmp_project)])
    assert result.exit_code == 0
    assert "class" in result.output.lower()


def test_config_show(tmp_project: Path):
    """config show prints JSON."""
    runner = CliRunner()
    _init_project(runner, str(tmp_project))
    result = runner.invoke(main, ["config", "show", "--path", str(tmp_project)])
    assert result.exit_code == 0
    assert "ignore" in result.output


def test_config_ignore_and_remove(tmp_project: Path):
    """config ignore adds a pattern, config remove removes it."""
    runner = CliRunner()
    _init_project(runner, str(tmp_project))

    result = runner.invoke(
        main, ["config", "ignore", "*.log", "--path", str(tmp_project)]
    )
    assert result.exit_code == 0
    assert "Added to ignore" in result.output

    result = runner.invoke(
        main, ["config", "remove", "*.log", "--path", str(tmp_project)]
    )
    assert result.exit_code == 0
    assert "Removed from ignore" in result.output
