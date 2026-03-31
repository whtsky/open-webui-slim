# DB Performance Fixes — Spec Brief

## Goal

Eliminate OOM-causing database query patterns in the chat subsystem by moving sanitization to write paths, adding column projection on list paths, paginating endpoints, fixing dual-write gaps, and migrating message reads from the JSON blob to the `chat_message` table.

## Context

- The `chat` table has a `chat` JSON column that can be 200MB+ for power users
- 4 endpoints load ALL chats without pagination
- 8 list functions load full JSON blobs when only metadata is needed
- `_sanitize_chat_row()` is called on every read, can trigger writes
- `get_messages_map_by_chat_id()` loads entire Chat row to extract messages
- The `chat_message` table exists with backfill migration and dual-write
- Status history dual-write has a gap
- Addresses upstream open-webui/open-webui#23192

## Files

- `backend/open_webui/models/chats.py`
- `backend/open_webui/models/chat_messages.py`
- `backend/open_webui/routers/chats.py`
- `README.md`

## Steps

1. Move `_sanitize_chat_row()` to write paths only
2. Add `.with_entities()` column projection to 5 list functions
3. Add pagination to `/chats/all/archived` and `/chats/folder/{id}`
4. Fix status history dual-write gap
5. Add `get_messages_map_by_chat_id()` to ChatMessages
6. Migrate reads to `chat_message` table with validated fallback
7. Verify middleware (no code changes)
8. Update README.md
9. Commit and push
