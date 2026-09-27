# Research plan

## North-star question

Can a structured latent world model reduce expensive real Brood War interaction while learning useful planning behavior on one consumer GPU?

“No” is a valid result.

## M0 — infrastructure

Status: implemented.

Success criteria:

- lint and tests pass on CPU;
- synthetic loss is finite;
- backward pass is finite;
- CUDA smoke training runs locally.

M0 makes no game-intelligence claim.

## M1 — replay/state collection

Goal: a trustworthy data contract.

Required records:

- episode metadata;
- observation at decision time;
- action(s);
- next observation;
- reward components;
- terminal outcome;
- visibility / observability mode.

Validation:

- schema version per shard;
- deterministic extraction;
- no future information;
- no hidden enemy state in non-cheating mode;
- transitions/sec measurement;
- WSL/Linux loader test.

## M2 — structured JEPA-style world model

### H1

Action-conditioned target-representation learning retains more control-relevant information than equally sized simple baselines.

Baselines:

1. current-state representation;
2. direct next-feature MLP;
3. supervised auxiliary-only encoder;
4. EMA target-representation model.

Metrics:

- held-out temporal prediction;
- probes for economy / army / tech / map-control targets;
- reward and terminal calibration;
- multi-step rollout degradation;
- throughput and VRAM.

Do not advance on training loss alone.

## M3 — latent planning

### H2

Short latent rollouts improve action selection over the same model without planning.

Start with random shooting or CEM-style search, short horizon, uncertainty penalty, and receding-horizon execution.

Compare policy/value only, world-model planner, and a deliberately broken/shuffled dynamics sanity control.

## M4 — latent skills and diffusion proposals

### H3

A learned proposal distribution improves search over the combinatorial action space at the same planning budget.

Only begin after M3 shows world-model planning is useful.

Candidate experiments:

- inverse/forward latent-action discovery;
- vector-quantized skills;
- discrete diffusion action/skill proposals;
- autoregressive proposal baseline.

## M5 — self-play population

After a stable evaluation protocol:

- current policy;
- historical snapshots;
- exploiters/counter-policies;
- prioritized matchmaking;
- diversity / exploitability metrics.

Win rate against one snapshot is insufficient.

## Reproducibility

Every public experiment records:

- git commit;
- dataset version/hash;
- seeds;
- hardware;
- Python/PyTorch/CUDA versions;
- effective config;
- transitions / environment steps;
- wall-clock time;
- peak VRAM;
- evaluation protocol.

## Public language

Good early wording: “experimental”, “prototype”, “we are testing whether…”.

Avoid unsupported: “human-level”, “state of the art”, “beats RL”, “learns strategy autonomously”.
