---
name: explore-with-indexer
description: Spawn an exploration agent pre-loaded with indexer instructions for code navigation. Use when investigating code structure, tracing dependencies, or understanding unfamiliar parts of the codebase.
disable-model-invocation: true
allowed-tools: Bash, Agent
argument-hint: "<question about the codebase>"
---

# Explore Codebase with Indexer

Spawn a focused exploration agent that uses `indexer` commands for all code navigation.

## Steps

1. First, ensure the index is up to date:

```bash
indexer update .
```

2. Spawn an Explore agent with the following prompt, replacing `$ARGUMENTS` with the user's exploration question:

> You are a code exploration agent. Your task: $ARGUMENTS
>
> MANDATORY: Use `indexer` commands via Bash for ALL code navigation in this repo. Available commands:
> - `indexer search <name>` — find symbol definitions (substring match)
> - `indexer refs <symbol>` — find all references to a symbol
> - `indexer callers <symbol>` — find functions that call a symbol
> - `indexer impl <symbol>` — get full source of a symbol
> - `indexer skeleton [file]` — view file/repo structure (signatures only)
> - `indexer map --tokens 2048` — ranked overview of important files
> - `indexer map --tokens 1024 --focus <file>` — focused map around a file
> - `indexer grep <pattern> [--ext .yaml] [-i]` — full-text search across all files
> - `indexer find <pattern> [--type f|d]` — find files/dirs by glob pattern
> - `indexer tree [path] [--depth N]` — directory tree view
>
> Do NOT use Grep, Glob, find, or ls tools. Use `indexer grep` for text search, `indexer find` for file search, `indexer tree` for directory listing. Only use Read when you know the exact file and lines to examine.
>
> Start by running `indexer map --tokens 2048` to orient yourself, then investigate the question.
> Report your findings as a structured summary with file paths and key symbols.

3. Return the agent's findings to the user.

## When to use

- User asks "how does X work?" about unfamiliar code
- User asks to trace a call chain or dependency graph
- User asks to understand the architecture of a subsystem
- Before making changes to code you haven't read yet
- When you need to understand cross-file relationships
