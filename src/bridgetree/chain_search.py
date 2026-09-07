"""Finite, auditable Chain search primitives (extend, join, stop)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence

from .chain_judge import JointJudge, JointScore, PublicQuery
from .chain_support import ClosureResult, close_support


@dataclass(frozen=True)
class EvidenceState:
    raw_ids: tuple[str, ...]
    paths: tuple[tuple[str, ...], ...] = ()
    expandable_ids: tuple[str, ...] = ()
    completed_actions: frozenset[str] = frozenset()
    graph_epoch: int = 0

    def __post_init__(self) -> None:
        ids = tuple(dict.fromkeys(str(x) for x in self.raw_ids))
        if len(ids) != len(self.raw_ids):
            raise ValueError("EvidenceState.raw_ids must be unique")
        for path in self.paths:
            if len(path) != len(set(path)):
                raise ValueError("a path cannot repeat a memory")
        object.__setattr__(self, "raw_ids", ids)
        object.__setattr__(self, "expandable_ids", tuple(dict.fromkeys(self.expandable_ids)))

    def extend(self, memory_id: str, *, parent: str | None = None, epoch: int | None = None) -> "EvidenceState":
        identifier = str(memory_id)
        if identifier in self.raw_ids:
            return self
        paths = self.paths or (self.raw_ids,)
        new_paths = tuple(path + (identifier,) for path in paths if identifier not in path)
        return EvidenceState(
            self.raw_ids + (identifier,), new_paths, (identifier,),
            self.completed_actions | {f"extend:{identifier}"},
            self.graph_epoch if epoch is None else epoch,
        )


@dataclass(frozen=True)
class Terminal:
    state: EvidenceState
    score: JointScore
    closure: ClosureResult | None = None

    @property
    def selected_ids(self) -> tuple[str, ...]:
        if self.closure and self.closure.status in {"single_deletion_minimal", "closure_budget_exhausted"}:
            return self.closure.retained_ids
        return self.state.raw_ids


@dataclass
class SearchArchive:
    observed_terminals: list[Terminal] = field(default_factory=list)
    verified_terminals: list[Terminal] = field(default_factory=list)
    open_states: list[EvidenceState] = field(default_factory=list)


class ChainSearcher:
    def __init__(self, query: PublicQuery, judge: JointJudge, *, horizon: int = 2,
                 max_joint_contexts: int = 512, max_verify_calls: int = 512):
        if horizon < 0 or horizon > 2:
            raise ValueError("ChainSearcher horizon must be 0, 1, or 2")
        self.query, self.judge = query, judge
        self.horizon = horizon
        self.max_joint_contexts = max_joint_contexts
        self.max_verify_calls = max_verify_calls
        self._scores: dict[tuple[str, ...], JointScore] = {}
        self._joint_calls = 0

    def score(self, ids: Sequence[str]) -> JointScore:
        canonical = tuple(dict.fromkeys(str(x) for x in ids))
        if canonical not in self._scores:
            if self._joint_calls >= self.max_joint_contexts:
                raise RuntimeError("joint budget exhausted")
            self._scores[canonical] = self.judge.score(self.query, canonical)
            self._joint_calls += 1
        return self._scores[canonical]

    def search(
        self,
        roots: Sequence[EvidenceState], *,
        proposals: Mapping[str, Sequence[str]] | Callable[[EvidenceState], Sequence[str]] = (),
               join_pool: Sequence[EvidenceState] = (), closure: bool = False) -> SearchArchive:
        archive = SearchArchive()
        frontier = list(roots)
        for state in frontier:
            archive.open_states.append(state)
        for depth in range(self.horizon + 1):
            next_frontier: list[EvidenceState] = []
            # Stop participates at every depth; no score based pruning occurs.
            for state in list(frontier):
                terminal = Terminal(state, self.score(state.raw_ids))
                archive.observed_terminals.append(terminal)
                if closure:
                    result = close_support(
                        self.query, state.raw_ids, self.judge,
                        max_verify_calls=self.max_verify_calls,
                    )
                    if result.status == "single_deletion_minimal":
                        rescored = Terminal(state, self.score(result.retained_ids), result)
                        archive.verified_terminals.append(rescored)
                elif not closure:
                    archive.verified_terminals.append(terminal)
                if depth >= self.horizon:
                    continue
                values = (
                    proposals(state) if callable(proposals)
                    else [item for anchor in state.expandable_ids for item in proposals.get(anchor, ())]
                )
                for candidate in values:
                    candidate = str(candidate)
                    if candidate in state.raw_ids:
                        continue
                    next_frontier.append(state.extend(candidate, epoch=state.graph_epoch + 1))
                # Joins use a true union and are scored afresh.
                for other in join_pool:
                    union = tuple(dict.fromkeys(state.raw_ids + other.raw_ids))
                    if union != state.raw_ids:
                        next_frontier.append(
                            EvidenceState(
                                union, state.paths + other.paths, (), frozenset({"join"}), state.graph_epoch
                            )
                        )
            frontier = _dedupe_states(next_frontier)
            archive.open_states.extend(frontier)
        return archive


def _dedupe_states(states: Iterable[EvidenceState]) -> list[EvidenceState]:
    seen: set[tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]] = set()
    result = []
    for state in states:
        key = (state.raw_ids, state.paths)
        if key not in seen:
            seen.add(key)
            result.append(state)
    return result


def choose_terminal(terminals: Sequence[Terminal]) -> Terminal | None:
    if not terminals:
        return None
    return sorted(terminals, key=lambda item: (-item.score.log_u, len(item.selected_ids), item.selected_ids))[0]
