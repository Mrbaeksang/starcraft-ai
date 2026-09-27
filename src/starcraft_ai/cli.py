from __future__ import annotations

import platform
import sys

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
    steps: int = typer.Option(50, min=1),
    device: str = typer.Option("auto", help="auto, cpu, or cuda"),
    seed: int = typer.Option(7),
) -> None:
    """Run a tiny action-conditioned latent world-model training loop."""
    from starcraft_ai.training import smoke_train

    result = smoke_train(steps=steps, device_name=device, seed=seed)
    typer.echo(f"device:      {result.device}")
    typer.echo(f"first loss:  {result.first_loss:.6f}")
    typer.echo(f"final loss:  {result.final_loss:.6f}")


if __name__ == "__main__":
    app()
