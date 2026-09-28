from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(no_args_is_help=True, help="StarCraft AI research utilities.")


@app.command()
def doctor() -> None:
    """Print the local Python/PyTorch/CUDA environment."""
    import torch

    typer.echo(f"python:      {sys.version.split()[0]}")
    typer.echo(f"platform:    {platform.platform()}")
    typer.echo(f"torch:       {torch.__version__}")
    typer.echo(f"cuda build:  {torch.version.cuda or 'none'}")
    typer.echo(f"cuda:        {'available' if torch.cuda.is_available() else 'unavailable'}")

    if torch.cuda.is_available():
        typer.echo(f"device:      {torch.cuda.get_device_name(0)}")
        typer.echo(f"capability:  {torch.cuda.get_device_capability(0)}")
        free_bytes, total_bytes = torch.cuda.mem_get_info()
        gib = 1024**3
        typer.echo(f"vram free:   {free_bytes / gib:.1f} GiB / {total_bytes / gib:.1f} GiB")


@app.command("smoke-train")
def smoke_train_command(
    steps: Annotated[int, typer.Option(min=1)] = 50,
    device: Annotated[str, typer.Option(help="auto, cpu, or cuda")] = "auto",
    seed: Annotated[int, typer.Option()] = 7,
) -> None:
    """Run a tiny action-conditioned latent world-model training loop."""
    from starcraft_ai.training import smoke_train

    result = smoke_train(steps=steps, device_name=device, seed=seed)
    typer.echo(f"device:      {result.device}")
    typer.echo(f"first loss:  {result.first_loss:.6f}")
    typer.echo(f"final loss:  {result.final_loss:.6f}")


@app.command("benchmark-synthetic")
def benchmark_synthetic_command(
    profile: Annotated[str, typer.Option(help="tiny, small, or medium")] = "tiny",
    steps: Annotated[int, typer.Option(min=1, max=20_000)] = 100,
    seed: Annotated[int, typer.Option()] = 7,
    device: Annotated[str, typer.Option(help="auto, cpu, or cuda")] = "auto",
    output: Annotated[
        Path | None,
        typer.Option(help="Optional JSON result path."),
    ] = None,
) -> None:
    """Benchmark deterministic synthetic latent dynamics training."""
    from starcraft_ai.benchmarking import benchmark_synthetic_dynamics

    result = benchmark_synthetic_dynamics(
        profile=profile,
        steps=steps,
        seed=seed,
        device_name=device,
    )
    payload = json.dumps(asdict(result), indent=2, sort_keys=True)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    typer.echo(payload)


@app.command("benchmark-baseline")
def benchmark_baseline_command(
    model: Annotated[str, typer.Option(help="mlp, recurrent, or jepa")] = "jepa",
    steps: Annotated[int, typer.Option(min=1, max=5_000)] = 30,
    seed: Annotated[int, typer.Option()] = 7,
    device: Annotated[str, typer.Option(help="auto, cpu, or cuda")] = "auto",
    output: Annotated[
        Path | None,
        typer.Option(help="Optional JSON result path."),
    ] = None,
) -> None:
    """Compare a dynamics baseline with probes and multi-step rollout metrics."""
    from starcraft_ai.research_baselines import run_baseline_benchmark

    result = run_baseline_benchmark(
        model_name=model,
        steps=steps,
        seed=seed,
        device_name=device,
    )
    payload = json.dumps(result.to_dict(), indent=2, sort_keys=True)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    typer.echo(payload)


@app.command("inspect-data")
def inspect_data_command(
    path: Annotated[Path, typer.Argument(help="TransitionV1 JSONL file.")],
) -> None:
    """Validate a TransitionV1 JSONL file and print a compact summary."""
    from starcraft_ai.data import iter_jsonl_v1, sha256_file

    transitions = list(iter_jsonl_v1(path))
    if not transitions:
        raise typer.BadParameter("dataset contains no transitions")

    episodes = sorted({item.episode_id for item in transitions})
    frames = [
        frame
        for item in transitions
        for frame in (item.observation.frame, item.next_observation.frame)
    ]
    typer.echo(f"transitions: {len(transitions)}")
    typer.echo(f"episodes:    {len(episodes)}")
    typer.echo(f"frame range: {min(frames)}..{max(frames)}")
    typer.echo(f"sha256:      {sha256_file(path)}")


@app.command("pack-data")
def pack_data_command(
    input_path: Annotated[Path, typer.Argument(help="TransitionV1 JSONL input.")],
    output_path: Annotated[Path, typer.Argument(help="Compressed NPZ output.")],
) -> None:
    """Validate TransitionV1 JSONL and pack it into the compact NPZ format."""
    from starcraft_ai.data import iter_jsonl_v1, pack_npz_v1

    count = pack_npz_v1(output_path, iter_jsonl_v1(input_path))
    typer.echo(f"packed {count} transitions -> {output_path}")


@app.command("audit-data")
def audit_data_command(
    path: Annotated[Path, typer.Argument(help="TransitionV1 JSONL file.")],
) -> None:
    """Audit ordering, observability safety, and canonical hashes."""
    from starcraft_ai.data.audit import audit_jsonl, audit_to_dict

    typer.echo(json.dumps(audit_to_dict(audit_jsonl(path)), indent=2, sort_keys=True))


@app.command("benchmark-data")
def benchmark_data_command(
    path: Annotated[Path, typer.Argument(help="TransitionV1 JSONL file.")],
    repeats: Annotated[int, typer.Option(min=1, max=100)] = 3,
) -> None:
    """Measure validated JSONL loader throughput."""
    from starcraft_ai.data.audit import benchmark_loader, benchmark_to_dict

    result = benchmark_loader(path, repeats=repeats)
    typer.echo(json.dumps(benchmark_to_dict(result), indent=2, sort_keys=True))


@app.command("compare-extractions")
def compare_extractions_command(
    first: Annotated[Path, typer.Argument(help="First TransitionV1 JSONL.")],
    second: Annotated[Path, typer.Argument(help="Second TransitionV1 JSONL.")],
) -> None:
    """Compare two independently generated extraction outputs canonically."""
    from starcraft_ai.data.audit import compare_extractions

    identical, first_audit, second_audit = compare_extractions(first, second)
    payload = {
        "identical": identical,
        "first_canonical_sha256": first_audit.canonical_sha256,
        "second_canonical_sha256": second_audit.canonical_sha256,
        "first_transitions": first_audit.transitions,
        "second_transitions": second_audit.transitions,
    }
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    if not identical:
        raise typer.Exit(code=1)


@app.command("split-data")
def split_data_command(
    path: Annotated[Path, typer.Argument(help="TransitionV1 JSONL file.")],
    output: Annotated[Path, typer.Argument(help="JSON split manifest output.")],
    seed: Annotated[int, typer.Option()] = 7,
) -> None:
    """Create deterministic episode-level split assignments."""
    from starcraft_ai.data import iter_jsonl_v1
    from starcraft_ai.data.audit import episode_split

    transitions = list(iter_jsonl_v1(path))
    assignments = episode_split([item.episode_id for item in transitions], seed=seed)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {"schema_version": 1, "seed": seed, "episodes": assignments},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    typer.echo(f"wrote {len(assignments)} episode assignments -> {output}")


@app.command("train-data")
def train_data_command(
    paths: Annotated[
        list[Path],
        typer.Argument(help="One or more TransitionV1 JSONL files."),
    ],
    model: Annotated[str, typer.Option(help="mlp, recurrent, or jepa")] = "jepa",
    steps: Annotated[int, typer.Option(min=1, max=100_000)] = 100,
    batch_size: Annotated[int, typer.Option(min=1, max=4096)] = 64,
    seed: Annotated[int, typer.Option()] = 7,
    device: Annotated[str, typer.Option(help="auto, cpu, or cuda")] = "auto",
    allow_single_episode_smoke: Annotated[
        bool,
        typer.Option(help="Allow a non-claimable single/few-episode pipeline smoke run."),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(help="Optional JSON result path."),
    ] = None,
) -> None:
    """Train a baseline/world model directly from TransitionV1 data."""
    from starcraft_ai.transition_training import train_transition_dataset

    result = train_transition_dataset(
        paths,
        model_name=model,
        steps=steps,
        batch_size=batch_size,
        seed=seed,
        device_name=device,
        allow_single_episode_smoke=allow_single_episode_smoke,
    )
    payload = json.dumps(result.to_dict(), indent=2, sort_keys=True)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    typer.echo(payload)


@app.command("compare-backends")
def compare_backends_command(
    reference: Annotated[Path, typer.Argument(help="Authoritative BWAPI TransitionV1 JSONL.")],
    candidate: Annotated[Path, typer.Argument(help="Headless candidate TransitionV1 JSONL.")],
    output: Annotated[
        Path | None,
        typer.Option(help="Optional JSON report path."),
    ] = None,
    require_promotion: Annotated[
        bool,
        typer.Option(help="Exit non-zero unless strict promotion thresholds pass."),
    ] = False,
) -> None:
    """Compare BWAPI reference state/action data with a headless backend."""
    from starcraft_ai.data.backend_compare import compare_backends

    result = compare_backends(reference, candidate)
    payload = json.dumps(result.to_dict(), indent=2, sort_keys=True)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    typer.echo(payload)
    if require_promotion and not result.promotion_eligible:
        raise typer.Exit(code=2)


@app.command("certify-backend")
def certify_backend_command(
    reference: Annotated[Path, typer.Argument(help="Authoritative BWAPI TransitionV1 JSONL.")],
    candidate: Annotated[Path, typer.Argument(help="Headless candidate TransitionV1 JSONL.")],
    replay_sha256: Annotated[str, typer.Option(help="SHA-256 of the source .rep file.")],
    candidate_backend: Annotated[
        str,
        typer.Option(help="Candidate backend name, e.g. broodwar-live/bw-engine."),
    ],
    candidate_backend_commit: Annotated[
        str,
        typer.Option(help="Exact 40-character candidate backend git SHA."),
    ],
    output: Annotated[Path, typer.Option(help="Certificate JSON output path.")],
) -> None:
    """Write a deterministic certificate only when backend promotion checks pass."""
    from starcraft_ai.data.certification import (
        create_backend_certificate,
        write_backend_certificate,
    )

    certificate = create_backend_certificate(
        reference,
        candidate,
        replay_sha256=replay_sha256,
        candidate_backend=candidate_backend,
        candidate_backend_commit=candidate_backend_commit,
    )
    write_backend_certificate(output, certificate)
    typer.echo(f"certificate: {certificate.certificate_id}")
    typer.echo(f"wrote:       {output}")


@app.command("validate-certification")
def validate_certification_command(
    path: Annotated[Path, typer.Argument(help="Backend certificate JSON.")],
) -> None:
    """Validate a committed backend promotion certificate."""
    from starcraft_ai.data.certification import load_backend_certificate

    certificate = load_backend_certificate(path)
    typer.echo(f"valid:       {certificate.certificate_id}")
    typer.echo(f"backend:     {certificate.candidate_backend}")
    typer.echo(f"commit:      {certificate.candidate_backend_commit}")


if __name__ == "__main__":
    app()
