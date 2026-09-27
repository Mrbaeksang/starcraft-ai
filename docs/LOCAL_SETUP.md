# Local setup

Recommended: **Windows 11 + WSL2 Ubuntu + NVIDIA GPU**.

## WSL2 GPU

From Windows:

```powershell
wsl --update
wsl
```

Inside WSL:

```bash
nvidia-smi
```

Do **not** install a Linux NVIDIA display driver inside WSL. NVIDIA documents that the Windows host provides the WSL GPU driver.

For normal PyTorch training, the wheel supplies the CUDA user-space runtime. Install a separate CUDA toolkit only when building custom CUDA/C++ extensions.

## Clone and install

```bash
git clone https://github.com/Mrbaeksang/starcraft-ai.git
cd starcraft-ai

curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
uv sync --extra cu130 --group dev
```

CPU:

```bash
uv sync --extra cpu --group dev
```

## Verify

```bash
uv run --extra cu130 scai doctor
uv run --extra cu130 scai smoke-train --steps 100 --device cuda
make EXTRA=cu130 check
```

If `nvidia-smi` works but PyTorch CUDA does not:

```bash
nvidia-smi
uv run --extra cu130 python - <<'PY'
import torch
print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.is_available())
PY
```

Record those outputs before changing CUDA packages.

## Brood War / BWAPI on Windows

The classic BWAPI path uses StarCraft: Brood War 1.16.1 and BWAPI 4.4.0. Upstream BWAPI supports both bot clients/modules and frame-by-frame replay analysis.

This project will prefer an external collector/client boundary instead of embedding PyTorch in the injected game process.

Proposed local layout:

```text
Windows:
C:\starcraft-ai-runtime\     # local only; ignored
C:\starcraft-ai-data\        # local only

WSL:
/mnt/c/starcraft-ai-data/
```

Exact collector commands will be documented after M1 exists and is tested.

## Keep runtime files out of Git

Before every commit:

```bash
git status --short
```

Never commit StarCraft executables, MPQ files, private replay dumps, large checkpoints, or assets without explicit redistribution rights.

## Codex handoff

Codex reads root `AGENTS.md`. From the repository root, direct it to implement **M1 in `docs/RESEARCH_PLAN.md`** while preserving all M0 checks.
