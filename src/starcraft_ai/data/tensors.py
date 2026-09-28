from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor

from starcraft_ai.data.io import ACTION_INDEX
from starcraft_ai.data.schema import ObservationV1, TransitionV1, UnitObservationV1

ENTITY_FEATURES = 24
ACTION_FEATURES = 8
ACTION_TYPES = max(ACTION_INDEX.values()) + 1


@dataclass(frozen=True, slots=True)
class TransitionTensorBatch:
    entities: Tensor
    next_entities: Tensor
    entity_mask: Tensor
    next_entity_mask: Tensor
    action_type: Tensor
    action_features: Tensor
    reward: Tensor
    terminal: Tensor
    episode_ids: tuple[str, ...]

    def select(self, indices: Tensor) -> TransitionTensorBatch:
        cpu_indices = indices.to("cpu")
        ids = tuple(self.episode_ids[int(index)] for index in cpu_indices.tolist())
        return TransitionTensorBatch(
            entities=self.entities.index_select(0, cpu_indices),
            next_entities=self.next_entities.index_select(0, cpu_indices),
            entity_mask=self.entity_mask.index_select(0, cpu_indices),
            next_entity_mask=self.next_entity_mask.index_select(0, cpu_indices),
            action_type=self.action_type.index_select(0, cpu_indices),
            action_features=self.action_features.index_select(0, cpu_indices),
            reward=self.reward.index_select(0, cpu_indices),
            terminal=self.terminal.index_select(0, cpu_indices),
            episode_ids=ids,
        )

    def to(self, device: torch.device) -> TransitionTensorBatch:
        return TransitionTensorBatch(
            entities=self.entities.to(device),
            next_entities=self.next_entities.to(device),
            entity_mask=self.entity_mask.to(device),
            next_entity_mask=self.next_entity_mask.to(device),
            action_type=self.action_type.to(device),
            action_features=self.action_features.to(device),
            reward=self.reward.to(device),
            terminal=self.terminal.to(device),
            episode_ids=self.episode_ids,
        )


def _global_values(observation: ObservationV1, max_frame: int) -> list[float]:
    return [
        min(observation.minerals / 5000.0, 2.0),
        min(observation.gas / 5000.0, 2.0),
        min(observation.supply_used / 400.0, 2.0),
        min(observation.supply_total / 400.0, 2.0),
        observation.explored_fraction,
        observation.frame / max(max_frame, 1),
        min(observation.map_width / 256.0, 2.0),
        min(observation.map_height / 256.0, 2.0),
    ]


def _unit_features(
    unit: UnitObservationV1,
    observation: ObservationV1,
    max_frame: int,
) -> list[float]:
    width_px = max(observation.map_width * 32, 1)
    height_px = max(observation.map_height * 32, 1)
    hp_ratio = unit.hp / max(unit.hp_max, 1)
    last_seen = unit.last_seen_frame is not None
    age = (
        max(observation.frame - unit.last_seen_frame, 0) / 2400.0
        if unit.last_seen_frame is not None
        else 0.0
    )
    owners = [
        float(unit.owner == "self"),
        float(unit.owner == "enemy"),
        float(unit.owner == "neutral"),
    ]
    unit_values = [
        0.0,
        unit.type_id / 227.0,
        *owners,
        min(unit.x / width_px, 1.5),
        min(unit.y / height_px, 1.5),
        min(hp_ratio, 2.0),
        min(unit.hp_max / 2000.0, 2.0),
        min(unit.shields / 500.0, 2.0),
        min(unit.energy / 250.0, 2.0),
        unit.order_id / 255.0,
        float(unit.visible),
        float(last_seen),
        min(age, 2.0),
    ]
    return [*unit_values, *_global_values(observation, max_frame), 1.0]


def _global_token(observation: ObservationV1, max_frame: int) -> list[float]:
    unit_slots = [1.0] + [0.0] * 14
    return [*unit_slots, *_global_values(observation, max_frame), 1.0]


def _observation_rows(
    observation: ObservationV1,
    *,
    max_frame: int,
    max_units: int,
) -> list[list[float]]:
    rows = [_global_token(observation, max_frame)]
    units = sorted(
        observation.units,
        key=lambda unit: (
            unit.owner != "self",
            unit.owner != "enemy",
            not unit.visible,
            unit.unit_id,
        ),
    )
    for unit in units[: max(max_units - 1, 0)]:
        rows.append(_unit_features(unit, observation, max_frame))
    return rows


def _action_features(transition: TransitionV1, max_frame: int) -> list[float]:
    action = transition.action
    observation = transition.observation
    width_px = max(observation.map_width * 32, 1)
    height_px = max(observation.map_height * 32, 1)
    return [
        min(len(action.actor_unit_ids) / 24.0, 2.0),
        float(action.target_unit_id is not None),
        (action.target_unit_id or 0) / 65535.0,
        min((action.target_x or 0) / width_px, 1.5),
        min((action.target_y or 0) / height_px, 1.5),
        (action.argument_type_id or 0) / 227.0,
        action.frame / max(max_frame, 1),
        1.0,
    ]


def transitions_to_tensors(
    transitions: list[TransitionV1],
    *,
    max_units: int = 256,
) -> TransitionTensorBatch:
    if not transitions:
        raise ValueError("at least one transition is required")
    if max_units < 1:
        raise ValueError("max_units must be >= 1")

    max_frame = max(item.next_observation.frame for item in transitions)
    current_rows = [
        _observation_rows(item.observation, max_frame=max_frame, max_units=max_units)
        for item in transitions
    ]
    next_rows = [
        _observation_rows(item.next_observation, max_frame=max_frame, max_units=max_units)
        for item in transitions
    ]
    entity_count = max(
        1,
        max(max(len(rows) for rows in current_rows), max(len(rows) for rows in next_rows)),
    )

    entities = torch.zeros(len(transitions), entity_count, ENTITY_FEATURES)
    next_entities = torch.zeros_like(entities)
    entity_mask = torch.zeros(len(transitions), entity_count, dtype=torch.bool)
    next_entity_mask = torch.zeros_like(entity_mask)

    for index, rows in enumerate(current_rows):
        count = len(rows)
        entities[index, :count] = torch.tensor(rows, dtype=torch.float32)
        entity_mask[index, :count] = True

    for index, rows in enumerate(next_rows):
        count = len(rows)
        next_entities[index, :count] = torch.tensor(rows, dtype=torch.float32)
        next_entity_mask[index, :count] = True

    action_type = torch.tensor(
        [ACTION_INDEX[item.action.action_type] for item in transitions],
        dtype=torch.long,
    )
    action_features = torch.tensor(
        [_action_features(item, max_frame) for item in transitions],
        dtype=torch.float32,
    )
    reward = torch.tensor([item.reward for item in transitions], dtype=torch.float32)
    terminal = torch.tensor([item.terminal for item in transitions], dtype=torch.float32)

    return TransitionTensorBatch(
        entities=entities,
        next_entities=next_entities,
        entity_mask=entity_mask,
        next_entity_mask=next_entity_mask,
        action_type=action_type,
        action_features=action_features,
        reward=reward,
        terminal=terminal,
        episode_ids=tuple(item.episode_id for item in transitions),
    )
