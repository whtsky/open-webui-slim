# Open WebUI Slim Troubleshooting Guide

## Architecture Notes

Open WebUI Slim uses external inference providers only. It does not bundle or proxy a local Ollama runtime. Configure providers directly through Open WebUI connections/settings or environment variables.

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

### Speech controls or endpoints are unavailable

This is expected. Slim removes the entire speech-to-text and text-to-speech product surface, including remote-provider configuration, voice recording, calls, dictation, and read-aloud. Generic audio-file uploads and notification sounds remain available.

### A fresh install has no sign-up link

Public password registration is intentionally closed. Create the first administrator with `WEBUI_ADMIN_EMAIL` and `WEBUI_ADMIN_PASSWORD`, or set `ENABLE_INITIAL_ADMIN_SIGNUP=true` only for an empty-database interactive bootstrap. The latter permits exactly one administrator account and cannot be used for later public signups.

## Docker Tips

- Mount persistent app data to `/app/backend/data`.
- Expose the WebUI container on port `8080` internally; map it to any host port you prefer.
- If using reverse proxies, proxy only the Open WebUI app itself.

Example:

```bash
docker run -d -p 3000:8080 \
  -v open-webui:/app/backend/data \
  -e OPENAI_API_KEY=your_key \
  -e WEBUI_ADMIN_EMAIL=admin@example.com \
  -e WEBUI_ADMIN_PASSWORD='replace-with-a-strong-password' \
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
