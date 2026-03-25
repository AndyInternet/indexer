"""Personalized PageRank computation over the dependency graph."""

from __future__ import annotations

import networkx as nx


def _pagerank_power_iteration(
    graph: nx.DiGraph,
    alpha: float = 0.85,
    personalization: dict[str, float] | None = None,
    max_iter: int = 100,
    tol: float = 1e-6,
) -> dict[str, float]:
    """Simple power-iteration PageRank (no scipy/numpy dependency)."""
    nodes = list(graph.nodes)
    n = len(nodes)
    if n == 0:
        return {}

    # Initialize
    if personalization:
        total = sum(personalization.values())
        p = {node: personalization.get(node, 0.0) / total for node in nodes}
    else:
        p = {node: 1.0 / n for node in nodes}

    scores = dict(p)

    # Precompute out-degree weights
    out_weight: dict[str, float] = {}
    for node in nodes:
        total_w = sum(d.get("weight", 1.0) for _, _, d in graph.out_edges(node, data=True))
        out_weight[node] = total_w

    for _ in range(max_iter):
        new_scores = {}
        # Dangling nodes (no outgoing edges) distribute uniformly
        dangling_sum = sum(scores[node] for node in nodes if out_weight[node] == 0)

        for node in nodes:
            rank = (1 - alpha) * p[node]
            rank += alpha * dangling_sum / n

            # Sum contributions from incoming edges
            for pred in graph.predecessors(node):
                w = graph[pred][node].get("weight", 1.0)
                rank += alpha * scores[pred] * w / out_weight[pred]

            new_scores[node] = rank

        # Check convergence
        diff = sum(abs(new_scores[node] - scores[node]) for node in nodes)
        scores = new_scores
        if diff < tol:
            break

    return scores


def compute_pagerank(
    graph: nx.DiGraph,
    personalize_files: list[str] | None = None,
    personalize_boost: float = 50.0,
    alpha: float = 0.85,
) -> dict[str, float]:
    """Compute personalized PageRank scores for files in the dependency graph."""
    if len(graph) == 0:
        return {}

    # Build personalization vector
    personalization = None
    if personalize_files:
        base_weight = 1.0
        personalization = {}
        for node in graph.nodes:
            if node in personalize_files:
                personalization[node] = base_weight * personalize_boost
            else:
                personalization[node] = base_weight

    scores = _pagerank_power_iteration(
        graph, alpha=alpha, personalization=personalization,
    )

    # Sort descending
    return dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))
