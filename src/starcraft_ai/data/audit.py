from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from starcraft_ai.data.io import iter_jsonl_v1, sha256_file
from starcraft_ai.data.schema import TransitionV1


@dataclass(frozen=True, slots=True)
class DatasetAuditResult:
    path: str
    file_sha256: str
    canonical_sha256: str
    transitions: int
    episodes: int
    visible_enemy_records: int
    hidden_enemy_memory_records: int
    min_frame: int
    max_frame: int


@dataclass(frozen=True, slots=True)
class LoaderBenchmark:
    path: str
    repeats: int
    transitions: int
    elapsed_seconds: float
    transitions_per_second: float


def canonical_dataset_hash(transitions: list[TransitionV1]) -> str:
    digest = hashlib.sha256()
    for transition in transitions:
        digest.update(transition.canonical_json().encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def validate_sequence(transitions: list[TransitionV1]) -> None:
    if not transitions:
        raise ValueError("dataset contains no transitions")

    episodes: dict[str, list[TransitionV1]] = {}
    for transition in transitions:
        episodes.setdefault(transition.episode_id, []).append(transition)

    for episode_id, episode in episodes.items():
        ordered = sorted(episode, key=lambda item: item.step)
        expected_steps = list(range(len(ordered)))
        actual_steps = [item.step for item in ordered]
        if actual_steps != expected_steps:
            raise ValueError(
                f"{episode_id}: transition steps must be contiguous from zero; "
                f"got {actual_steps[:8]}"
            )

        previous_frame = -1
        for transition in ordered:
            if transition.observation.frame < previous_frame:
                raise ValueError(f"{episode_id}: observation frames are not monotonic")
            previous_frame = transition.observation.frame


def audit_jsonl(path: Path) -> DatasetAuditResult:
    transitions = list(iter_jsonl_v1(path))
    validate_sequence(transitions)

    visible_enemy = 0
    hidden_enemy = 0
    frames: list[int] = []

    for transition in transitions:
        for observation in (transition.observation, transition.next_observation):
            frames.append(observation.frame)
            for unit in observation.units:
                if unit.owner != "enemy":
                    continue
                if unit.visible:
                    visible_enemy += 1
                else:
                    if unit.position_source != "last_seen" or unit.last_seen_frame is None:
                        raise ValueError(
                            "hidden enemy state leaked a non-last-seen position"
                        )
                    hidden_enemy += 1

    return DatasetAuditResult(
        path=str(path),
        file_sha256=sha256_file(path),
        canonical_sha256=canonical_dataset_hash(transitions),
        transitions=len(transitions),
        episodes=len({item.episode_id for item in transitions}),
        visible_enemy_records=visible_enemy,
        hidden_enemy_memory_records=hidden_enemy,
        min_frame=min(frames),
        max_frame=max(frames),
    )


def compare_extractions(
    first: Path,
    second: Path,
) -> tuple[bool, DatasetAuditResult, DatasetAuditResult]:
    first_audit = audit_jsonl(first)
    second_audit = audit_jsonl(second)
    identical = (
        first_audit.canonical_sha256 == second_audit.canonical_sha256
        and first_audit.transitions == second_audit.transitions
    )
    return identical, first_audit, second_audit


def episode_split(
    episode_ids: list[str],
    *,
    seed: int = 7,
    train_fraction: float = 0.8,
    validation_fraction: float = 0.1,
) -> dict[str, str]:
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be in (0, 1)")
    if not 0.0 <= validation_fraction < 1.0:
        raise ValueError("validation_fraction must be in [0, 1)")
    if train_fraction + validation_fraction >= 1.0:
        raise ValueError("train + validation fractions must be < 1")

    assignments: dict[str, str] = {}
    for episode_id in sorted(set(episode_ids)):
        digest = hashlib.sha256(f"{seed}:{episode_id}".encode()).digest()
        bucket = int.from_bytes(digest[:8], "big") / float(2**64)
        if bucket < train_fraction:
            split = "train"
        elif bucket < train_fraction + validation_fraction:
            split = "validation"
        else:
            split = "test"
        assignments[episode_id] = split
    return assignments


def benchmark_loader(path: Path, *, repeats: int = 3) -> LoaderBenchmark:
    if repeats < 1:
        raise ValueError("repeats must be >= 1")

    started = time.perf_counter()
    transitions = 0
    for _ in range(repeats):
        count = sum(1 for _ in iter_jsonl_v1(path))
        if transitions == 0:
            transitions = count
        elif count != transitions:
            raise RuntimeError("loader returned inconsistent transition counts")
    elapsed = time.perf_counter() - started
    total = transitions * repeats

    return LoaderBenchmark(
        path=str(path),
        repeats=repeats,
        transitions=transitions,
        elapsed_seconds=elapsed,
        transitions_per_second=total / max(elapsed, 1e-9),
    )


def audit_to_dict(result: DatasetAuditResult) -> dict[str, object]:
    return asdict(result)


def benchmark_to_dict(result: LoaderBenchmark) -> dict[str, object]:
    return asdict(result)
