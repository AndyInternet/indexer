"""CLI entry point for the indexer."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from indexer.config import Config
from indexer.db import Database, FileRecord, RefRecord, SymbolRecord
from indexer.parsing.extractors import extract_references, extract_symbols
from indexer.parsing.languages import detect_language
from indexer.parsing.parser import parse_file
from indexer.scanner import detect_changes, scan_directory
from indexer.skeleton.extractor import extract_skeleton
from indexer.tokens import count_tokens


def _get_config(path: str | None = None) -> Config:
    root = Path(path).resolve() if path else Path.cwd()
    return Config(root=root)


def _get_db(config: Config) -> Database:
    db = Database(config.db_path)
    db.connect()
    return db


def _index_files(db: Database, config: Config, files_to_index, action: str = "Indexing") -> None:
    """Parse, extract symbols/refs/skeletons for a list of FileInfo objects."""
    total = len(files_to_index)
    for i, fi in enumerate(files_to_index, 1):
        click.echo(f"  [{i}/{total}] {action}: {fi.path}")

        lang = detect_language(fi.path)

        # Upsert file record
        file_rec = FileRecord(
            id=None,
            path=fi.path,
            content_hash=fi.content_hash,
            last_modified=fi.last_modified,
            language=lang,
            line_count=fi.line_count,
            byte_size=fi.byte_size,
        )
        file_id = db.upsert_file(file_rec)

        # Clear old symbols/refs for this file (for updates)
        db.delete_symbols_for_file(file_id)
        db.delete_refs_for_file(file_id)

        if lang is None:
            continue

        # Parse with tree-sitter
        abs_path = config.root / fi.path
        result = parse_file(abs_path)
        if result is None:
            continue

        # Extract symbols
        symbols = extract_symbols(result)
        if symbols:
            sym_records = []
            parent_ids: dict[str, int | None] = {}

            for sym in symbols:
                sr = SymbolRecord(
                    id=None,
                    name=sym.name,
                    kind=sym.kind,
                    file_id=file_id,
                    line_start=sym.line_start,
                    line_end=sym.line_end,
                    col_start=sym.col_start,
                    col_end=sym.col_end,
                    signature=sym.signature,
                    parent_symbol_id=None,
                )
                sym_records.append(sr)

            db.insert_symbols(sym_records)

        # Extract skeleton
        skeleton_text = extract_skeleton(result)
        if skeleton_text.strip():
            tok_count = count_tokens(skeleton_text)
            db.upsert_skeleton(file_id, skeleton_text, tok_count)

    db.connect().commit()


def _resolve_references(db: Database, config: Config, files_to_index) -> None:
    """Extract references now that all symbols are known."""
    known_symbols = db.get_all_symbol_names()
    if not known_symbols:
        return

    total = len(files_to_index)
    for i, fi in enumerate(files_to_index, 1):
        lang = detect_language(fi.path)
        if lang is None:
            continue

        abs_path = config.root / fi.path
        result = parse_file(abs_path)
        if result is None:
            continue

        frec = db.get_file(fi.path)
        if frec is None or frec.id is None:
            continue

        refs = extract_references(result, known_symbols)
        if refs:
            ref_records = [
                RefRecord(
                    id=None,
                    from_file_id=frec.id,
                    to_symbol_name=r.name,
                    line=r.line,
                    resolved_symbol_id=None,
                )
                for r in refs
            ]
            db.insert_refs(ref_records)

    db.connect().commit()


@click.group()
def main():
    """Indexer: AI-optimized codebase index generator."""
    pass


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def init(path: str):
    """Index a codebase and store in .indexer/index.db."""
    config = _get_config(path)
    db = _get_db(config)
    db.init_schema()

    click.echo(f"Scanning {config.root}...")
    files = list(scan_directory(config.root, config.ignore_patterns))
    click.echo(f"Found {len(files)} files.")

    if not files:
        click.echo("No files to index.")
        return

    # Filter to parseable files for symbol extraction, but store all
    parseable = [f for f in files if detect_language(f.path) is not None]
    non_parseable = [f for f in files if detect_language(f.path) is None]

    # Store non-parseable files (just metadata)
    for fi in non_parseable:
        db.upsert_file(FileRecord(
            id=None, path=fi.path, content_hash=fi.content_hash,
            last_modified=fi.last_modified, language=None,
            line_count=fi.line_count, byte_size=fi.byte_size,
        ))
    db.connect().commit()

    click.echo(f"Parsing {len(parseable)} source files...")
    _index_files(db, config, parseable)

    click.echo("Resolving cross-file references...")
    _resolve_references(db, config, parseable)

    stats = db.get_stats()
    click.echo(
        f"\nDone! Indexed {stats['files']} files, "
        f"{stats['symbols']} symbols, "
        f"{stats['refs']} references, "
        f"{stats['skeletons']} skeletons."
    )
    click.echo(f"Index stored at: {config.db_path}")
    db.close()


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def update(path: str):
    """Incrementally update the index for changed files."""
    config = _get_config(path)
    db = _get_db(config)

    if not config.db_path.exists():
        click.echo("No index found. Run 'indexer init' first.")
        sys.exit(1)

    click.echo("Scanning for changes...")
    files = list(scan_directory(config.root, config.ignore_patterns))
    existing_hashes = db.get_all_file_hashes()
    changes = detect_changes(existing_hashes, files)

    click.echo(
        f"Changes: {len(changes.added)} added, "
        f"{len(changes.modified)} modified, "
        f"{len(changes.deleted)} deleted, "
        f"{len(changes.unchanged)} unchanged."
    )

    # Delete removed files
    for p in changes.deleted:
        db.delete_file(p)
    db.connect().commit()

    # Index new and modified files
    to_index = changes.added + changes.modified
    if to_index:
        parseable = [f for f in to_index if detect_language(f.path) is not None]
        _index_files(db, config, parseable, action="Updating")
        _resolve_references(db, config, parseable)

    stats = db.get_stats()
    click.echo(
        f"Index updated: {stats['files']} files, "
        f"{stats['symbols']} symbols, "
        f"{stats['refs']} references."
    )
    db.close()


@main.command()
@click.argument("file", required=False)
@click.option("--path", "-p", default=".", type=click.Path(exists=True), help="Project root")
def skeleton(file: str | None, path: str):
    """Print skeleton of a file or entire repo."""
    config = _get_config(path)
    db = _get_db(config)

    if file:
        frec = db.get_file(file)
        if frec is None:
            click.echo(f"File not found in index: {file}")
            sys.exit(1)
        skel = db.get_skeleton(frec.id)  # type: ignore
        if skel:
            click.echo(skel)
        else:
            click.echo(f"No skeleton available for {file}")
    else:
        files = db.get_all_files()
        for frec in files:
            skel = db.get_skeleton(frec.id)  # type: ignore
            if skel:
                click.echo(f"# {frec.path}")
                click.echo(skel)
                click.echo()

    db.close()


@main.command("map")
@click.option("--tokens", "-t", default=4096, help="Token budget")
@click.option("--focus", "-f", multiple=True, help="Files to boost in ranking")
@click.option("--path", "-p", default=".", type=click.Path(exists=True), help="Project root")
def repo_map(tokens: int, focus: tuple[str, ...], path: str):
    """Print PageRank-based repo map within token budget."""
    from indexer.graph.builder import build_dependency_graph
    from indexer.graph.pagerank import compute_pagerank
    from indexer.graph.repomap import render_repo_map

    config = _get_config(path)
    db = _get_db(config)

    click.echo("Building dependency graph...", err=True)
    graph = build_dependency_graph(db)
    click.echo(f"Graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges", err=True)

    focus_list = list(focus) if focus else None
    scores = compute_pagerank(graph, personalize_files=focus_list)

    output = render_repo_map(db, scores, token_budget=tokens)
    click.echo(output)

    actual_tokens = count_tokens(output)
    click.echo(f"\n# Token usage: {actual_tokens}/{tokens}", err=True)
    db.close()


@main.command()
@click.argument("query")
@click.option("--path", "-p", default=".", type=click.Path(exists=True), help="Project root")
def search(query: str, path: str):
    """Search symbols by name."""
    config = _get_config(path)
    db = _get_db(config)

    results = db.search_symbols(query)
    if not results:
        click.echo(f"No symbols matching '{query}'")
        sys.exit(0)

    for sym, file_path in results:
        click.echo(f"  {sym.kind:10} {sym.name:30} {file_path}:{sym.line_start}")
        if sym.signature:
            click.echo(f"             {sym.signature}")

    click.echo(f"\n{len(results)} result(s)")
    db.close()


@main.command()
@click.argument("symbol")
@click.option("--path", "-p", default=".", type=click.Path(exists=True), help="Project root")
def refs(symbol: str, path: str):
    """Find all references to a symbol."""
    config = _get_config(path)
    db = _get_db(config)

    results = db.get_refs_to_symbol(symbol)
    if not results:
        click.echo(f"No references to '{symbol}'")
        sys.exit(0)

    for ref, file_path in results:
        click.echo(f"  {file_path}:{ref.line}")

    click.echo(f"\n{len(results)} reference(s)")
    db.close()


@main.command()
@click.argument("symbol")
@click.option("--path", "-p", default=".", type=click.Path(exists=True), help="Project root")
def callers(symbol: str, path: str):
    """Find all callers of a function."""
    config = _get_config(path)
    db = _get_db(config)

    results = db.get_refs_to_symbol(symbol)
    if not results:
        click.echo(f"No callers of '{symbol}'")
        sys.exit(0)

    # Group by file
    by_file: dict[str, list[int]] = {}
    for ref, file_path in results:
        by_file.setdefault(file_path, []).append(ref.line or 0)

    for file_path, lines in sorted(by_file.items()):
        line_str = ", ".join(str(ln) for ln in sorted(lines) if ln > 0)
        click.echo(f"  {file_path}: lines {line_str}")

    click.echo(f"\n{len(by_file)} file(s), {len(results)} reference(s)")
    db.close()


@main.command()
@click.argument("symbol")
@click.option("--path", "-p", default=".", type=click.Path(exists=True), help="Project root")
def impl(symbol: str, path: str):
    """Get full implementation of a specific symbol."""
    config = _get_config(path)
    db = _get_db(config)

    results = db.get_symbol_by_name(symbol)
    if not results:
        click.echo(f"Symbol '{symbol}' not found")
        sys.exit(1)

    for sym, file_path in results:
        abs_path = config.root / file_path
        try:
            lines = abs_path.read_text().splitlines()
        except OSError:
            click.echo(f"Cannot read {file_path}")
            continue

        click.echo(f"# {file_path}:{sym.line_start}-{sym.line_end}")
        for i in range(sym.line_start - 1, min(sym.line_end, len(lines))):
            click.echo(f"{i + 1:4d} | {lines[i]}")
        click.echo()

    db.close()


@main.command()
@click.option("--path", "-p", default=".", type=click.Path(exists=True), help="Project root")
def stats(path: str):
    """Show index statistics."""
    config = _get_config(path)

    if not config.db_path.exists():
        click.echo("No index found. Run 'indexer init' first.")
        sys.exit(1)

    db = _get_db(config)
    s = db.get_stats()

    click.echo(f"Index: {config.db_path}")
    click.echo(f"  Files:      {s['files']}")
    click.echo(f"  Symbols:    {s['symbols']}")
    click.echo(f"  References: {s['refs']}")
    click.echo(f"  Skeletons:  {s['skeletons']}")

    # Language breakdown
    conn = db.connect()
    rows = conn.execute(
        "SELECT language, COUNT(*) as cnt FROM files WHERE language IS NOT NULL GROUP BY language ORDER BY cnt DESC"
    ).fetchall()
    if rows:
        click.echo("\n  Languages:")
        for r in rows:
            click.echo(f"    {r['language']:15} {r['cnt']:5d} files")

    db.close()


if __name__ == "__main__":
    main()
