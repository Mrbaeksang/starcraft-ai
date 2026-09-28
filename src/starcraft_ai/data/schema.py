from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal


SCHEMA_VERSION = 1
OwnerRelation = Literal["self", "enemy", "neutral"]
PositionSource = Literal["current", "last_seen"]
ObservabilityMode = Literal["player", "privileged"]
ActionType = Literal[
    "NOOP",
    "MOVE",
    "ATTACK_UNIT",
    "ATTACK_MOVE",
    "RIGHT_CLICK",
    "STOP",
    "HOLD",
    "TRAIN",
    "BUILD",
    "MORPH",
    "RESEARCH",
    "UPGRADE",
]


def _strict_keys(data: Mapping[str, Any], expected: set[str], label: str) -> None:
    unknown = set(data) - expected
    missing = expected - set(data)
    if unknown:
        raise ValueError(f"{label}: unknown fields: {sorted(unknown)}")
    if missing:
        raise ValueError(f"{label}: missing fields: {sorted(missing)}")


def _non_negative(value: int, field: str) -> None:
    if value < 0:
        raise ValueError(f"{field} must be >= 0")


def canonical_json(data: Mapping[str, Any]) -> str:
    return json.dumps(
        data,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass(frozen=True, slots=True)
class EpisodeMetadataV1:
    episode_id: str
    source: str
    map_name: str
    player_id: int
    race: str
    opponent_race: str
    observability: ObservabilityMode
    replay_sha256: str | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported EpisodeMetadataV1 schema_version")
        if not self.episode_id.strip():
            raise ValueError("episode_id must not be empty")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        _non_negative(self.player_id, "player_id")
        if self.observability not in {"player", "privileged"}:
            raise ValueError("observability must be 'player' or 'privileged'")
        if self.replay_sha256 is not None:
            digest = self.replay_sha256.lower()
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError("replay_sha256 must be a 64-character hexadecimal digest")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "source": self.source,
            "map_name": self.map_name,
            "player_id": self.player_id,
            "race": self.race,
            "opponent_race": self.opponent_race,
            "observability": self.observability,
            "replay_sha256": self.replay_sha256,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EpisodeMetadataV1:
        expected = {
            "schema_version",
            "episode_id",
            "source",
            "map_name",
            "player_id",
            "race",
            "opponent_race",
            "observability",
            "replay_sha256",
        }
        _strict_keys(data, expected, "EpisodeMetadataV1")
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class UnitObservationV1:
    unit_id: int
    type_id: int
    owner: OwnerRelation
    x: int
    y: int
    hp: int
    hp_max: int
    shields: int
    energy: int
    order_id: int
    visible: bool
    position_source: PositionSource
    last_seen_frame: int | None

    def __post_init__(self) -> None:
        for field, value in (
            ("unit_id", self.unit_id),
            ("type_id", self.type_id),
            ("x", self.x),
            ("y", self.y),
            ("hp", self.hp),
            ("hp_max", self.hp_max),
            ("shields", self.shields),
            ("energy", self.energy),
            ("order_id", self.order_id),
        ):
            _non_negative(value, field)
        if self.hp > self.hp_max:
            raise ValueError("hp cannot exceed hp_max")
        if self.owner not in {"self", "enemy", "neutral"}:
            raise ValueError("owner must be self, enemy, or neutral")
        if self.position_source not in {"current", "last_seen"}:
            raise ValueError("position_source must be current or last_seen")
        if self.visible:
            if self.position_source != "current":
                raise ValueError("visible units must use current position")
            if self.last_seen_frame is not None:
                raise ValueError("visible units must not carry last_seen_frame")
        elif self.owner == "enemy":
            if self.position_source != "last_seen" or self.last_seen_frame is None:
                raise ValueError(
                    "hidden enemy units may only expose an explicitly last-seen position"
                )
            _non_negative(self.last_seen_frame, "last_seen_frame")
        elif self.position_source == "last_seen" and self.last_seen_frame is None:
            raise ValueError("last_seen position requires last_seen_frame")

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "type_id": self.type_id,
            "owner": self.owner,
            "x": self.x,
            "y": self.y,
            "hp": self.hp,
            "hp_max": self.hp_max,
            "shields": self.shields,
            "energy": self.energy,
            "order_id": self.order_id,
            "visible": self.visible,
            "position_source": self.position_source,
            "last_seen_frame": self.last_seen_frame,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> UnitObservationV1:
        expected = {
            "unit_id",
            "type_id",
            "owner",
            "x",
            "y",
            "hp",
            "hp_max",
            "shields",
            "energy",
            "order_id",
            "visible",
            "position_source",
            "last_seen_frame",
        }
        _strict_keys(data, expected, "UnitObservationV1")
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class ObservationV1:
    frame: int
    player_id: int
    minerals: int
    gas: int
    supply_used: int
    supply_total: int
    map_width: int
    map_height: int
    explored_fraction: float
    upgrades: tuple[int, ...]
    techs: tuple[int, ...]
    units: tuple[UnitObservationV1, ...]
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported ObservationV1 schema_version")
        for field, value in (
            ("frame", self.frame),
            ("player_id", self.player_id),
            ("minerals", self.minerals),
            ("gas", self.gas),
            ("supply_used", self.supply_used),
            ("supply_total", self.supply_total),
        ):
            _non_negative(value, field)
        if self.supply_used > self.supply_total:
            raise ValueError("supply_used cannot exceed supply_total")
        if self.map_width <= 0 or self.map_height <= 0:
            raise ValueError("map dimensions must be positive")
        if not 0.0 <= self.explored_fraction <= 1.0:
            raise ValueError("explored_fraction must be in [0, 1]")
        if len({unit.unit_id for unit in self.units}) != len(self.units):
            raise ValueError("unit_id values must be unique within one observation")
        if any(value < 0 for value in self.upgrades + self.techs):
            raise ValueError("upgrade/tech ids must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "frame": self.frame,
            "player_id": self.player_id,
            "minerals": self.minerals,
            "gas": self.gas,
            "supply_used": self.supply_used,
            "supply_total": self.supply_total,
            "map_width": self.map_width,
            "map_height": self.map_height,
            "explored_fraction": self.explored_fraction,
            "upgrades": list(self.upgrades),
            "techs": list(self.techs),
            "units": [unit.to_dict() for unit in self.units],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ObservationV1:
        expected = {
            "schema_version",
            "frame",
            "player_id",
            "minerals",
            "gas",
            "supply_used",
            "supply_total",
            "map_width",
            "map_height",
            "explored_fraction",
            "upgrades",
            "techs",
            "units",
        }
        _strict_keys(data, expected, "ObservationV1")
        values = dict(data)
        values["upgrades"] = tuple(int(value) for value in data["upgrades"])
        values["techs"] = tuple(int(value) for value in data["techs"])
        values["units"] = tuple(UnitObservationV1.from_dict(unit) for unit in data["units"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ActionV1:
    frame: int
    player_id: int
    action_type: ActionType
    actor_unit_ids: tuple[int, ...]
    target_unit_id: int | None
    target_x: int | None
    target_y: int | None
    argument_type_id: int | None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported ActionV1 schema_version")
        _non_negative(self.frame, "frame")
        _non_negative(self.player_id, "player_id")
        valid_actions = {
            "NOOP",
            "MOVE",
            "ATTACK_UNIT",
            "ATTACK_MOVE",
            "RIGHT_CLICK",
            "STOP",
            "HOLD",
            "TRAIN",
            "BUILD",
            "MORPH",
            "RESEARCH",
            "UPGRADE",
        }
        if self.action_type not in valid_actions:
            raise ValueError(f"unsupported action_type: {self.action_type}")
        if len(set(self.actor_unit_ids)) != len(self.actor_unit_ids):
            raise ValueError("actor_unit_ids must be unique")
        if any(unit_id < 0 for unit_id in self.actor_unit_ids):
            raise ValueError("actor_unit_ids must be non-negative")
        if self.action_type != "NOOP" and not self.actor_unit_ids:
            raise ValueError("non-NOOP actions require at least one actor")
        if self.action_type == "NOOP" and self.actor_unit_ids:
            raise ValueError("NOOP must not contain actors")
        if (self.target_x is None) != (self.target_y is None):
            raise ValueError("target_x and target_y must be provided together")
        if self.target_unit_id is not None:
            _non_negative(self.target_unit_id, "target_unit_id")
        if self.target_x is not None:
            _non_negative(self.target_x, "target_x")
            _non_negative(self.target_y or 0, "target_y")
        if self.argument_type_id is not None:
            _non_negative(self.argument_type_id, "argument_type_id")

        if self.action_type in {"MOVE", "ATTACK_MOVE", "BUILD"} and self.target_x is None:
            raise ValueError(f"{self.action_type} requires a target position")
        if self.action_type == "ATTACK_UNIT" and self.target_unit_id is None:
            raise ValueError("ATTACK_UNIT requires target_unit_id")
        if self.action_type in {"TRAIN", "BUILD", "MORPH", "RESEARCH", "UPGRADE"}:
            if self.argument_type_id is None:
                raise ValueError(f"{self.action_type} requires argument_type_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "frame": self.frame,
            "player_id": self.player_id,
            "action_type": self.action_type,
            "actor_unit_ids": list(self.actor_unit_ids),
            "target_unit_id": self.target_unit_id,
            "target_x": self.target_x,
            "target_y": self.target_y,
            "argument_type_id": self.argument_type_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ActionV1:
        expected = {
            "schema_version",
            "frame",
            "player_id",
            "action_type",
            "actor_unit_ids",
            "target_unit_id",
            "target_x",
            "target_y",
            "argument_type_id",
        }
        _strict_keys(data, expected, "ActionV1")
        values = dict(data)
        values["actor_unit_ids"] = tuple(int(value) for value in data["actor_unit_ids"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class TransitionV1:
    episode_id: str
    step: int
    observation: ObservationV1
    action: ActionV1
    next_observation: ObservationV1
    reward: float
    terminal: bool
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported TransitionV1 schema_version")
        if not self.episode_id.strip():
            raise ValueError("episode_id must not be empty")
        _non_negative(self.step, "step")
        if self.observation.player_id != self.next_observation.player_id:
            raise ValueError("observation player_id must be stable across a transition")
        if self.action.player_id != self.observation.player_id:
            raise ValueError("action player_id must match the observation")
        if not self.observation.frame <= self.action.frame < self.next_observation.frame:
            raise ValueError("action frame must fall within [observation, next_observation)")
        if not math.isfinite(self.reward):
            raise ValueError("reward must be finite")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "step": self.step,
            "observation": self.observation.to_dict(),
            "action": self.action.to_dict(),
            "next_observation": self.next_observation.to_dict(),
            "reward": self.reward,
            "terminal": self.terminal,
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TransitionV1:
        expected = {
            "schema_version",
            "episode_id",
            "step",
            "observation",
            "action",
            "next_observation",
            "reward",
            "terminal",
        }
        _strict_keys(data, expected, "TransitionV1")
        values = dict(data)
        values["observation"] = ObservationV1.from_dict(data["observation"])
        values["action"] = ActionV1.from_dict(data["action"])
        values["next_observation"] = ObservationV1.from_dict(data["next_observation"])
        return cls(**values)

    @classmethod
    def from_json(cls, value: str) -> TransitionV1:
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("TransitionV1 JSON must contain an object")
        return cls.from_dict(parsed)
