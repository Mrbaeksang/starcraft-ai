from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import torch
from torch import Tensor


class SequenceScorer(Protocol):
    action_types: int
    action_features: int

    def score(
        self,
        initial_state: Tensor,
        action_type_sequence: Tensor,
        action_feature_sequence: Tensor,
        *,
        discount: float,
        uncertainty_penalty: float,
    ) -> Tensor: ...


@dataclass(frozen=True, slots=True)
class PlanResult:
    action_type: Tensor
    action_features: Tensor
    sequence_action_types: Tensor
    sequence_action_features: Tensor
    score: Tensor


class WorldModelSequenceScorer:
    """Scores imagined action sequences with one or more latent world models."""

    def __init__(self, models: list[torch.nn.Module]) -> None:
        if not models:
            raise ValueError("at least one world model is required")
        self.models = models
        first = models[0]
        self.action_types = first.config.action_types
        self.action_features = first.config.action_features
        for model in models[1:]:
            if model.config.action_types != self.action_types:
                raise ValueError("ensemble action_types must match")
            if model.config.action_features != self.action_features:
                raise ValueError("ensemble action_features must match")

    @torch.no_grad()
    def score(
        self,
        initial_state: Tensor,
        action_type_sequence: Tensor,
        action_feature_sequence: Tensor,
        *,
        discount: float,
        uncertainty_penalty: float,
    ) -> Tensor:
        if action_type_sequence.ndim != 2:
            raise ValueError("action_type_sequence must have [population, horizon]")
        if action_feature_sequence.ndim != 3:
            raise ValueError("action_feature_sequence must have [population, horizon, features]")
        population, horizon = action_type_sequence.shape
        if action_feature_sequence.shape != (population, horizon, self.action_features):
            raise ValueError("action feature sequence shape mismatch")
        if initial_state.ndim != 1:
            raise ValueError("initial_state must be a single latent vector")
        if not 0.0 < discount <= 1.0:
            raise ValueError("discount must be in (0, 1]")
        if uncertainty_penalty < 0:
            raise ValueError("uncertainty_penalty must be non-negative")

        latents = [initial_state.unsqueeze(0).expand(population, -1).clone() for _ in self.models]
        total = torch.zeros(population, device=initial_state.device)
        weight = 1.0

        for step in range(horizon):
            next_latents: list[Tensor] = []
            rewards: list[Tensor] = []
            for model, latent in zip(self.models, latents, strict=True):
                predicted = model.predict_from_latent(
                    latent,
                    action_type_sequence[:, step],
                    action_feature_sequence[:, step],
                )
                next_latents.append(predicted)
                rewards.append(model.reward_head(predicted).squeeze(-1))

            reward_stack = torch.stack(rewards, dim=0)
            mean_reward = reward_stack.mean(dim=0)

            if len(next_latents) > 1:
                latent_stack = torch.stack(next_latents, dim=0)
                latent_uncertainty = latent_stack.var(dim=0, unbiased=False).mean(dim=-1)
                reward_uncertainty = reward_stack.var(dim=0, unbiased=False)
                uncertainty = latent_uncertainty + reward_uncertainty
            else:
                uncertainty = torch.zeros_like(mean_reward)

            total = total + weight * (mean_reward - uncertainty_penalty * uncertainty)
            weight *= discount
            latents = next_latents

        return total


class BrokenSequenceScorer:
    """Negative control that deliberately breaks state/action dependence."""

    def __init__(self, *, action_types: int, action_features: int) -> None:
        self.action_types = action_types
        self.action_features = action_features

    def score(
        self,
        initial_state: Tensor,
        action_type_sequence: Tensor,
        action_feature_sequence: Tensor,
        *,
        discount: float,
        uncertainty_penalty: float,
    ) -> Tensor:
        del initial_state, action_feature_sequence, discount, uncertainty_penalty
        return torch.zeros(
            action_type_sequence.shape[0],
            dtype=torch.float32,
            device=action_type_sequence.device,
        )


def _validate_search(
    scorer: SequenceScorer,
    initial_state: Tensor,
    *,
    horizon: int,
    population: int,
) -> None:
    if initial_state.ndim != 1:
        raise ValueError("initial_state must be one-dimensional")
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if population < 1:
        raise ValueError("population must be >= 1")
    if scorer.action_types < 1 or scorer.action_features < 1:
        raise ValueError("scorer action dimensions must be positive")


@torch.no_grad()
def random_shooting(
    scorer: SequenceScorer,
    initial_state: Tensor,
    *,
    horizon: int = 4,
    population: int = 256,
    discount: float = 0.99,
    uncertainty_penalty: float = 0.1,
    seed: int = 7,
) -> PlanResult:
    _validate_search(scorer, initial_state, horizon=horizon, population=population)
    generator = torch.Generator(device=initial_state.device)
    generator.manual_seed(seed)

    action_types = torch.randint(
        0,
        scorer.action_types,
        (population, horizon),
        generator=generator,
        device=initial_state.device,
    )
    action_features = torch.empty(
        population,
        horizon,
        scorer.action_features,
        device=initial_state.device,
    ).uniform_(-1.0, 1.0, generator=generator)

    scores = scorer.score(
        initial_state,
        action_types,
        action_features,
        discount=discount,
        uncertainty_penalty=uncertainty_penalty,
    )
    best = int(torch.argmax(scores).item())
    return PlanResult(
        action_type=action_types[best, 0].clone(),
        action_features=action_features[best, 0].clone(),
        sequence_action_types=action_types[best].clone(),
        sequence_action_features=action_features[best].clone(),
        score=scores[best].clone(),
    )


@torch.no_grad()
def cem_plan(
    scorer: SequenceScorer,
    initial_state: Tensor,
    *,
    horizon: int = 4,
    population: int = 256,
    elite_fraction: float = 0.1,
    iterations: int = 4,
    discount: float = 0.99,
    uncertainty_penalty: float = 0.1,
    seed: int = 7,
) -> PlanResult:
    _validate_search(scorer, initial_state, horizon=horizon, population=population)
    if not 0.0 < elite_fraction <= 1.0:
        raise ValueError("elite_fraction must be in (0, 1]")
    if iterations < 1:
        raise ValueError("iterations must be >= 1")

    elite_count = max(1, int(population * elite_fraction))
    generator = torch.Generator(device=initial_state.device)
    generator.manual_seed(seed)

    type_probabilities = torch.full(
        (horizon, scorer.action_types),
        1.0 / scorer.action_types,
        device=initial_state.device,
    )
    feature_mean = torch.zeros(
        horizon,
        scorer.action_features,
        device=initial_state.device,
    )
    feature_std = torch.ones_like(feature_mean)

    best_score = torch.tensor(float("-inf"), device=initial_state.device)
    best_types = torch.zeros(horizon, dtype=torch.long, device=initial_state.device)
    best_features = torch.zeros_like(feature_mean)

    for _ in range(iterations):
        sampled_types = torch.multinomial(
            type_probabilities,
            population,
            replacement=True,
            generator=generator,
        ).T.contiguous()
        noise = torch.randn(
            population,
            horizon,
            scorer.action_features,
            generator=generator,
            device=initial_state.device,
        )
        sampled_features = (feature_mean.unsqueeze(0) + feature_std.unsqueeze(0) * noise).clamp(
            -1.0, 1.0
        )

        scores = scorer.score(
            initial_state,
            sampled_types,
            sampled_features,
            discount=discount,
            uncertainty_penalty=uncertainty_penalty,
        )
        elite_indices = torch.topk(scores, elite_count).indices
        elite_types = sampled_types[elite_indices]
        elite_features = sampled_features[elite_indices]

        for step in range(horizon):
            counts = torch.bincount(
                elite_types[:, step],
                minlength=scorer.action_types,
            ).float()
            type_probabilities[step] = (counts + 0.5) / (counts.sum() + 0.5 * scorer.action_types)

        feature_mean = elite_features.mean(dim=0)
        feature_std = elite_features.std(dim=0, unbiased=False).clamp_min(0.05)

        iteration_best = int(torch.argmax(scores).item())
        if scores[iteration_best] > best_score:
            best_score = scores[iteration_best].clone()
            best_types = sampled_types[iteration_best].clone()
            best_features = sampled_features[iteration_best].clone()

    return PlanResult(
        action_type=best_types[0].clone(),
        action_features=best_features[0].clone(),
        sequence_action_types=best_types,
        sequence_action_features=best_features,
        score=best_score,
    )


def receding_horizon_action(plan: PlanResult) -> tuple[int, Tensor]:
    """Return only the first action; call the planner again after the next observation."""
    return int(plan.action_type.item()), plan.action_features.clone()
