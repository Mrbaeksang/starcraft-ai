from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor


@dataclass(frozen=True, slots=True)
class ProbeMetrics:
    economy_mae: float
    army_mae: float
    tech_mae: float
    map_control_mae: float


def synthetic_probe_targets(entities: Tensor) -> Tensor:
    """Deterministic proxy targets used only for CI research-path validation."""
    pooled = entities.mean(dim=1)
    return torch.stack(
        (
            pooled[:, 0] + pooled[:, 1],
            pooled[:, 2].abs() + pooled[:, 3].abs(),
            torch.sigmoid(pooled[:, 4]),
            torch.sigmoid(pooled[:, 5]),
        ),
        dim=-1,
    )


def linear_probe_mae(
    representation: Tensor,
    targets: Tensor,
    *,
    train_fraction: float = 0.75,
    ridge: float = 1e-3,
) -> ProbeMetrics:
    if representation.ndim != 2 or targets.ndim != 2 or targets.shape[1] != 4:
        raise ValueError("expected [batch, representation] and [batch, 4] targets")
    if representation.shape[0] != targets.shape[0]:
        raise ValueError("representation and target batch sizes must match")
    split = max(2, min(representation.shape[0] - 1, int(representation.shape[0] * train_fraction)))

    train_x = representation[:split].float()
    test_x = representation[split:].float()
    train_y = targets[:split].float()
    test_y = targets[split:].float()

    train_x = torch.cat((train_x, torch.ones_like(train_x[:, :1])), dim=1)
    test_x = torch.cat((test_x, torch.ones_like(test_x[:, :1])), dim=1)

    identity = torch.eye(train_x.shape[1], device=train_x.device, dtype=train_x.dtype)
    weights = torch.linalg.solve(
        train_x.T @ train_x + ridge * identity,
        train_x.T @ train_y,
    )
    prediction = test_x @ weights
    mae = (prediction - test_y).abs().mean(dim=0).detach().cpu().tolist()
    return ProbeMetrics(
        economy_mae=float(mae[0]),
        army_mae=float(mae[1]),
        tech_mae=float(mae[2]),
        map_control_mae=float(mae[3]),
    )


def terminal_brier(logits: Tensor, target: Tensor) -> float:
    probabilities = torch.sigmoid(logits)
    return float(((probabilities - target) ** 2).mean().detach().cpu())


def reward_mae(prediction: Tensor, target: Tensor) -> float:
    return float((prediction - target).abs().mean().detach().cpu())
