"""Tests for PageRank computation."""

from __future__ import annotations

import networkx as nx

from indexer.graph.pagerank import compute_pagerank


def test_empty_graph():
    """Empty graph returns empty dict."""
    G = nx.DiGraph()
    assert compute_pagerank(G) == {}


def test_single_node():
    """Single node gets all the rank."""
    G = nx.DiGraph()
    G.add_node("a.py")
    scores = compute_pagerank(G)
    assert abs(scores["a.py"] - 1.0) < 0.01


def test_two_nodes_one_edge():
    """Target of a directed edge gets higher score."""
    G = nx.DiGraph()
    G.add_edge("a.py", "b.py")
    scores = compute_pagerank(G)
    assert scores["b.py"] > scores["a.py"]


def test_cycle_graph():
    """Cycle converges with roughly equal scores."""
    G = nx.DiGraph()
    G.add_edge("a.py", "b.py")
    G.add_edge("b.py", "c.py")
    G.add_edge("c.py", "a.py")
    scores = compute_pagerank(G)
    vals = list(scores.values())
    assert max(vals) - min(vals) < 0.01


def test_star_graph():
    """Hub node (pointed to by all others) gets highest score."""
    G = nx.DiGraph()
    for name in ["a.py", "b.py", "c.py"]:
        G.add_edge(name, "hub.py")
    scores = compute_pagerank(G)
    assert scores["hub.py"] == max(scores.values())


def test_personalization_boost():
    """Focused file gets a higher score than without personalization."""
    G = nx.DiGraph()
    G.add_edge("a.py", "b.py")
    G.add_edge("b.py", "c.py")
    scores_plain = compute_pagerank(G)
    scores_boosted = compute_pagerank(G, personalize_files=["a.py"])
    # Personalization should boost the focused file relative to baseline
    assert scores_boosted["a.py"] > scores_plain["a.py"]


def test_personalization_multiple():
    """Multiple focused files are both boosted."""
    G = nx.DiGraph()
    G.add_edge("a.py", "c.py")
    G.add_edge("b.py", "c.py")
    G.add_node("d.py")
    scores = compute_pagerank(G, personalize_files=["a.py", "b.py"])
    assert scores["a.py"] > scores["d.py"]
    assert scores["b.py"] > scores["d.py"]


def test_scores_sum_to_one():
    """All scores sum to approximately 1.0."""
    G = nx.DiGraph()
    G.add_edge("a.py", "b.py")
    G.add_edge("b.py", "c.py")
    G.add_edge("c.py", "a.py")
    G.add_node("d.py")
    scores = compute_pagerank(G)
    assert abs(sum(scores.values()) - 1.0) < 0.01
