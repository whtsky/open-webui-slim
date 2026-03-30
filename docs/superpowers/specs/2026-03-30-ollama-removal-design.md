# Ollama Removal Design

## Goal

Remove Ollama support from Open WebUI Slim so the fork only supports external API-based inference providers.

## Scope

- Delete the backend Ollama router and Ollama-specific retrieval/web helpers.
- Remove Ollama branches from model aggregation, chat dispatch, embeddings dispatch, and retrieval settings.
- Delete the frontend Ollama API client and Ollama-only admin components.
- Remove frontend model-pull and Ollama version UI.
- Update README and environment examples to reflect the new supported provider set.

## Approach

Use a hard removal instead of feature-flagging. This keeps the fork smaller and reduces long-term rebase overhead versus carrying disabled Ollama code.

## Expected Result

- No `/ollama` backend routes.
- No Ollama settings, connection management, or model pulling UI.
- No Ollama-specific model types or payload/response conversion code.
- README describes an API-only slim fork without Ollama support.

## Risks

- Chat and embedding dispatchers currently branch on `owned_by == 'ollama'` and must keep working for remaining providers.
- Frontend model selector contains mixed general-purpose and Ollama-only logic, so cleanup must be surgical.
- Retrieval settings currently expose Ollama embedding options and must be narrowed without breaking saved config updates.

## Verification

- Run targeted grep for remaining `ollama` references.
- Run backend tests if available.
- Run frontend build and fix resulting type/import issues.
