from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

import torch
from torch import Tensor, nn
from torch.nn import functional as F


@dataclass(frozen=True, slots=True)
class WorldModelConfig:
    entity_features: int = 24
    action_types: int = 16
    action_features: int = 8
    model_dim: int = 128
    latent_dim: int = 128
    attention_heads: int = 4
    transformer_layers: int = 2
    dropout: float = 0.0


class EntityEncoder(nn.Module):
    def __init__(self, config: WorldModelConfig) -> None:
        super().__init__()
        self.input_projection = nn.Sequential(
            nn.Linear(config.entity_features, config.model_dim),
            nn.LayerNorm(config.model_dim),
            nn.GELU(),
        )
        layer = nn.TransformerEncoderLayer(
            d_model=config.model_dim,
            nhead=config.attention_heads,
            dim_feedforward=config.model_dim * 4,
            dropout=config.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(
            layer,
            num_layers=config.transformer_layers,
            enable_nested_tensor=False,
        )
        self.output_projection = nn.Sequential(
            nn.LayerNorm(config.model_dim),
            nn.Linear(config.model_dim, config.latent_dim),
        )

    def forward(self, entities: Tensor, entity_mask: Tensor | None = None) -> Tensor:
        if entities.ndim != 3:
            raise ValueError("entities must have shape [batch, entities, features]")

        encoded = self.input_projection(entities)
        padding_mask = None
        if entity_mask is not None:
            if entity_mask.shape != entities.shape[:2]:
                raise ValueError("entity_mask must have shape [batch, entities]")
            padding_mask = ~entity_mask.bool()

        encoded = self.transformer(encoded, src_key_padding_mask=padding_mask)

        if entity_mask is None:
            pooled = encoded.mean(dim=1)
        else:
            weights = entity_mask.to(encoded.dtype).unsqueeze(-1)
            pooled = (encoded * weights).sum(dim=1) / weights.sum(dim=1).clamp_min(1.0)

        return F.normalize(self.output_projection(pooled), dim=-1)


class ActionEncoder(nn.Module):
    def __init__(self, config: WorldModelConfig) -> None:
        super().__init__()
        self.type_embedding = nn.Embedding(config.action_types, config.model_dim)
        self.argument_projection = nn.Sequential(
            nn.Linear(config.action_features, config.model_dim),
            nn.GELU(),
            nn.Linear(config.model_dim, config.model_dim),
        )
        self.output = nn.Sequential(
            nn.LayerNorm(config.model_dim * 2),
            nn.Linear(config.model_dim * 2, config.latent_dim),
            nn.GELU(),
        )

    def forward(self, action_type: Tensor, action_features: Tensor) -> Tensor:
        type_embedding = self.type_embedding(action_type)
        argument_embedding = self.argument_projection(action_features)
        return self.output(torch.cat((type_embedding, argument_embedding), dim=-1))


class LatentWorldModel(nn.Module):
    """Minimal action-conditioned latent dynamics model for M0/M2 experiments."""

    def __init__(self, config: WorldModelConfig) -> None:
        super().__init__()
        self.config = config
        self.encoder = EntityEncoder(config)
        self.target_encoder = deepcopy(self.encoder)
        self.target_encoder.requires_grad_(False)

        self.action_encoder = ActionEncoder(config)
        self.predictor = nn.Sequential(
            nn.Linear(config.latent_dim * 2, config.model_dim * 2),
            nn.GELU(),
            nn.Linear(config.model_dim * 2, config.latent_dim),
        )
        self.reward_head = nn.Sequential(
            nn.Linear(config.latent_dim, config.model_dim),
            nn.GELU(),
            nn.Linear(config.model_dim, 1),
        )
        self.terminal_head = nn.Linear(config.latent_dim, 1)

    def encode(self, entities: Tensor, entity_mask: Tensor | None = None) -> Tensor:
        return self.encoder(entities, entity_mask)

    @torch.no_grad()
    def encode_target(self, entities: Tensor, entity_mask: Tensor | None = None) -> Tensor:
        return self.target_encoder(entities, entity_mask)

    def predict(
        self,
        entities: Tensor,
        action_type: Tensor,
        action_features: Tensor,
        entity_mask: Tensor | None = None,
    ) -> dict[str, Tensor]:
        state_latent = self.encode(entities, entity_mask)
        action_latent = self.action_encoder(action_type, action_features)
        next_latent = F.normalize(
            self.predictor(torch.cat((state_latent, action_latent), dim=-1)),
            dim=-1,
        )
        return {
            "state_latent": state_latent,
            "next_latent": next_latent,
            "reward": self.reward_head(next_latent).squeeze(-1),
            "terminal_logit": self.terminal_head(next_latent).squeeze(-1),
        }

    def loss(
        self,
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

        with torch.no_grad():
            target_latent = self.encode_target(next_entities, next_entity_mask)

        latent_loss = (1.0 - F.cosine_similarity(prediction["next_latent"], target_latent)).mean()
        reward_loss = F.smooth_l1_loss(prediction["reward"], reward)
        terminal_loss = F.binary_cross_entropy_with_logits(
            prediction["terminal_logit"], terminal
        )
        total_loss = latent_loss + 0.25 * reward_loss + 0.05 * terminal_loss

        return {
            "loss": total_loss,
            "latent_loss": latent_loss,
            "reward_loss": reward_loss,
            "terminal_loss": terminal_loss,
        }

    @torch.no_grad()
    def update_target_encoder(self, momentum: float = 0.99) -> None:
        if not 0.0 <= momentum <= 1.0:
            raise ValueError("momentum must be in [0, 1]")

        for online, target in zip(
            self.encoder.parameters(), self.target_encoder.parameters(), strict=True
        ):
            target.data.mul_(momentum).add_(online.data, alpha=1.0 - momentum)
