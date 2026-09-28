from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch import nn

from starcraft_ai.data import iter_jsonl_v1, sha256_file
from starcraft_ai.data.audit import episode_split
from starcraft_ai.data.tensors import (
    ACTION_FEATURES,
    ACTION_TYPES,
    ENTITY_FEATURES,
    TransitionTensorBatch,
    transitions_to_tensors,
)
from starcraft_ai.models.baselines import DirectDynamicsMLP, RecurrentDynamicsBaseline
from starcraft_ai.models.world_model import LatentWorldModel, WorldModelConfig
from starcraft_ai.training import resolve_device


@dataclass(frozen=True, slots=True)
class TransitionTrainResult:
    model: str
    seed: int
    steps: int
    device: str
    transitions: int
    episodes: int
    train_transitions: int
    eval_transitions: int
    smoke_only: bool
    parameters: int
    first_loss: float
    final_loss: float
    eval_loss: float
    elapsed_seconds: float
    dataset_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _dataset_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda value: str(value)):
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _model(model_name: str, config: WorldModelConfig) -> nn.Module:
    if model_name == "mlp":
        return DirectDynamicsMLP(config)
    if model_name == "recurrent":
        return RecurrentDynamicsBaseline(config)
    if model_name == "jepa":
        return LatentWorldModel(config)
    raise ValueError("model must be one of: mlp, recurrent, jepa")


def _loss(model: nn.Module, batch: TransitionTensorBatch) -> torch.Tensor:
    losses = model.loss(
        entities=batch.entities,
        next_entities=batch.next_entities,
        action_type=batch.action_type,
        action_features=batch.action_features,
        reward=batch.reward,
        terminal=batch.terminal,
        entity_mask=batch.entity_mask,
        next_entity_mask=batch.next_entity_mask,
    )
    return losses["loss"]


def _indices_for_episodes(
    episode_ids: tuple[str, ...],
    wanted: set[str],
) -> torch.Tensor:
    return torch.tensor(
        [index for index, episode_id in enumerate(episode_ids) if episode_id in wanted],
        dtype=torch.long,
    )


def train_transition_dataset(
    paths: list[Path],
    *,
    model_name: str,
    steps: int,
    batch_size: int,
    seed: int,
    device_name: str,
    allow_single_episode_smoke: bool = False,
) -> TransitionTrainResult:
    if not paths:
        raise ValueError("at least one dataset path is required")
    if steps < 1:
        raise ValueError("steps must be >= 1")
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")

    transitions = [item for path in paths for item in iter_jsonl_v1(path)]
    if not transitions:
        raise ValueError("dataset contains no transitions")

    episode_ids = sorted({item.episode_id for item in transitions})
    smoke_only = len(episode_ids) < 3
    if smoke_only and not allow_single_episode_smoke:
        raise ValueError(
            "fewer than 3 episodes cannot support a held-out episode-level experiment; "
            "pass allow_single_episode_smoke=True only for pipeline validation"
        )

    tensor_data = transitions_to_tensors(transitions)
    if smoke_only:
        train_indices = torch.arange(len(transitions), dtype=torch.long)
        eval_indices = train_indices
    else:
        assignments = episode_split(episode_ids, seed=seed)
        train_episodes = {
            episode_id for episode_id, split in assignments.items() if split == "train"
        }
        eval_episodes = {
            episode_id for episode_id, split in assignments.items() if split != "train"
        }
        if not train_episodes or not eval_episodes:
            raise ValueError(
                "episode hash split produced an empty train/eval partition; "
                "use a larger dataset or a different seed"
            )
        train_indices = _indices_for_episodes(tensor_data.episode_ids, train_episodes)
        eval_indices = _indices_for_episodes(tensor_data.episode_ids, eval_episodes)

    torch.manual_seed(seed)
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    device = resolve_device(device_name)
    config = WorldModelConfig(
        entity_features=ENTITY_FEATURES,
        action_types=ACTION_TYPES,
        action_features=ACTION_FEATURES,
        model_dim=64,
        latent_dim=64,
        attention_heads=4,
        transformer_layers=2,
    )
    model = _model(model_name, config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)

    first_loss = 0.0
    final_loss = 0.0
    started = time.perf_counter()
    model.train()
    for step in range(steps):
        picks = torch.randint(
            0,
            len(train_indices),
            (min(batch_size, max(len(train_indices), 1)),),
            generator=generator,
        )
        indices = train_indices.index_select(0, picks)
        batch = tensor_data.select(indices).to(device)
        loss = _loss(model, batch)

        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        if isinstance(model, LatentWorldModel):
            model.update_target_encoder(momentum=0.99)

        value = float(loss.detach().cpu())
        if step == 0:
            first_loss = value
        final_loss = value

    model.eval()
    with torch.no_grad():
        eval_batch = tensor_data.select(eval_indices).to(device)
        eval_loss = float(_loss(model, eval_batch).detach().cpu())

    elapsed = time.perf_counter() - started
    parameters = sum(parameter.numel() for parameter in model.parameters())

    return TransitionTrainResult(
        model=model_name,
        seed=seed,
        steps=steps,
        device=str(device),
        transitions=len(transitions),
        episodes=len(episode_ids),
        train_transitions=len(train_indices),
        eval_transitions=len(eval_indices),
        smoke_only=smoke_only,
        parameters=parameters,
        first_loss=first_loss,
        final_loss=final_loss,
        eval_loss=eval_loss,
        elapsed_seconds=elapsed,
        dataset_sha256=_dataset_hash(paths),
    )
