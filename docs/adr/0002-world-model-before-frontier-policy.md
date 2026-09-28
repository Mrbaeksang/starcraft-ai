# ADR 0002: Validate world models before frontier policy methods

Status: accepted

## Context

Latent-action discovery and discrete diffusion policies are attractive research directions, but they can obscure whether the learned environment dynamics are useful at all.

## Decision

Required order:

1. data correctness;
2. simple supervised dynamics;
3. recurrent world-model baseline;
4. JEPA-style representation hypothesis;
5. random-shooting/CEM planning;
6. latent actions;
7. diffusion proposals;
8. self-play league.

## Consequences

A newer method is not automatically promoted.

Every frontier experiment inherits a mature baseline and a negative control.
