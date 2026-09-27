import torch

from starcraft_ai.models.world_model import LatentWorldModel, WorldModelConfig
from starcraft_ai.synthetic import make_synthetic_batch


def test_world_model_backward_is_finite() -> None:
    torch.manual_seed(0)
    device = torch.device("cpu")
    config = WorldModelConfig(
        entity_features=8,
        action_types=4,
        action_features=3,
        model_dim=32,
        latent_dim=32,
        attention_heads=4,
        transformer_layers=1,
    )
    model = LatentWorldModel(config)
    batch = make_synthetic_batch(
        config,
        batch_size=4,
        entities_per_state=6,
        device=device,
        seed=3,
    )

    losses = model.loss(
        entities=batch.entities,
        next_entities=batch.next_entities,
        action_type=batch.action_type,
        action_features=batch.action_features,
        reward=batch.reward,
        terminal=batch.terminal,
        entity_mask=batch.entity_mask,
        next_entity_mask=batch.entity_mask,
    )
    losses["loss"].backward()

    assert torch.isfinite(losses["loss"])
    gradients = [p.grad for p in model.parameters() if p.grad is not None]
    assert gradients
    assert all(torch.isfinite(gradient).all() for gradient in gradients)
