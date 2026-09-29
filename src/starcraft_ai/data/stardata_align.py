from __future__ import annotations

import bisect
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class StarDataAlignmentResult:
    states: int
    actions: int
    aligned_actions: int
    dropped_before_first_state: int
    dropped_after_last_state: int
    intervals_with_actions: int
    max_actions_per_interval: int
    max_before_gap: int
    max_after_gap: int
    selected_actor_refs: int
    raw_actor_id_matches: int
    raw_actor_owner_matches: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            value = line.strip()
            if not value:
                continue
            payload = json.loads(value)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            rows.append(payload)
    return rows


def _validate_states(states: list[dict[str, Any]]) -> list[int]:
    if len(states) < 2:
        raise ValueError("at least two sampled states are required")

    frames: list[int] = []
    for index, state in enumerate(states):
        if state.get("sample_index") != index:
            raise ValueError("state sample_index values must be contiguous from zero")
        frame = state.get("approx_game_frame")
        if not isinstance(frame, int) or frame < 0:
            raise ValueError("approx_game_frame must be a non-negative integer")
        frames.append(frame)

    if any(right <= left for left, right in zip(frames, frames[1:], strict=False)):
        raise ValueError("sampled state frames must be strictly increasing")
    return frames


def align_stardata_actions(
    states_path: Path,
    actions_path: Path,
    output_path: Path,
) -> StarDataAlignmentResult:
    states = _read_jsonl(states_path)
    actions = _read_jsonl(actions_path)
    state_frames = _validate_states(states)

    aligned: list[dict[str, Any]] = []
    dropped_before = 0
    dropped_after = 0
    interval_counts: dict[int, int] = {}
    before_gaps: list[int] = []
    after_gaps: list[int] = []
    selected_actor_refs = 0
    raw_actor_id_matches = 0
    raw_actor_owner_matches = 0

    previous_key: tuple[int, int] | None = None
    for fallback_ordinal, action in enumerate(actions):
        frame = action.get("frame")
        if not isinstance(frame, int) or frame < 0:
            raise ValueError("action frame must be a non-negative integer")
        ordinal = action.get("ordinal", fallback_ordinal)
        if not isinstance(ordinal, int) or ordinal < 0:
            raise ValueError("action ordinal must be a non-negative integer")

        key = (frame, ordinal)
        if previous_key is not None and key < previous_key:
            raise ValueError("actions must be ordered by frame/ordinal")
        previous_key = key

        state_index = bisect.bisect_right(state_frames, frame) - 1
        if state_index < 0:
            dropped_before += 1
            continue
        if state_index + 1 >= len(states):
            dropped_after += 1
            continue

        state_frame = state_frames[state_index]
        next_state_frame = state_frames[state_index + 1]
        before_gap = frame - state_frame
        after_gap = next_state_frame - frame
        before_gaps.append(before_gap)
        after_gaps.append(after_gap)
        interval_counts[state_index] = interval_counts.get(state_index, 0) + 1

        # These IDs come from different extractors. Count exact overlaps as a
        # diagnostic only; even a match does not certify a shared ID namespace.
        unit_owners = {
            unit["unit_id"]: unit["player_id"] for unit in states[state_index].get("units", [])
        }
        for actor_tag in action.get("selected_unit_tags", []):
            selected_actor_refs += 1
            if actor_tag in unit_owners:
                raw_actor_id_matches += 1
                if unit_owners[actor_tag] == action.get("player_id"):
                    raw_actor_owner_matches += 1

        aligned.append(
            {
                "schema_version": 1,
                "action_ordinal": ordinal,
                "action_frame": frame,
                "player_id": action.get("player_id"),
                "selected_unit_tags": action.get("selected_unit_tags", []),
                "command": action.get("command"),
                "state_sample_index": state_index,
                "state_frame": state_frame,
                "next_state_sample_index": state_index + 1,
                "next_state_frame": next_state_frame,
                "before_gap": before_gap,
                "after_gap": after_gap,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in aligned:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            handle.write("\n")

    return StarDataAlignmentResult(
        states=len(states),
        actions=len(actions),
        aligned_actions=len(aligned),
        dropped_before_first_state=dropped_before,
        dropped_after_last_state=dropped_after,
        intervals_with_actions=len(interval_counts),
        max_actions_per_interval=max(interval_counts.values(), default=0),
        max_before_gap=max(before_gaps, default=0),
        max_after_gap=max(after_gaps, default=0),
        selected_actor_refs=selected_actor_refs,
        raw_actor_id_matches=raw_actor_id_matches,
        raw_actor_owner_matches=raw_actor_owner_matches,
    )
