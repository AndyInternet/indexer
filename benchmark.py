#!/usr/bin/env python3
"""Benchmark indexer vs traditional tools using a real Claude agent.

Runs concrete code navigation tasks in two modes:
  - "indexer": agent has access to indexer commands
  - "baseline": agent can only use grep/find/cat/head/ls

Measures total tokens consumed, tool call count, and answer correctness.

Usage:
    # Run full benchmark (costs API tokens)
    uv run --extra bench python benchmark.py /path/to/project

    # Preview tasks without running agents
    uv run --extra bench python benchmark.py /path/to/project --dry-run

    # Use a specific model
    uv run --extra bench python benchmark.py /path/to/project --model claude-sonnet-4-20250514

    # JSON output
    uv run --extra bench python benchmark.py /path/to/project --json

Requires: ANTHROPIC_API_KEY environment variable.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Task definitions
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """A concrete navigation task with verifiable ground truth."""
    name: str
    question: str
    expected: list[str]  # strings that should appear in a correct answer
    category: str  # symbol_lookup, caller_trace, file_understanding, text_search, file_discovery
    min_matches: int | None = None  # override: how many expected must match (default: half)


@dataclass
class RunResult:
    """Result of running one task in one mode."""
    task_name: str
    mode: str  # "indexer" or "baseline"
    input_tokens: int
    output_tokens: int
    tool_calls: int
    turns: int
    answer: str
    correct: bool
    elapsed_sec: float


@dataclass
class Comparison:
    """Side-by-side comparison of indexer vs baseline for one task."""
    task: Task
    indexer: RunResult
    baseline: RunResult

    @property
    def token_savings_pct(self) -> float:
        base_total = self.baseline.input_tokens + self.baseline.output_tokens
        idx_total = self.indexer.input_tokens + self.indexer.output_tokens
        if base_total == 0:
            return 0.0
        return (1 - idx_total / base_total) * 100


# ---------------------------------------------------------------------------
# Task generation — introspects the index for ground truth
# ---------------------------------------------------------------------------

def run_cmd(cmd: str, cwd: Path, timeout: int = 30) -> str:
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=cwd,
        )
        return proc.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def _parse_search_paths(search_output: str) -> list[str]:
    """Extract file paths from `indexer search` output."""
    paths = []
    for line in search_output.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(("─", "Found")):
            for part in stripped.split():
                if "/" in part and (":" in part or "." in part.split("/")[-1]):
                    paths.append(part.split(":")[0])
    return paths


def _parse_caller_paths(callers_output: str) -> list[str]:
    """Extract file paths from `indexer callers` output."""
    paths = []
    for line in callers_output.splitlines():
        stripped = line.strip()
        if stripped and "/" in stripped and ": " in stripped:
            paths.append(stripped.split(":")[0])
    return paths


def _parse_grep_paths(grep_output: str) -> list[str]:
    """Extract file paths from `indexer grep` output."""
    paths = []
    for line in grep_output.splitlines():
        stripped = line.strip()
        if stripped and "[rank:" in stripped:
            path = stripped.split("[")[0].strip()
            if "/" in path:
                paths.append(path)
    return paths


def _parse_find_paths(find_output: str) -> list[str]:
    """Extract file paths from `indexer find` output (files only, not directories)."""
    paths = []
    for line in find_output.splitlines():
        stripped = line.strip()
        if stripped and "/" in stripped and not stripped.startswith(("No ", "Found")) and "result" not in stripped:
            # Skip directories (end with /)
            if stripped.endswith("/"):
                continue
            paths.append(stripped)
    return paths


def _query_top_symbols(project: Path, limit: int = 20) -> list[tuple[str, int]]:
    """Query the index DB directly for the most-referenced symbol names."""
    import sqlite3

    db_path = project / ".indexer" / "index.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT r.to_symbol_name AS name, COUNT(*) AS ref_count
           FROM refs r
           GROUP BY r.to_symbol_name
           HAVING LENGTH(r.to_symbol_name) > 2 AND LENGTH(r.to_symbol_name) <= 40
           ORDER BY ref_count DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [(r["name"], r["ref_count"]) for r in rows]


def _query_top_file(project: Path) -> str | None:
    """Get the highest-ranked file from the repo map."""
    map_out = run_cmd("indexer map --tokens 512", project)
    for line in map_out.splitlines():
        stripped = line.strip()
        if stripped and stripped.endswith(":") and "/" in stripped:
            return stripped.rstrip(":")
    return None


def _query_file_with_most_symbols(project: Path, min_line_count: int = 100) -> str | None:
    """Find a file with many symbols and enough lines for skeleton to shine."""
    import sqlite3

    db_path = project / ".indexer" / "index.db"
    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT f.path, COUNT(s.id) AS sym_count, f.line_count
           FROM files f
           JOIN symbols s ON s.file_id = f.id
           WHERE f.line_count >= ?
             AND f.path NOT LIKE '%%.pb.go'
             AND f.path NOT LIKE '%%_generated%%'
             AND f.path NOT LIKE '%%_grpc.pb.go'
             AND f.path NOT LIKE '%%.gen.%%'
             AND f.path NOT LIKE '%%/proto/%%'
             AND f.path NOT LIKE '%%/generated/%%'
           GROUP BY f.id
           ORDER BY sym_count DESC
           LIMIT 1""",
        (min_line_count,),
    ).fetchall()
    conn.close()
    return rows[0]["path"] if rows else None


def _query_file_symbols(project: Path, filepath: str) -> list[str]:
    """Get symbol names defined in a file via indexer search output."""
    import sqlite3

    db_path = project / ".indexer" / "index.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT s.name FROM symbols s
           JOIN files f ON s.file_id = f.id
           WHERE f.path = ? AND LENGTH(s.name) > 2
           ORDER BY s.line_start""",
        (filepath,),
    ).fetchall()
    conn.close()
    return [r["name"] for r in rows]


def _query_common_substring(project: Path) -> str | None:
    """Find a filename substring shared by multiple files (for file_discovery task)."""
    import sqlite3

    db_path = project / ".indexer" / "index.db"
    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))
    # Get all filenames, find a common word that appears in 3+ files
    rows = conn.execute("SELECT path FROM files").fetchall()
    conn.close()

    from collections import Counter
    word_counts: Counter[str] = Counter()
    for (path,) in rows:
        name = Path(path).stem.lower()
        # Split on common separators
        for part in name.replace("-", "_").replace(".", "_").split("_"):
            if len(part) >= 3:
                word_counts[part] += 1

    # Pick the most common word that appears in 3+ files but not all files
    total_files = len(rows)
    for word, count in word_counts.most_common():
        if 3 <= count <= total_files * 0.5:
            return word
    return None


def _query_grep_term(project: Path) -> str | None:
    """Find a content search term that hits multiple files from the top symbols."""
    import sqlite3

    db_path = project / ".indexer" / "index.db"
    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Pick the most-referenced symbol name — it's likely to appear in many files as text too
    rows = conn.execute(
        """SELECT r.to_symbol_name AS name, COUNT(DISTINCT r.from_file_id) AS file_count
           FROM refs r
           GROUP BY r.to_symbol_name
           HAVING file_count >= 3 AND LENGTH(r.to_symbol_name) BETWEEN 4 AND 20
           ORDER BY file_count DESC
           LIMIT 5""",
    ).fetchall()
    conn.close()
    return rows[0]["name"] if rows else None


def generate_tasks(project: Path) -> list[Task]:
    """Generate benchmark tasks by introspecting the project's index."""
    tasks: list[Task] = []

    # Ensure index exists
    stats = run_cmd("indexer stats", project)
    if "No index" in stats:
        print("Building index...")
        run_cmd("indexer init .", project)

    # Get the top symbols by reference count — these are the most central to the codebase
    top_symbols = _query_top_symbols(project)
    if not top_symbols:
        print("Error: no symbols found in index", file=sys.stderr)
        sys.exit(1)

    print(f"  Top symbols by reference count: {', '.join(f'{s}({c})' for s, c in top_symbols[:5])}")

    # Pick the highest-ranked file
    target_file = _query_top_file(project)
    if not target_file:
        print("Error: could not identify a target file from indexer map", file=sys.stderr)
        sys.exit(1)

    # --- Task 1: Symbol lookup ---
    # Use the most-referenced symbol
    for sym_name, _ in top_symbols:
        out = run_cmd(f"indexer search {sym_name}", project)
        if out and "No matches" not in out:
            expected = list(dict.fromkeys(_parse_search_paths(out)))  # dedupe
            if expected:
                tasks.append(Task(
                    name=f"symbol_lookup:{sym_name}",
                    question=f"Find where the function or method `{sym_name}` is defined in this codebase. Give me the exact file path and line number.",
                    expected=expected[:3],
                    category="symbol_lookup",
                ))
                break

    # --- Task 2: Caller trace ---
    # Find a symbol with multiple callers
    for sym_name, ref_count in top_symbols:
        if ref_count < 2:
            continue
        out = run_cmd(f"indexer callers {sym_name}", project)
        if out and "No callers" not in out and "No matches" not in out:
            caller_files = _parse_caller_paths(out)
            if len(caller_files) >= 2:
                tasks.append(Task(
                    name=f"caller_trace:{sym_name}",
                    question=f"List all files that call or invoke `{sym_name}`. Just the file paths.",
                    expected=caller_files[:5],
                    category="caller_trace",
                ))
                break

    # --- Task 3: File understanding ---
    # Pick a large file with many symbols — this is where skeleton >> cat
    structure_file = _query_file_with_most_symbols(project) or target_file
    file_symbols = _query_file_symbols(project, structure_file)
    if file_symbols:
        tasks.append(Task(
            name=f"file_structure:{Path(structure_file).name}",
            question=f"What are the main functions, methods, or classes defined in `{structure_file}`? List their names.",
            expected=file_symbols[:8],
            category="file_understanding",
        ))

    # --- Task 4: Text search ---
    # Many files may match; give a large expected set and require just 1 hit
    grep_term = _query_grep_term(project)
    if grep_term:
        out = run_cmd(f'indexer grep "{grep_term}" --max-results 50', project)
        if out:
            grep_files = _parse_grep_paths(out)
            if len(grep_files) >= 2:
                tasks.append(Task(
                    name=f"text_search:{grep_term}",
                    question=f'Find all files containing "{grep_term}". List the file paths.',
                    expected=grep_files[:20],
                    category="text_search",
                    min_matches=1,
                ))

    # --- Task 5: File discovery ---
    # Many files may match; give a large expected set and require just 1 hit
    find_term = _query_common_substring(project)
    if find_term:
        out = run_cmd(f'indexer find "{find_term}"', project)
        if out and "No matches" not in out:
            find_files = _parse_find_paths(out)
            if find_files:
                tasks.append(Task(
                    name=f"file_discovery:{find_term}",
                    question=f'Find all files with "{find_term}" in their name. List the file paths.',
                    expected=find_files[:30],
                    category="file_discovery",
                    min_matches=1,
                ))

    return tasks


# ---------------------------------------------------------------------------
# Agent runner — sends tasks to Claude with tool use
# ---------------------------------------------------------------------------

BASH_TOOL = {
    "name": "bash",
    "description": "Execute a bash command and return its stdout/stderr.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute.",
            },
        },
        "required": ["command"],
    },
}

INDEXER_SYSTEM = """\
You are a code navigation assistant. Answer the user's question about the codebase at {root}.

You have a bash tool. Use `indexer` commands for navigation:
  indexer search <name>     — find symbol definitions
  indexer callers <symbol>  — find who calls a symbol
  indexer refs <symbol>     — find all references
  indexer skeleton <file>   — show file structure (signatures only)
  indexer impl <symbol>     — show full source of a symbol
  indexer map --tokens 2048 — ranked repo overview
  indexer grep <pattern>    — full-text search ranked by importance
  indexer find <pattern>    — find files by name
  indexer tree [path]       — directory tree

Be concise. Give the answer directly once you have it. Do not over-explore.\
"""

BASELINE_SYSTEM = """\
You are a code navigation assistant. Answer the user's question about the codebase at {root}.

You have a bash tool. You may use: grep, find, cat, head, tail, ls, wc.
Do NOT use any `indexer` commands — they are not available.

Be concise. Give the answer directly once you have it. Do not over-explore.\
"""

MAX_TURNS = 15


def execute_bash(command: str, cwd: Path) -> str:
    """Execute a bash command with safety limits."""
    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=30, cwd=cwd,
        )
        output = proc.stdout + proc.stderr
        # Truncate very long output to avoid blowing up context
        if len(output) > 20_000:
            output = output[:20_000] + f"\n... (truncated, {len(output)} chars total)"
        return output
    except subprocess.TimeoutExpired:
        return "(command timed out after 30s)"


def run_agent(
    task: Task,
    mode: str,
    project: Path,
    model: str,
) -> RunResult:
    """Run a single task with Claude in the given mode."""
    import anthropic

    client = anthropic.Anthropic()

    system = (INDEXER_SYSTEM if mode == "indexer" else BASELINE_SYSTEM).format(
        root=project,
    )

    messages = [{"role": "user", "content": task.question}]
    total_input = 0
    total_output = 0
    tool_calls = 0
    turns = 0
    start = time.time()

    while turns < MAX_TURNS:
        turns += 1
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system,
            tools=[BASH_TOOL],
            messages=messages,
        )

        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens

        # Collect all text and tool_use blocks
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        # If stop reason is "end_turn" — agent is done
        if response.stop_reason == "end_turn":
            break

        # Process tool calls
        tool_results = []
        for block in assistant_content:
            if block.type == "tool_use":
                tool_calls += 1
                cmd = block.input.get("command", "")

                # In baseline mode, block indexer commands
                if mode == "baseline" and cmd.strip().startswith("indexer"):
                    output = "Error: indexer is not available in this mode."
                else:
                    output = execute_bash(cmd, project)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output or "(no output)",
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    elapsed = time.time() - start

    # Extract final answer text
    answer_parts = []
    for block in messages[-1].get("content", []) if isinstance(messages[-1], dict) else messages[-1]["content"]:
        if hasattr(block, "text"):
            answer_parts.append(block.text)
        elif isinstance(block, dict) and block.get("type") == "text":
            answer_parts.append(block["text"])
    answer = "\n".join(answer_parts)

    # If the last message was a tool result, pull text from the assistant message before it
    if not answer:
        for msg in reversed(messages):
            content = msg.get("content", []) if isinstance(msg, dict) else msg["content"]
            for block in (content if isinstance(content, list) else [content]):
                if hasattr(block, "text"):
                    answer = block.text
                    break
                elif isinstance(block, dict) and block.get("type") == "text":
                    answer = block["text"]
                    break
            if answer:
                break

    # Check correctness: majority of expected strings should appear in the answer.
    # Match on both full path and filename to handle relative/absolute differences.
    answer_lower = answer.lower()
    matches = 0
    unique_expected = list(dict.fromkeys(task.expected))  # dedupe preserving order
    for exp in unique_expected:
        exp_lower = exp.lower()
        # Match full path or just the filename
        filename = Path(exp).name.lower()
        if exp_lower in answer_lower or filename in answer_lower:
            matches += 1
    threshold = task.min_matches if task.min_matches is not None else max(1, len(unique_expected) // 2)
    correct = matches >= threshold

    return RunResult(
        task_name=task.name,
        mode=mode,
        input_tokens=total_input,
        output_tokens=total_output,
        tool_calls=tool_calls,
        turns=turns,
        answer=answer,
        correct=correct,
        elapsed_sec=round(elapsed, 1),
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_table(comparisons: list[Comparison]) -> None:
    print()
    header = (
        f"{'Task':<35} │ {'Mode':<8} │ {'In Tok':>8} {'Out Tok':>8} {'Total':>8} │ "
        f"{'Calls':>5} {'Turns':>5} │ {'Correct':>7} │ {'Time':>6}"
    )
    print(header)
    print("─" * len(header))

    totals = {"indexer": [0, 0, 0, 0, 0.0], "baseline": [0, 0, 0, 0, 0.0]}  # in, out, calls, turns, time

    for comp in comparisons:
        for r in [comp.indexer, comp.baseline]:
            total_tok = r.input_tokens + r.output_tokens
            correct_str = "yes" if r.correct else "NO"
            print(
                f"{r.task_name:<35} │ {r.mode:<8} │ {r.input_tokens:>8,} {r.output_tokens:>8,} "
                f"{total_tok:>8,} │ {r.tool_calls:>5} {r.turns:>5} │ {correct_str:>7} │ {r.elapsed_sec:>5.1f}s"
            )
            totals[r.mode][0] += r.input_tokens
            totals[r.mode][1] += r.output_tokens
            totals[r.mode][2] += r.tool_calls
            totals[r.mode][3] += r.turns
            totals[r.mode][4] += r.elapsed_sec
        print("─" * len(header))

    # Summary
    print()
    print("SUMMARY")
    print("─" * 60)
    for mode in ["indexer", "baseline"]:
        t = totals[mode]
        total = t[0] + t[1]
        correct_count = sum(
            1 for c in comparisons
            for r in [c.indexer if mode == "indexer" else c.baseline]
            if r.correct
        )
        print(
            f"  {mode:<10}  tokens: {total:>10,} (in: {t[0]:>8,}  out: {t[1]:>8,})  "
            f"calls: {t[2]:>4}  turns: {t[3]:>4}  correct: {correct_count}/{len(comparisons)}  "
            f"time: {t[4]:.1f}s"
        )

    idx_total = totals["indexer"][0] + totals["indexer"][1]
    base_total = totals["baseline"][0] + totals["baseline"][1]
    if base_total > 0:
        savings = (1 - idx_total / base_total) * 100
        print(f"\n  Token reduction: {savings:+.0f}%  ({base_total:,} -> {idx_total:,})")
    call_idx = totals["indexer"][2]
    call_base = totals["baseline"][2]
    if call_base > 0:
        call_savings = (1 - call_idx / call_base) * 100
        print(f"  Tool call reduction: {call_savings:+.0f}%  ({call_base} -> {call_idx})")
    time_idx = totals["indexer"][4]
    time_base = totals["baseline"][4]
    if time_base > 0:
        speed_improvement = (1 - time_idx / time_base) * 100
        print(f"  Speed improvement: {speed_improvement:+.0f}%  ({time_base:.1f}s -> {time_idx:.1f}s)")
    print()


def to_json(comparisons: list[Comparison]) -> str:
    results = []
    for comp in comparisons:
        results.append({
            "task": comp.task.name,
            "category": comp.task.category,
            "question": comp.task.question,
            "expected": comp.task.expected,
            "indexer": {
                "input_tokens": comp.indexer.input_tokens,
                "output_tokens": comp.indexer.output_tokens,
                "total_tokens": comp.indexer.input_tokens + comp.indexer.output_tokens,
                "tool_calls": comp.indexer.tool_calls,
                "turns": comp.indexer.turns,
                "correct": comp.indexer.correct,
                "elapsed_sec": comp.indexer.elapsed_sec,
                "answer": comp.indexer.answer,
            },
            "baseline": {
                "input_tokens": comp.baseline.input_tokens,
                "output_tokens": comp.baseline.output_tokens,
                "total_tokens": comp.baseline.input_tokens + comp.baseline.output_tokens,
                "tool_calls": comp.baseline.tool_calls,
                "turns": comp.baseline.turns,
                "correct": comp.baseline.correct,
                "elapsed_sec": comp.baseline.elapsed_sec,
                "answer": comp.baseline.answer,
            },
            "token_savings_pct": round(comp.token_savings_pct, 1),
        })
    return json.dumps(results, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark indexer vs traditional tools with a real Claude agent",
    )
    parser.add_argument("project", type=Path, help="Path to the project to benchmark")
    parser.add_argument(
        "--model", default="claude-haiku-4-5-20251001",
        help="Claude model to use (default: haiku for cost efficiency)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show tasks without running agents")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument(
        "--tasks", type=str, default=None,
        help="Comma-separated task categories to run (symbol_lookup,caller_trace,file_understanding,text_search,file_discovery)",
    )
    args = parser.parse_args()

    if not args.project.is_dir():
        print(f"Error: {args.project} is not a directory", file=sys.stderr)
        sys.exit(1)

    if not args.dry_run and not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    project = args.project.resolve()
    print(f"Generating tasks for: {project}")
    tasks = generate_tasks(project)

    if args.tasks:
        allowed = set(args.tasks.split(","))
        tasks = [t for t in tasks if t.category in allowed]

    if not tasks:
        print("No tasks could be generated. Is the index built?", file=sys.stderr)
        sys.exit(1)

    print(f"Generated {len(tasks)} tasks:\n")
    for t in tasks:
        print(f"  [{t.category}] {t.name}")
        print(f"    Q: {t.question}")
        print(f"    Expected: {t.expected}")
        print()

    if args.dry_run:
        print("(dry run — not calling the API)")
        return

    print(f"Running with model: {args.model}")
    print(f"Each task runs twice (indexer mode + baseline mode)")
    print()

    comparisons: list[Comparison] = []
    for i, task in enumerate(tasks, 1):
        print(f"[{i}/{len(tasks)}] {task.name}")

        print(f"  Running indexer mode...", end="", flush=True)
        idx_result = run_agent(task, "indexer", project, args.model)
        print(
            f" {idx_result.input_tokens + idx_result.output_tokens:,} tokens, "
            f"{idx_result.tool_calls} calls, "
            f"{idx_result.elapsed_sec:.1f}s, "
            f"{'correct' if idx_result.correct else 'WRONG'}"
        )

        print(f"  Running baseline mode...", end="", flush=True)
        base_result = run_agent(task, "baseline", project, args.model)
        print(
            f" {base_result.input_tokens + base_result.output_tokens:,} tokens, "
            f"{base_result.tool_calls} calls, "
            f"{base_result.elapsed_sec:.1f}s, "
            f"{'correct' if base_result.correct else 'WRONG'}"
        )

        comparisons.append(Comparison(task=task, indexer=idx_result, baseline=base_result))

    if args.json:
        print(to_json(comparisons))
    else:
        print_table(comparisons)


if __name__ == "__main__":
    main()
