from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import numpy as np

from starcraft_ai.data.schema import EpisodeMetadataV1, TransitionV1

ACTION_INDEX = {
    "NOOP": 0,
    "MOVE": 1,
    "ATTACK_UNIT": 2,
    "ATTACK_MOVE": 3,
    "RIGHT_CLICK": 4,
    "STOP": 5,
    "HOLD": 6,
    "TRAIN": 7,
    "BUILD": 8,
    "MORPH": 9,
    "RESEARCH": 10,
    "UPGRADE": 11,
}
OWNER_INDEX = {"self": 0, "enemy": 1, "neutral": 2}
POSITION_INDEX = {"current": 0, "last_seen": 1}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_jsonl_v1(path: Path, transitions: Iterable[TransitionV1]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for transition in transitions:
            handle.write(transition.canonical_json())
            handle.write("\n")
            count += 1
    return count


def iter_jsonl_v1(path: Path) -> Iterator[TransitionV1]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            value = line.strip()
            if not value:
                continue
            try:
                yield TransitionV1.from_json(value)
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                raise ValueError(f"{path}:{line_number}: {error}") from error


def build_manifest_v1(
    *,
    dataset_id: str,
    episode: EpisodeMetadataV1,
    jsonl_path: Path,
    transition_count: int,
) -> dict[str, Any]:
    if transition_count < 0:
        raise ValueError("transition_count must be non-negative")
    return {
        "schema_version": 1,
        "dataset_id": dataset_id,
        "format": "transition-jsonl-v1",
        "transition_count": transition_count,
        "episodes": [episode.to_dict()],
        "files": [
            {
                "path": jsonl_path.name,
                "bytes": jsonl_path.stat().st_size,
                "sha256": sha256_file(jsonl_path),
                "transitions": transition_count,
            }
        ],
    }


def _unit_rows(transition: TransitionV1, *, next_state: bool) -> list[list[float]]:
    observation = transition.next_observation if next_state else transition.observation
    rows: list[list[float]] = []
    for unit in observation.units:
        rows.append(
            [
                float(unit.unit_id),
                float(unit.type_id),
                float(OWNER_INDEX[unit.owner]),
                float(unit.x),
                float(unit.y),
                float(unit.hp),
                float(unit.hp_max),
                float(unit.shields),
                float(unit.energy),
                float(unit.order_id),
                float(unit.visible),
                float(POSITION_INDEX[unit.position_source]),
                float(unit.last_seen_frame if unit.last_seen_frame is not None else -1),
            ]
        )
    return rows


def _global_row(transition: TransitionV1, *, next_state: bool) -> list[float]:
    observation = transition.next_observation if next_state else transition.observation
    return [
        float(observation.frame),
        float(observation.player_id),
        float(observation.minerals),
        float(observation.gas),
        float(observation.supply_used),
        float(observation.supply_total),
        float(observation.map_width),
        float(observation.map_height),
        float(observation.explored_fraction),
    ]


def pack_npz_v1(path: Path, transitions: Iterable[TransitionV1]) -> int:
    materialized = list(transitions)
    path.parent.mkdir(parents=True, exist_ok=True)

    observation_units: list[list[float]] = []
    next_units: list[list[float]] = []
    observation_offsets = [0]
    next_offsets = [0]

    for transition in materialized:
        observation_units.extend(_unit_rows(transition, next_state=False))
        next_units.extend(_unit_rows(transition, next_state=True))
        observation_offsets.append(len(observation_units))
        next_offsets.append(len(next_units))

    actions = np.zeros((len(materialized), 7), dtype=np.float32)
    for index, transition in enumerate(materialized):
        action = transition.action
        actions[index] = [
            float(ACTION_INDEX[action.action_type]),
            float(len(action.actor_unit_ids)),
            float(action.target_unit_id if action.target_unit_id is not None else -1),
            float(action.target_x if action.target_x is not None else -1),
            float(action.target_y if action.target_y is not None else -1),
            float(action.argument_type_id if action.argument_type_id is not None else -1),
            float(action.frame),
        ]

    np.savez_compressed(
        path,
        format_version=np.asarray([1], dtype=np.int32),
        observation_global=np.asarray(
            [_global_row(item, next_state=False) for item in materialized],
            dtype=np.float32,
        ),
        next_observation_global=np.asarray(
            [_global_row(item, next_state=True) for item in materialized],
            dtype=np.float32,
        ),
        observation_units=np.asarray(observation_units, dtype=np.float32).reshape(-1, 13),
        next_observation_units=np.asarray(next_units, dtype=np.float32).reshape(-1, 13),
        observation_unit_offsets=np.asarray(observation_offsets, dtype=np.int64),
        next_observation_unit_offsets=np.asarray(next_offsets, dtype=np.int64),
        actions=actions,
        rewards=np.asarray([item.reward for item in materialized], dtype=np.float32),
        terminals=np.asarray([item.terminal for item in materialized], dtype=np.bool_),
    )
    return len(materialized)


def load_npz_v1(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        version = archive["format_version"]
        if version.shape != (1,) or int(version[0]) != 1:
            raise ValueError("unsupported packed dataset format_version")
        return {key: archive[key].copy() for key in archive.files}
