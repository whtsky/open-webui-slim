# Open WebUI Slim Troubleshooting Guide

## Architecture Notes

Open WebUI Slim is API-only. It does not bundle or proxy a local Ollama runtime. Configure external providers directly through Open WebUI connections/settings or environment variables.

## Common Startup Issues

### No models appear

- Verify at least one external provider is configured.
- For Docker, make sure provider credentials and any custom base URLs are passed into the container.
- In the admin UI, check **Settings → Connections** and confirm the connection is enabled.

### RAG features fail

Slim removes local embedding models. Configure an external embedding engine, for example:

```bash
RAG_EMBEDDING_ENGINE=openai
# or
RAG_EMBEDDING_ENGINE=azure_openai
```

Also ensure the matching API credentials are configured.

### Speech-to-text or text-to-speech fails

Slim removes local STT/TTS runtimes. Use external providers only.

Examples:

```bash
AUDIO_STT_ENGINE=openai
AUDIO_TTS_ENGINE=openai
```

## Docker Tips

- Mount persistent app data to `/app/backend/data`.
- Expose the WebUI container on port `8080` internally; map it to any host port you prefer.
- If using reverse proxies, proxy only the Open WebUI app itself.

Example:

```bash
docker run -d -p 3000:8080 \
  -v open-webui:/app/backend/data \
  -e OPENAI_API_KEY=your_key \
  --name open-webui \
  --restart always \
  ghcr.io/OWNER/open-webui-slim:slim
```

## Legacy Configs

If you still have older environment variables or deployment scripts referencing bundled Ollama support, remove them. Open WebUI Slim no longer supports:

- `OLLAMA_BASE_URL`
- `/ollama` backend proxy routes
- bundled `ollama serve` startup
- compose stacks that launch an Ollama sidecar
