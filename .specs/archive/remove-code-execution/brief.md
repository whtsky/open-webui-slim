# Remove Code Execution Feature

## Goal

Remove the entire code execution feature (Pyodide browser Python, Jupyter integration, Code Interpreter) from Open WebUI Slim. This saves ~81 MB of assets, eliminates ~2,000 lines of dedicated code, 17 config variables, and reduces attack surface.

## Context

- This is Open WebUI Slim, a fork focused on reducing resource usage
- Code execution has two engines: Pyodide (browser WASM, default) and Jupyter (remote server)
- `static/pyodide/` is 61 MB — 71% of the entire `static/` directory
- The feature is deeply integrated but modular across ~35 files

## User Decisions

- Full removal of both Pyodide and Jupyter code execution
- Option A for code formatting: make server-side `/code/format` available to all verified users
- Keep `black` package (used for formatting, independent of execution)
- Keep `aiohttp` (shared with OAuth, webhooks, model APIs, etc.)

## Scope

- IN: All Pyodide runtime, Jupyter integration, Code Interpreter chat feature, admin settings, permissions, model capabilities
- OUT: Code syntax highlighting (keep), code formatting via black (keep), terminal feature (independent)

## Subsystems

1. File deletions (10 dedicated files + static/pyodide/)
2. Backend Python edits (config, main, routers, tools, middleware, misc, tools.py)
3. Frontend component edits (17 Svelte/TS files)
4. Frontend stores/APIs/constants/layout (7 files)
5. Package management (package.json, requirements, lockfiles)
6. README update

## Verification

- `npm run build` succeeds
- Backend starts without import errors
- grep finds no dangling references to removed features
- static/pyodide/ directory is gone
