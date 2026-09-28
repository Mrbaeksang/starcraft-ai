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


if __name__ == "__main__":
    app()
