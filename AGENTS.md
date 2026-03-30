# AI Agent Instructions

## Repository Context

This is **Open WebUI Slim** — an opinionated fork of [Open WebUI](https://github.com/open-webui/open-webui) (based on v0.8.12) focused on reducing resource usage and improving speed by removing heavyweight dependencies like PyTorch and local ML inference features.

## Auto-Update README

Whenever features are added or removed from this fork, **automatically update `README.md`** to reflect the current state. Specifically:

- Keep the "What's Removed" section accurate with every removal PR
- Keep the "What's Kept" section accurate
- Update the size/resource comparison table when new measurements are available
- Update "Getting Started" once installation instructions are finalized

The README is the primary document communicating the fork's purpose and current state — it must stay in sync with the code.

## Key Decisions

- **No local ML inference**: All embedding, reranking, STT, and TTS must use external API providers
- **No PyTorch**: The `torch`, `torchvision`, `torchaudio`, `sentence-transformers`, `transformers`, `accelerate`, and `colbert-ai` packages are removed
- **No CUDA/GPU support**: Not needed without local models
- **Minimal diff from upstream**: Keep changes surgical so we can rebase onto new upstream releases

## Branch Strategy

- `main` — stable slim releases
- `slim` — active development branch
- Upstream tags (e.g., `v0.8.12`) are preserved for reference
