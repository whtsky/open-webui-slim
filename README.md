# Open WebUI Slim

Open WebUI Slim is an opinionated fork of [Open WebUI](https://github.com/open-webui/open-webui), currently based on **v0.10.2**. It keeps the API-backed core chat experience while removing local model inference and optional products to reduce dependency, image, memory, and maintenance overhead.

This fork is intended for deployments that use OpenAI-compatible or other external providers. It does not support Ollama, CUDA, or in-process ML models.

## What's Removed

### Local ML and GPU support

- PyTorch and its ecosystem: `torch`, `torchvision`, `torchaudio`, `transformers`, `sentence-transformers`, `accelerate`, and `colbert-ai`
- Local embedding and reranking models; embeddings must use `openai` or `azure_openai`, and reranking must use an external API or remain disabled
- Local Whisper, OCR models, and their model-download/runtime dependencies
- CUDA/GPU image variants, CUDA environment setup, and model pre-download steps
- Embedded Chroma, whose full package pulls ONNX and Hugging Face runtimes; remote Chroma remains supported through `chromadb-client`

### Providers and products

- Ollama routes, discovery, dispatch, settings, Docker sidecars, and helper scripts
- Pyodide, Jupyter/code interpreter, executable code blocks, terminals, and OpenTerminal
- Community publishing/sync and external community statistics export
- Ratings, evaluations, arena models, and leaderboards
- Notes and Channels, including their user interfaces, APIs, socket handlers, and direct collaboration wiring
- Playground, `/watch`, and the empty `/home` placeholder route
- The entire speech product surface: local and remote STT/TTS endpoints, voice recording, voice calls, dictation, read-aloud controls, speech settings, and provider configuration
- Calendar and Automations, including their runtime models, schedulers, APIs, routes, navigation, permissions, events, and settings
- SCIM provisioning, including its API router, runtime behavior, environment configuration, and admin settings
- Speech-only runtime dependencies (`pydub`, PyAV, `python-mimeparse`, and FFmpeg) and the Automations scheduler dependency (`APScheduler`)

Historical database migrations for removed products remain in place so existing databases can still traverse the upstream migration chain. The legacy SCIM user column is likewise retained only for schema compatibility; there is no SCIM runtime behavior. Shared syntax highlighting and authenticated code formatting are also retained; they do not execute user code.

## What's Kept

The fork adopts upstream v0.10.2 features that do not depend on a removed subsystem, including:

- Core single- and multi-model chat through OpenAI-compatible and other external APIs
- Skills, context summaries/compaction, structured output, output editing, and memories
- Knowledge directories and RAG with external embeddings, optional external reranking, web search, and externally configured vector databases
- Shared folders, access grants, and ordinary internal shared-chat links
- Authentication and administration features including LDAP, OAuth/OIDC, trusted-header provisioning, SSO, RBAC, admin-created users, and unrelated admin analytics
- Image generation, pipelines, MCP/tool servers, Markdown/LaTeX rendering, PWA support, i18n, and OpenTelemetry; terminal execution remains removed
- Generic audio-file upload/preview and notification or greeting sounds, which have live uses independent of transcription and synthesis
- SQLite and PostgreSQL application databases plus upstream external vector-store integrations

The fork also preserves its chat scalability work on the v0.10.2 async database architecture: projected chat-list queries, normalized `chat_message` reads with JSON fallback, status-history dual writes, write-time sanitization, and batched NDJSON chat exports.

## Getting Started

### Docker

```bash
docker run -d \
  --name open-webui-slim \
  -p 3000:8080 \
  -e OPENAI_API_KEY=your_key \
  -e WEBUI_ADMIN_EMAIL=admin@example.com \
  -e WEBUI_ADMIN_PASSWORD='replace-with-a-strong-password' \
  -v open-webui:/app/backend/data \
  --restart unless-stopped \
  ghcr.io/OWNER/open-webui-slim:slim
```

Replace `OWNER/open-webui-slim` with this fork's GitHub repository name.

The example creates the first administrator directly on an empty database. Remove `WEBUI_ADMIN_PASSWORD` from the deployment environment after that first successful start. Public password registration cannot be enabled from the admin UI.

### Docker Compose

The root Compose file builds the local Python 3.12 slim image:

```bash
docker compose up -d --build
```

Use a bind mount instead of the default named volume when desired:

```bash
OPEN_WEBUI_DATA_SOURCE=./open-webui-data docker compose up -d --build
```

### External inference and vector storage

Configure an external chat provider and, before using RAG, an external embedding provider and vector database. Remote Chroma is the default-compatible option:

```bash
OPENAI_API_KEY=your_key
RAG_EMBEDDING_ENGINE=openai
RAG_EMBEDDING_MODEL=text-embedding-3-small

VECTOR_DB=chroma
CHROMA_HTTP_HOST=chroma.example.com
CHROMA_HTTP_PORT=8000
CHROMA_HTTP_SSL=true
```

Other retained vector backends can be selected with `VECTOR_DB`; see [.env.example](./.env.example) and upstream configuration documentation for provider-specific settings.

### Registration policy

Public password registration is closed by default and cannot be reopened through persistent configuration or the admin UI. The legacy `ENABLE_SIGNUP` setting and stale `ui.enable_signup=true` database values are ignored.

For an interactive first-run bootstrap only, set `ENABLE_INITIAL_ADMIN_SIGNUP=true` on a fresh empty database. Exactly the first account can then be created and is made administrator; after any user exists, `POST /api/v1/auths/signup` returns HTTP 403 regardless of that environment variable or stale configuration. Administrators can still create users, and explicitly configured OAuth, LDAP, and trusted-header provisioning remain separate.

## Development and Releases

- `main` contains stable slim releases.
- `slim` is the active development branch.
- The image uses `python:3.12-slim-bookworm` and has no CUDA or bundled-model variant.
- [`.github/workflows/docker.yaml`](./.github/workflows/docker.yaml) publishes one amd64/arm64 slim image for `main`, `slim`, and version tags.

No current v0.10.2 image-size comparison is published yet; the table will be updated after reproducible upstream and slim images are measured with the same build settings.

## Upstream and License

This fork tracks [open-webui/open-webui](https://github.com/open-webui/open-webui). See [the upstream documentation](https://docs.openwebui.com/) for general usage guidance, with the removals above taking precedence.

The license is unchanged from upstream. See [LICENSE](./LICENSE) and [LICENSE_HISTORY](./LICENSE_HISTORY).
