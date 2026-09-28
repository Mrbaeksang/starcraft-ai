from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

from starcraft_ai.data import iter_jsonl_v1
from starcraft_ai.data.schema import ActionV1, ObservationV1, TransitionV1, UnitObservationV1


@dataclass(frozen=True, slots=True)
class BackendComparisonPolicy:
    min_aligned_actions: int = 20
    min_action_alignment: float = 0.95
    max_actor_count_mae: float = 0.5
    max_action_target_position_mae: float = 16.0
    min_visible_unit_precision: float = 0.97
    min_visible_unit_recall: float = 0.97
    max_unit_position_mae: float = 8.0
    max_unit_hp_mae: float = 1.0
    max_minerals_mae: float = 1.0
    max_gas_mae: float = 1.0
    max_supply_used_mae: float = 0.0
    max_supply_total_mae: float = 0.0
    max_state_frame_delta: float = 0.0


@dataclass(frozen=True, slots=True)
class BackendComparisonResult:
    reference_transitions: int
    candidate_transitions: int
    aligned_actions: int
    reference_action_alignment: float
    candidate_action_alignment: float
    actor_count_mae: float
    action_target_position_mae: float
    state_frames_compared: int
    state_frame_delta_mae: float
    visible_unit_precision: float
    visible_unit_recall: float
    matched_visible_units: int
    unit_position_mae: float
    unit_position_p95: float
    unit_hp_mae: float
    minerals_mae: float
    gas_mae: float
    supply_used_mae: float
    supply_total_mae: float
    promotion_eligible: bool
    promotion_failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["promotion_failures"] = list(self.promotion_failures)
        return value


@dataclass(frozen=True, slots=True)
class _AlignedAction:
    reference: TransitionV1
    candidate: TransitionV1


def _target_position_distance(left: ActionV1, right: ActionV1) -> float | None:
    if left.target_x is None or left.target_y is None:
        return None
    if right.target_x is None or right.target_y is None:
        return None
    return math.hypot(left.target_x - right.target_x, left.target_y - right.target_y)


def _action_cost(reference: ActionV1, candidate: ActionV1) -> float:
    cost = abs(len(reference.actor_unit_ids) - len(candidate.actor_unit_ids)) * 32.0
    if reference.argument_type_id != candidate.argument_type_id:
        cost += 512.0
    if (reference.target_unit_id is None) != (candidate.target_unit_id is None):
        cost += 256.0
    target_distance = _target_position_distance(reference, candidate)
    if target_distance is not None:
        cost += target_distance
    elif (reference.target_x is None) != (candidate.target_x is None):
        cost += 256.0
    return cost


def _align_actions(
    reference: list[TransitionV1],
    candidate: list[TransitionV1],
) -> list[_AlignedAction]:
    buckets: dict[tuple[int, str], list[int]] = {}
    for index, transition in enumerate(reference):
        key = (transition.action.frame, transition.action.action_type)
        buckets.setdefault(key, []).append(index)

    used: set[int] = set()
    aligned: list[_AlignedAction] = []
    for transition in candidate:
        key = (transition.action.frame, transition.action.action_type)
        choices = [index for index in buckets.get(key, []) if index not in used]
        if not choices:
            continue
        best = min(
            choices,
            key=lambda index: _action_cost(reference[index].action, transition.action),
        )
        used.add(best)
        aligned.append(_AlignedAction(reference=reference[best], candidate=transition))
    return aligned


def _visible_units(observation: ObservationV1) -> list[UnitObservationV1]:
    return [unit for unit in observation.units if unit.visible]


def _match_units(
    reference: ObservationV1,
    candidate: ObservationV1,
) -> tuple[int, int, int, list[float], list[float]]:
    reference_units = _visible_units(reference)
    candidate_units = _visible_units(candidate)

    reference_groups: dict[tuple[str, int], list[UnitObservationV1]] = {}
    candidate_groups: dict[tuple[str, int], list[UnitObservationV1]] = {}
    for unit in reference_units:
        reference_groups.setdefault((unit.owner, unit.type_id), []).append(unit)
    for unit in candidate_units:
        candidate_groups.setdefault((unit.owner, unit.type_id), []).append(unit)

    matched = 0
    position_errors: list[float] = []
    hp_errors: list[float] = []
    keys = set(reference_groups) | set(candidate_groups)
    for key in keys:
        left = reference_groups.get(key, [])
        right = candidate_groups.get(key, [])
        pairs = sorted(
            (
                (math.hypot(a.x - b.x, a.y - b.y), i, j)
                for i, a in enumerate(left)
                for j, b in enumerate(right)
            ),
            key=lambda item: item[0],
        )
        left_used: set[int] = set()
        right_used: set[int] = set()
        for distance, left_index, right_index in pairs:
            if left_index in left_used or right_index in right_used:
                continue
            left_used.add(left_index)
            right_used.add(right_index)
            matched += 1
            position_errors.append(distance)
            hp_errors.append(abs(left[left_index].hp - right[right_index].hp))
            if len(left_used) == len(left) or len(right_used) == len(right):
                break

    return (
        len(reference_units),
        len(candidate_units),
        matched,
        position_errors,
        hp_errors,
    )


def _mae(values: list[float]) -> float:
    return mean(values) if values else 0.0


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def _state_pairs(aligned: list[_AlignedAction]) -> list[tuple[ObservationV1, ObservationV1]]:
    pairs: dict[tuple[int, int], tuple[ObservationV1, ObservationV1]] = {}
    for item in aligned:
        candidates = (
            (item.reference.observation, item.candidate.observation),
            (item.reference.next_observation, item.candidate.next_observation),
        )
        for reference, candidate in candidates:
            pairs.setdefault((reference.frame, candidate.frame), (reference, candidate))
    return list(pairs.values())


def compare_backends(
    reference_path: Path,
    candidate_path: Path,
    *,
    policy: BackendComparisonPolicy | None = None,
) -> BackendComparisonResult:
    active_policy = policy or BackendComparisonPolicy()
    reference = list(iter_jsonl_v1(reference_path))
    candidate = list(iter_jsonl_v1(candidate_path))
    if not reference or not candidate:
        raise ValueError("both backends must contain at least one transition")

    aligned = _align_actions(reference, candidate)
    reference_alignment = len(aligned) / len(reference)
    candidate_alignment = len(aligned) / len(candidate)

    actor_errors = [
        abs(len(item.reference.action.actor_unit_ids) - len(item.candidate.action.actor_unit_ids))
        for item in aligned
    ]
    target_errors = [
        distance
        for item in aligned
        if (distance := _target_position_distance(item.reference.action, item.candidate.action))
        is not None
    ]

    states = _state_pairs(aligned)
    frame_errors: list[float] = []
    minerals_errors: list[float] = []
    gas_errors: list[float] = []
    supply_used_errors: list[float] = []
    supply_total_errors: list[float] = []
    position_errors: list[float] = []
    hp_errors: list[float] = []
    reference_visible = 0
    candidate_visible = 0
    matched_visible = 0

    for reference_state, candidate_state in states:
        frame_errors.append(abs(reference_state.frame - candidate_state.frame))
        minerals_errors.append(abs(reference_state.minerals - candidate_state.minerals))
        gas_errors.append(abs(reference_state.gas - candidate_state.gas))
        supply_used_errors.append(abs(reference_state.supply_used - candidate_state.supply_used))
        supply_total_errors.append(abs(reference_state.supply_total - candidate_state.supply_total))

        ref_count, cand_count, matched, positions, hitpoints = _match_units(
            reference_state,
            candidate_state,
        )
        reference_visible += ref_count
        candidate_visible += cand_count
        matched_visible += matched
        position_errors.extend(positions)
        hp_errors.extend(hitpoints)

    precision = matched_visible / candidate_visible if candidate_visible else 1.0
    recall = matched_visible / reference_visible if reference_visible else 1.0

    metrics = {
        "aligned_actions": len(aligned),
        "reference_action_alignment": reference_alignment,
        "candidate_action_alignment": candidate_alignment,
        "actor_count_mae": _mae([float(value) for value in actor_errors]),
        "action_target_position_mae": _mae(target_errors),
        "state_frame_delta_mae": _mae(frame_errors),
        "visible_unit_precision": precision,
        "visible_unit_recall": recall,
        "unit_position_mae": _mae(position_errors),
        "unit_hp_mae": _mae(hp_errors),
        "minerals_mae": _mae(minerals_errors),
        "gas_mae": _mae(gas_errors),
        "supply_used_mae": _mae(supply_used_errors),
        "supply_total_mae": _mae(supply_total_errors),
    }

    failures: list[str] = []
    checks = (
        (
            metrics["aligned_actions"] >= active_policy.min_aligned_actions,
            "too few aligned actions",
        ),
        (
            metrics["reference_action_alignment"] >= active_policy.min_action_alignment,
            "reference action alignment below threshold",
        ),
        (
            metrics["candidate_action_alignment"] >= active_policy.min_action_alignment,
            "candidate action alignment below threshold",
        ),
        (
            metrics["actor_count_mae"] <= active_policy.max_actor_count_mae,
            "actor-count MAE above threshold",
        ),
        (
            metrics["action_target_position_mae"]
            <= active_policy.max_action_target_position_mae,
            "action target-position MAE above threshold",
        ),
        (
            metrics["visible_unit_precision"] >= active_policy.min_visible_unit_precision,
            "visible-unit precision below threshold",
        ),
        (
            metrics["visible_unit_recall"] >= active_policy.min_visible_unit_recall,
            "visible-unit recall below threshold",
        ),
        (
            metrics["unit_position_mae"] <= active_policy.max_unit_position_mae,
            "unit-position MAE above threshold",
        ),
        (
            metrics["unit_hp_mae"] <= active_policy.max_unit_hp_mae,
            "unit HP MAE above threshold",
        ),
        (
            metrics["minerals_mae"] <= active_policy.max_minerals_mae,
            "minerals MAE above threshold",
        ),
        (
            metrics["gas_mae"] <= active_policy.max_gas_mae,
            "gas MAE above threshold",
        ),
        (
            metrics["supply_used_mae"] <= active_policy.max_supply_used_mae,
            "supply-used MAE above threshold",
        ),
        (
            metrics["supply_total_mae"] <= active_policy.max_supply_total_mae,
            "supply-total MAE above threshold",
        ),
        (
            metrics["state_frame_delta_mae"] <= active_policy.max_state_frame_delta,
            "state-frame delta above threshold",
        ),
    )
    failures.extend(message for passed, message in checks if not passed)

    return BackendComparisonResult(
        reference_transitions=len(reference),
        candidate_transitions=len(candidate),
        aligned_actions=len(aligned),
        reference_action_alignment=reference_alignment,
        candidate_action_alignment=candidate_alignment,
        actor_count_mae=metrics["actor_count_mae"],
        action_target_position_mae=metrics["action_target_position_mae"],
        state_frames_compared=len(states),
        state_frame_delta_mae=metrics["state_frame_delta_mae"],
        visible_unit_precision=precision,
        visible_unit_recall=recall,
        matched_visible_units=matched_visible,
        unit_position_mae=metrics["unit_position_mae"],
        unit_position_p95=_p95(position_errors),
        unit_hp_mae=metrics["unit_hp_mae"],
        minerals_mae=metrics["minerals_mae"],
        gas_mae=metrics["gas_mae"],
        supply_used_mae=metrics["supply_used_mae"],
        supply_total_mae=metrics["supply_total_mae"],
        promotion_eligible=not failures,
        promotion_failures=tuple(failures),
    )
