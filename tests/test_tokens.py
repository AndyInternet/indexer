"""Tests for token counting."""

from indexer.tokens import count_tokens


def test_count_tokens_simple():
    """count_tokens returns a positive int for normal text."""
    assert count_tokens("hello world") > 0


def test_count_tokens_empty():
    """Empty string has zero tokens."""
    assert count_tokens("") == 0


def test_count_tokens_multiline():
    """Multi-line string returns a reasonable count."""
    text = "line one\nline two\nline three\n"
    tokens = count_tokens(text)
    assert tokens > 3  # at least one token per line
