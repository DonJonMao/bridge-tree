"""Method settings for evidence-driven BridgeTree; no deployment secrets."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from numbers import Integral, Real


def _integer(value, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


@dataclass(frozen=True)
class EvidenceSearchConfig:
    coverage_roots: int = 6
    exploration_roots: int = 4
    quantum_new_sets: int = 24
    quantum_measurements: int = 8
    max_consecutive_quanta: int = 2
    exploration_fraction: float = 0.5
    reserve_score_fraction: float = 0.25
    max_pivots: int = 4
    max_pivot_depth: int = 2
    max_speculative_depth: int = 2
    max_speculative_states: int = 8
    max_pairs_per_state: int = 6
    marginal_epsilon: float = 0.0
    root_selection: str = "diverse"

    def __post_init__(self):
        positive = {"coverage_roots", "quantum_new_sets", "quantum_measurements", "max_consecutive_quanta"}
        for name in positive | {
            "exploration_roots",
            "max_pivots",
            "max_pivot_depth",
            "max_speculative_depth",
            "max_speculative_states",
            "max_pairs_per_state",
        }:
            object.__setattr__(self, name, _integer(getattr(self, name), name, 1 if name in positive else 0))
        if self.quantum_new_sets < 4:
            raise ValueError("quantum_new_sets must accommodate one complete four-set measurement")
        for name in ("exploration_fraction", "reserve_score_fraction", "marginal_epsilon"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            if name == "marginal_epsilon":
                if value < 0:
                    raise ValueError("marginal_epsilon must be nonnegative")
            elif not 0 < value < 1:
                raise ValueError(f"{name} must be between zero and one")
        if self.root_selection not in {"diverse", "discovery"}:
            raise ValueError("root_selection must be diverse or discovery")


@dataclass(frozen=True)
class EvidenceSelectionConfig:
    max_requirements: int = 6
    max_llm_calls: int = 24
    max_json_repairs: int = 6
    max_repairs_per_request: int = 2
    max_selection_revisions: int = 2
    input_token_budget: int = 16384
    map_batch_token_budget: int = 6144
    output_max_tokens: int = 4096
    max_quote_chars: int = 400
    max_feedback_rounds: int = 2
    response_format: str = "plain"
    selection_input_margin: int = 256

    def __post_init__(self):
        zero = {
            "max_json_repairs",
            "max_repairs_per_request",
            "max_selection_revisions",
            "max_feedback_rounds",
            "selection_input_margin",
        }
        for name in self.__dataclass_fields__:
            if name == "response_format":
                continue
            object.__setattr__(self, name, _integer(getattr(self, name), name, 0 if name in zero else 1))
        if self.map_batch_token_budget > self.input_token_budget:
            raise ValueError("map_batch_token_budget cannot exceed input_token_budget")
        if not isinstance(self.response_format, str) or self.response_format not in {
            "plain",
            "json_object",
            "json_schema",
        }:
            raise ValueError("response_format must be plain, json_object, or json_schema")
        if self.selection_input_margin >= self.input_token_budget:
            raise ValueError("selection_input_margin must be smaller than input_token_budget")


@dataclass(frozen=True)
class EvidenceBridgeConfig:
    search: EvidenceSearchConfig = field(default_factory=EvidenceSearchConfig)
    selection: EvidenceSelectionConfig = field(default_factory=EvidenceSelectionConfig)
    gap_ann_calls: int = 2
    gap_proposal_width: int = 4

    def __post_init__(self):
        if not isinstance(self.search, EvidenceSearchConfig) or not isinstance(self.selection, EvidenceSelectionConfig):
            raise ValueError("evidence_bridge search/selection must be typed settings")
        object.__setattr__(self, "gap_ann_calls", _integer(self.gap_ann_calls, "gap_ann_calls"))
        object.__setattr__(self, "gap_proposal_width", _integer(self.gap_proposal_width, "gap_proposal_width", 1))
