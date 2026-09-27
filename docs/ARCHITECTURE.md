# Architecture

## Principle

Use the most structured trustworthy signal available.

Brood War already exposes entities, orders, resources, upgrades, map information, and visibility through BWAPI. The core research object is therefore a **structured latent world model**, not a pixel generator.

## Runtime split

```text
+----------------------------- Windows 11 -----------------------------+
| StarCraft: Brood War 1.16.1 -> BWAPI -> replay/live collector       |
+----------------------------------|-----------------------------------+
                                   | versioned transition records
                                   v
+------------------------------- WSL2 ---------------------------------+
| dataset -> entity encoder -> latent dynamics -> eval -> planner      |
|                              PyTorch / RTX GPU                        |
+------------------------------------------------------------------------+
```

Windows owns the legacy game runtime. WSL2 owns processing, training, and evaluation.

## M0 model

```text
entities_t ----> online encoder ----> z_t --------+
                                                  |
action --------> action encoder ----> a_t --------+--> predictor --> zhat_(t+1)
                                                                          |
entities_t+1 --> EMA target encoder ---------------------> z_(t+1) --------+
```

Auxiliary heads predict immediate reward and terminal probability.

M0 proves tensor contracts, masking, action conditioning, EMA updates, gradients, and CPU/CUDA portability. It does **not** prove StarCraft intelligence.

## Planned observation model

Entity candidates:

- friendly visible units;
- visible enemy units;
- neutral resources;
- relevant map regions/bases;
- production queues and orders.

Global candidates:

- minerals / gas / supply;
- upgrades and technologies;
- game time;
- matchup metadata;
- map identifier / normalized geometry;
- visibility summary.

The collector records which fields are observable at decision time.

## Temporal hierarchy

Long-term hypothesis:

```text
strategic latent state
        |
        | every ~1-5 s
        v
latent skill / subgoal
        |
        | tactical controller
        v
unit-level commands
```

This hierarchy is an experiment, not an assumption.

## Planning path

M3 starts simple:

1. sample candidate short action/skill sequences;
2. roll them forward in latent space;
3. score reward/value and uncertainty;
4. execute the first selected action;
5. replan.

Only after this baseline works should a learned diffusion proposal model be added.

## Boundaries

- Live observations default to BWAPI-visible information.
- Privileged-information experiments are labeled and separated.
- The repository stores no Blizzard game binaries or commercial assets.
- The learner consumes versioned records and does not depend directly on the Windows process.
