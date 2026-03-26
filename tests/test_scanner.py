"""Tests for scanner with allow-list support."""

from __future__ import annotations

from pathlib import Path

from indexer.scanner import _should_descend, scan_directory


# -- _should_descend tests --


def test_should_descend_direct_parent():
    """vendor is a parent of vendor/my-lib/**, so descend."""
    assert _should_descend("vendor", ["vendor/my-lib/**"]) is True


def test_should_descend_exact_match():
    """vendor/my-lib matches vendor/my-lib/**."""
    assert _should_descend("vendor/my-lib", ["vendor/my-lib/**"]) is True


def test_should_descend_sibling_rejected():
    """vendor/other is NOT a prefix of vendor/my-lib/**."""
    assert _should_descend("vendor/other", ["vendor/my-lib/**"]) is False


def test_should_descend_deeper_sibling():
    """vendor/other/deep should not match vendor/my-lib/**."""
    assert _should_descend("vendor/other/deep", ["vendor/my-lib/**"]) is False


def test_should_descend_double_star_prefix():
    """**/foo matches any directory because ** can match any depth."""
    assert _should_descend("anything", ["**/foo/*.py"]) is True
    assert _should_descend("deep/nested", ["**/foo/*.py"]) is True


def test_should_descend_no_patterns():
    """Empty allow list never matches."""
    assert _should_descend("vendor", []) is False


def test_should_descend_glob_in_segment():
    """Glob character in a pattern segment is treated as 'could match'."""
    assert _should_descend("vendor", ["vendor/*/src/**"]) is True
    assert _should_descend("vendor/anything", ["vendor/*/src/**"]) is True


def test_should_descend_nested_path():
    """Multi-level descend: node_modules/@scope/pkg."""
    patterns = ["node_modules/@scope/pkg/**"]
    assert _should_descend("node_modules", patterns) is True
    assert _should_descend("node_modules/@scope", patterns) is True
    assert _should_descend("node_modules/@scope/pkg", patterns) is True
    assert _should_descend("node_modules/@scope/other", patterns) is False


# -- Full scan integration tests --


def _make_tree(root: Path, paths: list[str]) -> None:
    """Create files at the given relative paths."""
    for p in paths:
        full = root / p
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(f"content of {p}")


def test_scan_ignores_vendor_by_default(tmp_path: Path):
    _make_tree(
        tmp_path,
        [
            "main.py",
            "vendor/lib/a.py",
        ],
    )
    files = list(scan_directory(tmp_path, ["vendor"]))
    paths = {f.path for f in files}
    assert "main.py" in paths
    assert "vendor/lib/a.py" not in paths


def test_scan_allow_overrides_ignore(tmp_path: Path):
    """Allow list re-includes a subdirectory inside an ignored directory."""
    _make_tree(
        tmp_path,
        [
            "main.py",
            "vendor/my-lib/a.py",
            "vendor/other/b.py",
        ],
    )
    files = list(
        scan_directory(
            tmp_path,
            ignore_patterns=["vendor"],
            allow_patterns=["vendor/my-lib/**"],
        )
    )
    paths = {f.path for f in files}
    assert "main.py" in paths
    assert "vendor/my-lib/a.py" in paths
    assert "vendor/other/b.py" not in paths


def test_scan_allow_specific_file(tmp_path: Path):
    """Allow a single file inside an ignored directory."""
    _make_tree(
        tmp_path,
        [
            "vendor/important.go",
            "vendor/other.go",
        ],
    )
    files = list(
        scan_directory(
            tmp_path,
            ignore_patterns=["vendor"],
            allow_patterns=["vendor/important.go"],
        )
    )
    paths = {f.path for f in files}
    assert "vendor/important.go" in paths
    assert "vendor/other.go" not in paths


def test_scan_allow_deep_nested(tmp_path: Path):
    """Allow works for deeply nested paths in ignored directories."""
    _make_tree(
        tmp_path,
        [
            "node_modules/@scope/pkg/index.js",
            "node_modules/@scope/other/index.js",
            "node_modules/random/index.js",
        ],
    )
    files = list(
        scan_directory(
            tmp_path,
            ignore_patterns=["node_modules"],
            allow_patterns=["node_modules/@scope/pkg/**"],
        )
    )
    paths = {f.path for f in files}
    assert "node_modules/@scope/pkg/index.js" in paths
    assert "node_modules/@scope/other/index.js" not in paths
    assert "node_modules/random/index.js" not in paths


def test_scan_no_allow_patterns(tmp_path: Path):
    """When allow_patterns is None, behaves like before."""
    _make_tree(tmp_path, ["main.py", "vendor/a.py"])
    files = list(scan_directory(tmp_path, ["vendor"], allow_patterns=None))
    paths = {f.path for f in files}
    assert "main.py" in paths
    assert "vendor/a.py" not in paths


def test_scan_allow_with_glob_extension(tmp_path: Path):
    """Allow only .go files inside vendor."""
    _make_tree(
        tmp_path,
        [
            "vendor/lib/a.go",
            "vendor/lib/b.py",
        ],
    )
    files = list(
        scan_directory(
            tmp_path,
            ignore_patterns=["vendor"],
            allow_patterns=["vendor/**/*.go"],
        )
    )
    paths = {f.path for f in files}
    assert "vendor/lib/a.go" in paths
    assert "vendor/lib/b.py" not in paths
