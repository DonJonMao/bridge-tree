"""Small, dependency-light mathematical oracle for semantic-path selection.

This module intentionally has no dependency on PersonaMem, model clients, or
the production retriever.  It is useful in tests and notebooks when checking
the frozen-DAG recurrences, PSD feature construction, and eager/lazy greedy
equivalence.  All numerical work is float64 and all IDs are canonicalized to
strings so that an input permutation cannot change an oracle result.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


def _sigmoid(value: float) -> float:
    return float(1.0 / (1.0 + np.exp(-value))) if value >= 0 else float(np.exp(value) / (1.0 + np.exp(value)))


def bounded_quality(raw: float, score_space: str = "unit_interval") -> float:
    """Adapt one declared scorer output to the closed interval ``[0, 1]``."""

    value = float(raw)
    if not np.isfinite(value):
        raise ValueError("quality score must be finite")
    space = str(score_space).strip().lower().replace("-", "_")
    if space in {"unit", "probability", "probabilities", "unit_interval"}:
        if not 0.0 <= value <= 1.0:
            raise ValueError("unit-interval quality is outside [0, 1]")
        return value
    if space in {"logit", "logit_diff", "logit_difference", "raw_logit_difference"}:
        return _sigmoid(value)
    raise ValueError("score_space must be unit_interval or logit_difference")


def _quality_value(raw: Any) -> float:
    """Read a scalar quality or a production-style quality record.

    The reference module deliberately does not import the production package,
    but accepting its small ``value``/``score_space`` protocol makes the
    mathematical oracle useful in cross-checks without coupling the modules.
    Mapping responses from lightweight adapters are accepted as well.
    """

    if isinstance(raw, Mapping):
        if "raw_score" in raw:
            return bounded_quality(raw["raw_score"], raw.get("score_space", "unit_interval"))
        if "score" in raw or "value" in raw:
            # ``score``/``value`` is conventionally already the adapted value
            # in a persisted quality record; only an explicit ``raw_score``
            # above should be passed through a logit transform.
            return bounded_quality(raw.get("score", raw.get("value")), "unit_interval")
        raise ValueError("quality record has no score/value field")
    if hasattr(raw, "value"):
        return bounded_quality(raw.value, "unit_interval")
    return bounded_quality(raw)


def _atom_table(atoms: Mapping[Any, Any]) -> dict[str, np.ndarray]:
    """Canonicalize an ID->feature table and reject normalization collisions."""

    if not isinstance(atoms, Mapping):
        raise ValueError("atoms must be a mapping")
    table: dict[str, np.ndarray] = {}
    for raw_identifier, raw_value in atoms.items():
        identifier = str(raw_identifier)
        if identifier in table:
            raise ValueError("atom IDs must remain unique after string normalization")
        value = np.asarray(
            raw_value.matrix if hasattr(raw_value, "matrix") else raw_value,
            dtype=np.float64,
        )
        if value.ndim == 1:
            value = value.reshape(-1)
        elif value.ndim == 2 and value.shape[0] == value.shape[1]:
            # A matrix atom is represented by a PSD matrix.  The greedy
            # helpers operate on rank-one features, so retain it as-is and
            # let ``_matrix_from_atom`` handle objective construction below.
            value = value.copy()
        else:
            value = value.reshape(-1)
        if value.size == 0 or not np.all(np.isfinite(value)):
            raise ValueError(f"atom {identifier} must be finite and non-empty")
        table[identifier] = value
    return table


def _target_count(k: int | None, size: int) -> int:
    if k is None:
        return size
    if isinstance(k, bool):
        raise ValueError("k must be a non-negative integer")
    try:
        value = int(k)
    except (TypeError, ValueError) as exc:
        raise ValueError("k must be a non-negative integer") from exc
    try:
        if float(k) != float(value):
            raise ValueError("k must be a non-negative integer")
    except (TypeError, ValueError) as exc:
        raise ValueError("k must be a non-negative integer") from exc
    if value < 0:
        return 0
    return min(value, size)


def _matrix_from_atom(value: np.ndarray) -> np.ndarray:
    """Return a symmetric PSD matrix for a vector or explicit matrix atom."""

    matrix = np.outer(value, value) if value.ndim == 1 else (value + value.T) * 0.5
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or not np.all(np.isfinite(matrix)):
        raise ValueError("atoms must be finite vectors or square matrices")
    eigenvalues = np.linalg.eigvalsh(matrix)
    scale = max(1.0, float(np.max(np.abs(eigenvalues))) if eigenvalues.size else 1.0)
    if eigenvalues.size and float(np.min(eigenvalues)) < -1e-10 * scale:
        raise ValueError("atom matrix must be positive semidefinite")
    return matrix


def angular_affinity(left: np.ndarray, right: np.ndarray) -> float:
    """Non-negative angular navigation affinity ``1-acos(cos)/pi``."""

    lhs = np.asarray(left, dtype=np.float64).reshape(-1)
    rhs = np.asarray(right, dtype=np.float64).reshape(-1)
    if lhs.shape != rhs.shape or lhs.size == 0 or not np.all(np.isfinite(lhs)) or not np.all(np.isfinite(rhs)):
        raise ValueError("angular vectors must be finite and have equal non-empty dimensions")
    norms = (float(np.linalg.norm(lhs)), float(np.linalg.norm(rhs)))
    if min(norms) <= 1e-12:
        raise ValueError("angular vectors must be non-zero")
    cosine = float(np.dot(lhs, rhs) / (norms[0] * norms[1]))
    return float(1.0 - np.arccos(np.clip(cosine, -1.0, 1.0)) / np.pi)


@dataclass(frozen=True)
class FrozenDAG:
    memory_ids: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]
    edge_weights: tuple[tuple[str, str, float], ...]
    root_mass: tuple[float, ...]
    graph_hash: str
    layers: tuple[tuple[str, ...], ...] = ()

    @classmethod
    def build(
        cls,
        memory_ids: Sequence[Any],
        edges: Iterable[Sequence[Any]],
        edge_weights: Mapping[Sequence[Any], float] | Iterable[Sequence[Any]] | None = None,
        root_mass: Mapping[Any, float] | Sequence[float] | None = None,
        layers: Sequence[Sequence[Any]] | None = None,
    ) -> "FrozenDAG":
        ids_raw = tuple(str(value) for value in memory_ids)
        if len(ids_raw) != len(set(ids_raw)):
            raise ValueError("memory IDs must be unique")
        ids = tuple(sorted(ids_raw))
        id_set = set(ids)
        edge_set: set[tuple[str, str]] = set()
        for item in edges:
            if len(item) != 2:
                raise ValueError("edges must contain parent and child")
            edge = (str(item[0]), str(item[1]))
            if edge[0] not in id_set or edge[1] not in id_set or edge[0] == edge[1]:
                raise ValueError("edge references an invalid ID")
            edge_set.add(edge)
        ordered_edges = tuple(sorted(edge_set))
        weights: dict[tuple[str, str], float] = {}
        if edge_weights is not None:
            items = edge_weights.items() if isinstance(edge_weights, Mapping) else edge_weights
            for item in items:
                if isinstance(edge_weights, Mapping):
                    key, value = item
                    if len(key) != 2:
                        raise ValueError("edge weight keys must be pairs")
                    item = (key[0], key[1], value)
                if len(item) != 3:
                    raise ValueError("edge weights must contain parent, child, weight")
                edge = (str(item[0]), str(item[1]))
                if edge not in edge_set or edge in weights:
                    raise ValueError("edge weight references an unknown or duplicate edge")
                value = float(item[2])
                if not np.isfinite(value) or value < 0:
                    raise ValueError("edge weights must be finite and non-negative")
                weights[edge] = value
        canonical_weights = tuple((left, right, weights.get((left, right), 0.0)) for left, right in ordered_edges)
        if root_mass is None:
            root = tuple(0.0 for _ in ids)
        elif isinstance(root_mass, Mapping):
            normalized: dict[str, float] = {}
            for key, value in root_mass.items():
                identifier = str(key)
                if identifier in normalized or identifier not in id_set:
                    raise ValueError("root mass has duplicate or unknown IDs")
                normalized[identifier] = float(value)
            root = tuple(normalized.get(identifier, 0.0) for identifier in ids)
        else:
            values = tuple(float(value) for value in root_mass)
            if len(values) != len(ids_raw):
                raise ValueError("root mass must align with memory IDs")
            raw_by_id = dict(zip(ids_raw, values))
            root = tuple(raw_by_id[identifier] for identifier in ids)
        if any(not np.isfinite(value) or value < 0 for value in root):
            raise ValueError("root mass must be finite and non-negative")
        normalized_layers = tuple(tuple(sorted(str(value) for value in layer)) for layer in (layers or ()))
        if normalized_layers:
            flattened = [value for layer in normalized_layers for value in layer]
            if len(flattened) != len(set(flattened)) or set(flattened) != id_set:
                raise ValueError("layers must partition the graph IDs")
            depth = {value: index for index, layer in enumerate(normalized_layers) for value in layer}
            if any(depth[left] >= depth[right] for left, right in ordered_edges):
                raise ValueError("layers must respect edge direction")
        else:
            # Kahn's algorithm is enough for the small oracle and avoids any
            # dependence on lexical IDs when detecting a cycle.
            indegree = {identifier: 0 for identifier in ids}
            children = {identifier: [] for identifier in ids}
            for left, right in ordered_edges:
                indegree[right] += 1
                children[left].append(right)
            queue = sorted(identifier for identifier, value in indegree.items() if value == 0)
            visited = []
            while queue:
                current = queue.pop(0)
                visited.append(current)
                for child in sorted(children[current]):
                    indegree[child] -= 1
                    if indegree[child] == 0:
                        queue.append(child)
                        queue.sort()
            if len(visited) != len(ids):
                raise ValueError("graph must be acyclic")
        payload = {
            "memory_ids": ids,
            "edges": ordered_edges,
            "edge_weights": canonical_weights,
            "root_mass": root,
            "layers": normalized_layers,
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return cls(ids, ordered_edges, canonical_weights, root, digest, normalized_layers)

    @property
    def roots(self) -> tuple[str, ...]:
        incoming = {identifier: False for identifier in self.memory_ids}
        for _left, right, weight in self.edge_weights:
            if weight > 0:
                incoming[right] = True
        return tuple(identifier for identifier in self.memory_ids if not incoming[identifier])


@dataclass(frozen=True)
class GraphMeasure:
    graph: FrozenDAG
    transition: Mapping[str, Mapping[str, float]]
    h: Mapping[str, float]
    gamma: Mapping[str, Mapping[str, float]]
    w: np.ndarray
    termination_quality: float


def propagate(graph: FrozenDAG) -> GraphMeasure:
    """Compute sparse transition, access quality ``h``, ``gamma`` and ``w``."""

    ids = graph.memory_ids
    if len(ids) != len(set(ids)):
        raise ValueError("graph memory IDs must be unique")
    positions = {identifier: index for index, identifier in enumerate(ids)}
    rows: dict[str, dict[str, float]] = {identifier: {} for identifier in ids}
    for left, right, weight in graph.edge_weights:
        if weight > 0:
            rows[left][right] = float(weight)
    for left in ids:
        total = sum(rows[left].values())
        if total:
            rows[left] = {right: value / total for right, value in sorted(rows[left].items())}
    roots = graph.roots
    root_values = {identifier: graph.root_mass[positions[identifier]] for identifier in roots}
    nonroot_mass = {
        identifier: float(value)
        for identifier, value in zip(ids, graph.root_mass)
        if float(value) > 1e-12 and identifier not in roots
    }
    if nonroot_mass:
        raise ValueError("root mass assigns positive mass to a non-root node")
    total_root = sum(root_values.values())
    if total_root <= 0 and roots:
        root_values = {identifier: 1.0 / len(roots) for identifier in roots}
    elif total_root:
        root_values = {identifier: value / total_root for identifier, value in root_values.items()}
    order = tuple(value for layer in graph.layers for value in layer) if graph.layers else _topological(graph)
    h = {identifier: 0.0 for identifier in ids}
    gamma: dict[str, dict[str, float]] = {identifier: {} for identifier in ids}
    for child in order:
        incoming = {
            parent: h[parent] * rows[parent].get(child, 0.0)
            for parent in ids
            if rows[parent].get(child, 0.0) > 0 and h[parent] > 0
        }
        h[child] = root_values.get(child, 0.0) + sum(incoming.values())
        mass = sum(incoming.values())
        if mass:
            gamma[child] = {parent: value / mass for parent, value in sorted(incoming.items())}
    w = np.zeros((len(ids), len(ids)), dtype=np.float64)
    for child in order:
        column = positions[child]
        for parent, probability in gamma[child].items():
            w[:, column] += probability * w[:, positions[parent]]
            w[positions[parent], column] += probability
    terminals = [identifier for identifier in ids if not rows[identifier]]
    terminal = float(sum(h[identifier] for identifier in terminals))
    w.setflags(write=False)
    if roots and not np.isclose(terminal, 1.0, atol=1e-8, rtol=1e-8):
        # Every non-terminal row is normalized and the graph is acyclic, so a
        # valid rooted DAG should conserve all path mass at terminal nodes.
        # Expose malformed disconnected/root declarations instead of calling
        # the resulting partial mass a probability measure.
        raise ValueError("terminal path mass does not conserve the normalized root prior")
    return GraphMeasure(graph, rows, h, gamma, w, terminal)


def _topological(graph: FrozenDAG) -> tuple[str, ...]:
    incoming = {identifier: 0 for identifier in graph.memory_ids}
    children = {identifier: [] for identifier in graph.memory_ids}
    for left, right in graph.edges:
        incoming[right] += 1
        children[left].append(right)
    queue = sorted(identifier for identifier, value in incoming.items() if value == 0)
    result = []
    while queue:
        current = queue.pop(0)
        result.append(current)
        for child in sorted(children[current]):
            incoming[child] -= 1
            if incoming[child] == 0:
                queue.append(child)
                queue.sort()
    if len(result) != len(graph.memory_ids):
        raise ValueError("graph must be acyclic")
    return tuple(result)


def thin_svd_shrink(
    vector: np.ndarray,
    ancestor_vectors: Sequence[np.ndarray],
    weights: Sequence[float] | None = None,
) -> np.ndarray:
    """Apply ``(I + B Bᵀ)^(-1/2)`` using only the thin SVD of ``B``."""

    value = np.asarray(vector, dtype=np.float64).reshape(-1)
    if value.size == 0 or not np.all(np.isfinite(value)):
        raise ValueError("vector must be finite and non-empty")
    if not ancestor_vectors:
        return value.copy()
    if weights is not None:
        try:
            if len(weights) != len(ancestor_vectors):
                raise ValueError("ancestor weights and vectors must have equal length")
        except TypeError as exc:
            raise ValueError("ancestor weights must be a finite sequence") from exc
    columns = []
    for index, ancestor in enumerate(ancestor_vectors):
        item = np.asarray(ancestor, dtype=np.float64).reshape(-1)
        if item.shape != value.shape or not np.all(np.isfinite(item)):
            raise ValueError("ancestor dimensions do not match vector")
        coefficient = 1.0 if weights is None else float(weights[index])
        if not np.isfinite(coefficient) or coefficient < 0:
            raise ValueError("ancestor weights must be finite and non-negative")
        columns.append(np.sqrt(coefficient) * item)
    if not columns:
        return value.copy()
    u, singular, _ = np.linalg.svd(np.column_stack(columns), full_matrices=False)
    projection = u.T @ value
    return value + u @ ((1.0 / np.sqrt(1.0 + singular**2) - 1.0) * projection)


def semantic_atom(
    quality: float,
    vector: np.ndarray,
    ancestors: Sequence[np.ndarray] = (),
    ancestor_weights: Sequence[float] | None = None,
) -> np.ndarray:
    """Return the fixed rank-one feature ``phi=sqrt(r) H v``."""

    r = bounded_quality(quality)
    value = np.asarray(vector, dtype=np.float64).reshape(-1)
    norm = float(np.linalg.norm(value))
    if norm <= 1e-12 or not np.all(np.isfinite(value)):
        raise ValueError("candidate vector must be finite and non-zero")
    shrunk = thin_svd_shrink(value / norm, ancestors, ancestor_weights)
    return np.sqrt(r) * shrunk


def logdet_value(features: Sequence[np.ndarray]) -> float:
    if not features:
        return 0.0
    first = np.asarray(features[0], dtype=np.float64).reshape(-1)
    if first.size == 0 or not np.all(np.isfinite(first)):
        raise ValueError("features must be finite and non-empty")
    matrix = np.eye(first.size, dtype=np.float64)
    for feature in features:
        value = np.asarray(feature, dtype=np.float64).reshape(-1)
        if value.shape != first.shape or not np.all(np.isfinite(value)):
            raise ValueError("feature dimensions must match and values must be finite")
        matrix += np.outer(value, value)
    sign, result = np.linalg.slogdet((matrix + matrix.T) * 0.5)
    if sign <= 0 or not np.isfinite(result):
        raise FloatingPointError("I + sum(phi phi^T) is not positive definite")
    return float(result)


def marginal(feature: np.ndarray, selected: Sequence[np.ndarray] = ()) -> float:
    candidate = np.asarray(feature, dtype=np.float64).reshape(-1)
    if candidate.size == 0 or not np.all(np.isfinite(candidate)):
        raise ValueError("feature must be finite and non-empty")
    if not selected:
        return float(np.log1p(np.dot(candidate, candidate)))
    rows = []
    for item in selected:
        row = np.asarray(item, dtype=np.float64).reshape(-1)
        if row.shape != candidate.shape or not np.all(np.isfinite(row)):
            raise ValueError("feature dimensions do not match")
        rows.append(row)
    basis = np.vstack(rows)
    if basis.shape[1] != candidate.size:
        raise ValueError("feature dimensions do not match")
    gram = np.eye(len(basis), dtype=np.float64) + basis @ basis.T
    cross = basis @ candidate
    conditional = float(np.dot(candidate, candidate) - cross @ np.linalg.solve(gram, cross))
    return float(np.log1p(max(0.0, conditional)))


def greedy(atoms: Mapping[Any, np.ndarray], k: int | None = None) -> tuple[list[str], list[float]]:
    table = _atom_table(atoms)
    if any(value.ndim != 1 for value in table.values()):
        raise ValueError("greedy expects rank-one feature vectors")
    remaining = sorted(table)
    target = _target_count(k, len(remaining))
    selected: list[str] = []
    margins: list[float] = []
    while len(selected) < target:
        selected_features = [table[identifier] for identifier in selected]
        rows = [(identifier, marginal(table[identifier], selected_features)) for identifier in remaining]
        best_margin = max(value for _identifier, value in rows)
        best = min(identifier for identifier, value in rows if value == best_margin)
        selected.append(best)
        margins.append(float(dict(rows)[best]))
        remaining.remove(best)
    return selected, margins


def lazy_greedy(
    atoms: Mapping[Any, np.ndarray],
    qualities: Mapping[Any, Any] | None = None,
    k: int | None = None,
) -> tuple[list[str], list[float], dict[str, Any]]:
    """Reference fixed-pool lazy selector with ``log(1+r)`` upper bounds."""

    table = _atom_table(atoms)
    if any(value.ndim != 1 for value in table.values()):
        raise ValueError("lazy_greedy expects rank-one feature vectors")
    quality: dict[str, float] = {}
    for raw_identifier, raw_value in (qualities or {}).items():
        identifier = str(raw_identifier)
        if identifier in quality:
            raise ValueError("quality IDs must remain unique after string normalization")
        quality[identifier] = _quality_value(raw_value)
    unknown = set(quality) - set(table)
    if unknown:
        raise ValueError("qualities contain unknown IDs")
    upper = {
        identifier: float(np.log1p(quality.get(identifier, np.dot(value, value))))
        for identifier, value in table.items()
    }
    for identifier, value in table.items():
        if identifier in quality and float(np.dot(value, value)) > quality[identifier] + 1e-10:
            raise ValueError(f"quality upper bound for {identifier} is smaller than its atom norm")
    target = _target_count(k, len(table))
    selected: list[str] = []
    margins: list[float] = []
    materialized: set[str] = set()
    while len(selected) < target:
        while True:
            exact_rows = []
            selected_features = [table[identifier] for identifier in selected]
            for identifier in sorted(materialized - set(selected)):
                exact_rows.append((identifier, marginal(table[identifier], selected_features)))
            unseen = sorted(set(table) - materialized - set(selected))
            if not exact_rows:
                if not unseen:
                    break
                materialized.add(unseen[0])
                continue
            best_id, best_margin = min(exact_rows, key=lambda item: (-item[1], item[0]))
            if not unseen:
                break
            unseen_best = min(unseen, key=lambda identifier: (-upper[identifier], identifier))
            if upper[unseen_best] > best_margin or (upper[unseen_best] == best_margin and unseen_best < best_id):
                materialized.add(unseen_best)
                continue
            break
        if not exact_rows:
            break
        best_id, best_margin = min(exact_rows, key=lambda item: (-item[1], item[0]))
        selected.append(best_id)
        margins.append(float(best_margin))
    return selected, margins, {
        "complete": len(selected) == target,
        "materialized": len(materialized),
        "upper_bounds": upper,
    }


# Friendly aliases used by external mathematical checks.
FrozenProposalGraph = FrozenDAG
FrozenGraphMeasure = GraphMeasure
angular_navigation_affinity = angular_affinity
propagate_frozen_graph = propagate
thin_svd_condition = thin_svd_shrink
information_atom = semantic_atom
logdet_greedy = greedy


__all__ = [
    "bounded_quality",
    "angular_affinity",
    "angular_navigation_affinity",
    "FrozenDAG",
    "FrozenProposalGraph",
    "GraphMeasure",
    "FrozenGraphMeasure",
    "propagate",
    "propagate_frozen_graph",
    "thin_svd_shrink",
    "thin_svd_condition",
    "semantic_atom",
    "information_atom",
    "logdet_value",
    "marginal",
    "greedy",
    "logdet_greedy",
    "lazy_greedy",
]
