from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor, nn
from torch.nn import functional as F

from starcraft_ai.models.world_model import WorldModelConfig


def masked_mean(entities: Tensor, entity_mask: Tensor | None) -> Tensor:
    if entity_mask is None:
        return entities.mean(dim=1)
    weights = entity_mask.to(entities.dtype).unsqueeze(-1)
    return (entities * weights).sum(dim=1) / weights.sum(dim=1).clamp_min(1.0)


class BaselineActionEncoder(nn.Module):
    def __init__(self, config: WorldModelConfig) -> None:
        super().__init__()
        self.type_embedding = nn.Embedding(config.action_types, config.latent_dim)
        self.arguments = nn.Sequential(
            nn.Linear(config.action_features, config.latent_dim),
            nn.GELU(),
            nn.Linear(config.latent_dim, config.latent_dim),
        )

    def forward(self, action_type: Tensor, action_features: Tensor) -> Tensor:
        return self.type_embedding(action_type) + self.arguments(action_features)


@dataclass(frozen=True, slots=True)
class BaselinePrediction:
    representation: Tensor
    next_features: Tensor
    reward: Tensor
    terminal_logit: Tensor


class DirectDynamicsMLP(nn.Module):
    """Direct next-feature baseline with no recurrent state."""

    def __init__(self, config: WorldModelConfig) -> None:
        super().__init__()
        self.config = config
        self.state_encoder = nn.Sequential(
            nn.Linear(config.entity_features, config.latent_dim),
            nn.LayerNorm(config.latent_dim),
            nn.GELU(),
        )
        self.action_encoder = BaselineActionEncoder(config)
        self.dynamics = nn.Sequential(
            nn.Linear(config.latent_dim * 2, config.model_dim * 2),
            nn.GELU(),
            nn.Linear(config.model_dim * 2, config.latent_dim),
            nn.GELU(),
        )
        self.next_feature_head = nn.Linear(config.latent_dim, config.entity_features)
        self.reward_head = nn.Linear(config.latent_dim, 1)
        self.terminal_head = nn.Linear(config.latent_dim, 1)

    def encode(self, entities: Tensor, entity_mask: Tensor | None = None) -> Tensor:
        return self.state_encoder(masked_mean(entities, entity_mask))

    def step_features(
        self,
        state_features: Tensor,
        action_type: Tensor,
        action_features: Tensor,
    ) -> tuple[Tensor, Tensor]:
        state_latent = self.state_encoder(state_features)
        action_latent = self.action_encoder(action_type, action_features)
        hidden = self.dynamics(torch.cat((state_latent, action_latent), dim=-1))
        return self.next_feature_head(hidden), hidden

    def predict(
        self,
        entities: Tensor,
        action_type: Tensor,
        action_features: Tensor,
        entity_mask: Tensor | None = None,
    ) -> BaselinePrediction:
        state_features = masked_mean(entities, entity_mask)
        next_features, hidden = self.step_features(
            state_features,
            action_type,
            action_features,
        )
        return BaselinePrediction(
            representation=self.state_encoder(state_features),
            next_features=next_features,
            reward=self.reward_head(hidden).squeeze(-1),
            terminal_logit=self.terminal_head(hidden).squeeze(-1),
        )

    def loss(
        self,
        *,
        entities: Tensor,
        next_entities: Tensor,
        action_type: Tensor,
        action_features: Tensor,
        reward: Tensor,
        terminal: Tensor,
        entity_mask: Tensor | None = None,
        next_entity_mask: Tensor | None = None,
    ) -> dict[str, Tensor]:
        prediction = self.predict(entities, action_type, action_features, entity_mask)
        target = masked_mean(next_entities, next_entity_mask)
        dynamics_loss = F.mse_loss(prediction.next_features, target)
        reward_loss = F.smooth_l1_loss(prediction.reward, reward)
        terminal_loss = F.binary_cross_entropy_with_logits(
            prediction.terminal_logit,
            terminal,
        )
        total = dynamics_loss + 0.25 * reward_loss + 0.05 * terminal_loss
        return {
            "loss": total,
            "dynamics_loss": dynamics_loss,
            "reward_loss": reward_loss,
            "terminal_loss": terminal_loss,
        }


class RecurrentDynamicsBaseline(nn.Module):
    """Small GRU dynamics baseline; intentionally simpler than full Dreamer/RSSM."""

    def __init__(self, config: WorldModelConfig) -> None:
        super().__init__()
        self.config = config
        self.state_encoder = nn.Sequential(
            nn.Linear(config.entity_features, config.latent_dim),
            nn.LayerNorm(config.latent_dim),
            nn.Tanh(),
        )
        self.action_encoder = BaselineActionEncoder(config)
        self.gru = nn.GRUCell(config.latent_dim, config.latent_dim)
        self.next_feature_head = nn.Linear(config.latent_dim, config.entity_features)
        self.reward_head = nn.Linear(config.latent_dim, 1)
        self.terminal_head = nn.Linear(config.latent_dim, 1)

    def encode(self, entities: Tensor, entity_mask: Tensor | None = None) -> Tensor:
        return self.state_encoder(masked_mean(entities, entity_mask))

    def step_hidden(
        self,
        hidden: Tensor,
        action_type: Tensor,
        action_features: Tensor,
    ) -> tuple[Tensor, Tensor]:
        action_latent = self.action_encoder(action_type, action_features)
        next_hidden = self.gru(action_latent, hidden)
        return self.next_feature_head(next_hidden), next_hidden

    def predict(
        self,
        entities: Tensor,
        action_type: Tensor,
        action_features: Tensor,
        entity_mask: Tensor | None = None,
    ) -> BaselinePrediction:
        hidden = self.encode(entities, entity_mask)
        next_features, next_hidden = self.step_hidden(hidden, action_type, action_features)
        return BaselinePrediction(
            representation=hidden,
            next_features=next_features,
            reward=self.reward_head(next_hidden).squeeze(-1),
            terminal_logit=self.terminal_head(next_hidden).squeeze(-1),
        )

    def loss(
        self,
        *,
        entities: Tensor,
        next_entities: Tensor,
        action_type: Tensor,
        action_features: Tensor,
        reward: Tensor,
        terminal: Tensor,
        entity_mask: Tensor | None = None,
        next_entity_mask: Tensor | None = None,
    ) -> dict[str, Tensor]:
        prediction = self.predict(entities, action_type, action_features, entity_mask)
        target = masked_mean(next_entities, next_entity_mask)
        dynamics_loss = F.mse_loss(prediction.next_features, target)
        reward_loss = F.smooth_l1_loss(prediction.reward, reward)
        terminal_loss = F.binary_cross_entropy_with_logits(
            prediction.terminal_logit,
            terminal,
        )
        total = dynamics_loss + 0.25 * reward_loss + 0.05 * terminal_loss
        return {
            "loss": total,
            "dynamics_loss": dynamics_loss,
            "reward_loss": reward_loss,
            "terminal_loss": terminal_loss,
        }
