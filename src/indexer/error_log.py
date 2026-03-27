"""Automatic error logging for the indexer CLI."""

from __future__ import annotations

import datetime
import json
import sys
import traceback
from pathlib import Path

import click

from indexer.config import ERROR_LOG_NAME, INDEXER_DIR, find_project_root


def _find_path_in_args(argv: list[str]) -> str | None:
    """Scan an argument list for --path / -p <value>."""
    for i, arg in enumerate(argv):
        if arg in ("--path", "-p") and i + 1 < len(argv):
            return argv[i + 1]
    return None


def _resolve_indexer_dir(ctx: click.Context | None) -> Path:
    """Best-effort resolve the .indexer directory from CLI context or cwd.

    Checks Click context params, remaining group args, and sys.argv for a
    --path / -p flag.  Falls back to cwd.
    """
    path_str = None

    # 1. Walk Click context chain for a "path" param
    c: click.Context | None = ctx
    while c is not None:
        if c.params and c.params.get("path"):
            path_str = c.params["path"]
            break
        c = c.parent

    # 2. Parse saved raw args from the group context (subcommand args)
    if path_str is None and ctx is not None:
        raw_args = (ctx.obj or {}).get("_raw_args", [])
        path_str = _find_path_in_args(raw_args)

    # 3. Fall back to sys.argv
    if path_str is None:
        path_str = _find_path_in_args(sys.argv[1:])

    root = Path(path_str).resolve() if path_str else Path.cwd()
    root = find_project_root(root)
    return root / INDEXER_DIR


def log_error(error: Exception, ctx: click.Context | None) -> None:
    """Append a JSONL error entry to .indexer/errors.log.

    Silently swallows any failures so the original error is never masked.
    """
    try:
        indexer_dir = _resolve_indexer_dir(ctx)
        indexer_dir.mkdir(parents=True, exist_ok=True)

        command = "unknown"
        if ctx is not None:
            # Walk to the invoked subcommand if available
            sub = ctx.invoked_subcommand
            if sub:
                command = sub
            else:
                command = ctx.info_name or "unknown"

        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "command": command,
            "args": sys.argv[1:],
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": "".join(traceback.format_exception(error)),
        }

        log_path = indexer_dir / ERROR_LOG_NAME
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:  # noqa: BLE001
        pass


class ErrorLoggingGroup(click.Group):
    """Click group that logs unhandled exceptions to .indexer/errors.log."""

    def get_params(self, ctx: click.Context) -> list[click.Parameter]:
        params = super().get_params(ctx)
        params.append(
            click.Option(
                ["--no-error-log"],
                is_flag=True,
                default=False,
                hidden=True,
                is_eager=True,
                expose_value=False,
                callback=lambda ctx, _param, value: ctx.ensure_object(dict)
                or ctx.obj.update(_no_error_log=value),
                help="Disable error logging (used in tests).",
            )
        )
        return params

    def invoke(self, ctx: click.Context) -> None:
        # Save raw args before Click consumes them during dispatch
        ctx.ensure_object(dict)
        ctx.obj["_raw_args"] = list(ctx.args or [])
        try:
            return super().invoke(ctx)
        except Exception as e:
            if not ctx.obj.get("_no_error_log"):
                log_error(e, ctx)
            raise
