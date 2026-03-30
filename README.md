# Open WebUI Slim

> **An opinionated fork of [Open WebUI](https://github.com/open-webui/open-webui) (v0.8.12) focused on reducing resource usage and improving speed by removing heavyweight local ML dependencies.**

## Why This Fork?

Upstream Open WebUI bundles PyTorch and local ML models for embedding, reranking, speech-to-text, and text-to-speech. This adds ~2.5 GB of Python packages (CPU) plus ~500 MB of pre-downloaded models to the Docker image, even when you're using external API providers for all of these.

This fork removes those local ML features entirely, producing a leaner image for deployments that use external APIs (OpenAI, Azure, Deepgram, ElevenLabs, etc.) for inference.

## What's Removed

The following packages have been removed from `requirements.txt` and `pyproject.toml`:

| Package | What it powered | Alternative |
|---|---|---|
| `torch`, `torchvision`, `torchaudio` | PyTorch runtime (~1.5 GB CPU) | Not needed — all local ML removed |
| `sentence-transformers` | Local RAG embedding & CrossEncoder reranking | Set `RAG_EMBEDDING_ENGINE` to `openai` or `azure_openai` |
| `transformers` | Local TTS via `microsoft/speecht5_tts` | Set `AUDIO_TTS_ENGINE` to `openai`, `elevenlabs`, or `azure` |
| `accelerate` | PyTorch GPU acceleration | Not needed |
| `faster-whisper` | Local Whisper speech-to-text | Set `AUDIO_STT_ENGINE` to `openai`, `deepgram`, or `azure` |
| `onnxruntime` | ONNX inference backend for faster-whisper | Not needed |
| `colbert-ai` | ColBERT dense reranking | Set `RAG_RERANKING_ENGINE` to `external` |
| `sentencepiece` | Tokenizer for transformers/sentence-transformers | Not needed |
| `soundfile` | Audio I/O for local TTS | Not needed |
| `einops` | Tensor operations for sentence-transformers | Not needed |
| `pyarrow` | DataFrame serialization for datasets | Not needed |
| `opencv-python-headless` | Legacy local OCR/image-processing dependency | Not needed — no code imports `cv2`; local OCR is removed/API-based |

Also removed from container/build tooling:
- Explicit `pip install torch torchvision torchaudio` step
- All CUDA build args and logic (`USE_CUDA`, `USE_CUDA_VER`)
- All ML model pre-downloads (sentence-transformers models, Whisper model)
- Build-time compilation dependencies (`build-essential`, `gcc`, `python3-dev`, `libmariadb-dev`, `libsm6`, `libxext6`)
- Bundled local model-server Docker/Compose sidecars and helper scripts

### Source code changes

Backend Python files modified to return clear error messages if local ML features are attempted:
- `backend/open_webui/env.py` — Removed torch CUDA/MPS detection; always sets `DEVICE_TYPE='cpu'`
- `backend/open_webui/__init__.py` — Removed CUDA LD_LIBRARY_PATH setup and torch validation
- `backend/open_webui/routers/retrieval.py` — Local embedding (`get_ef`) and local reranking (`get_rf`) raise errors directing users to external engines; removed `torch.cuda.empty_cache()` calls
- `backend/open_webui/routers/audio.py` — `set_faster_whisper_model()` returns None with warning; `load_speech_pipeline()` raises NotImplementedError; transformers TTS endpoint returns 501
- `backend/open_webui/routers/evaluations.py` — `_get_embedding_model()` returns None with warning (query-weighted leaderboard filtering disabled)
- `backend/open_webui/retrieval/utils.py` — Replaced `sentence_transformers.util.cos_sim` with numpy-based cosine similarity

## What's Kept

Everything else from upstream Open WebUI v0.8.12:

- All LLM chat features via OpenAI-compatible APIs
- RAG with external embedding providers (OpenAI, Azure OpenAI)
- External reranking via API
- Web search integration (SearXNG, Google PSE, Brave, DuckDuckGo, etc.)
- All authentication methods (LDAP, SSO, OAuth, SCIM)
- Admin panel, user management, RBAC
- Markdown/LaTeX rendering
- Image generation (DALL-E, Gemini, ComfyUI, AUTOMATIC1111)
- Pipelines plugin support
- All database backends (SQLite, PostgreSQL)
- All vector database backends (ChromaDB, PGVector, Qdrant, Milvus, Elasticsearch, etc.)
- STT via external providers (OpenAI, Deepgram, Azure, Mistral)
- TTS via external providers (OpenAI, ElevenLabs, Azure)
- Progressive Web App
- i18n / multilingual support
- OpenTelemetry observability

## Getting Started

### Docker

```bash
docker run -d -p 3000:8080 \
  -e OPENAI_API_KEY=your_key \
  -v open-webui:/app/backend/data \
  --name open-webui \
  --restart always \
  ghcr.io/OWNER/open-webui-slim:slim
```

Replace `OWNER` with your GitHub username/org. The image is built automatically on push to the `slim` branch.

### Docker Compose

The root compose stack now runs only Open WebUI Slim:

```bash
docker compose up -d --build
```

To use a bind mount instead of the default named volume:

```bash
OPEN_WEBUI_DATA_SOURCE=./open-webui-data docker compose up -d --build
```

### Required Configuration

Since local ML is removed, you must configure external providers:

```bash
# RAG Embedding (required for RAG features)
RAG_EMBEDDING_ENGINE=openai        # or "azure_openai"

# Speech-to-Text (optional)
AUDIO_STT_ENGINE=openai            # or "deepgram", "azure", "mistral"

# Text-to-Speech (optional)
AUDIO_TTS_ENGINE=openai            # or "elevenlabs", "azure"
```

## Branch Strategy

- `main` — stable slim releases
- `slim` — active development branch (based on upstream v0.8.12)

## CI/CD

The `.github/workflows/docker-build-slim.yaml` workflow builds and pushes multi-arch Docker images (linux/amd64 + linux/arm64) to GHCR on every push to `slim` or `slim/**` branches.

Image tags follow the branch name: `ghcr.io/OWNER/open-webui-slim:slim`

## Upstream

This fork tracks [open-webui/open-webui](https://github.com/open-webui/open-webui). See upstream for full documentation at [docs.openwebui.com](https://docs.openwebui.com/).

## License

Same license as upstream. See [LICENSE](./LICENSE) and [LICENSE_HISTORY](./LICENSE_HISTORY).
