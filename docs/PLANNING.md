# Latent planning

M3 starts with simple, inspectable search before any learned diffusion proposal policy.

## Implemented search baselines

### Random shooting

Sample complete short action sequences, imagine each sequence under the latent model, and select the highest-scoring sequence.

### Cross-Entropy Method (CEM)

Maintain:

- categorical probabilities over discrete action types;
- Gaussian mean/std over continuous action arguments.

Repeatedly sample a population, keep elites, and update the proposal distribution.

## Score

For an ensemble of latent models:

    score = discounted predicted reward - uncertainty_penalty * ensemble_disagreement

With one model, uncertainty is zero. With multiple independently trained models, disagreement combines latent-state variance and predicted-reward variance.

## Receding horizon

Only the first action from the selected sequence is executed.

After the next real observation, the planner runs again. This prevents a stale imagined trajectory from being executed open-loop.

## Negative control

BrokenSequenceScorer intentionally removes state/action dependence and returns zero scores.

A real-data M3 result must compare:

1. no-planning policy/value baseline;
2. learned-dynamics planner;
3. broken/shuffled-dynamics planner;
4. equal search/compute budgets.

The included synthetic tests validate planning mechanics only. They do not establish a Brood War performance gain.
