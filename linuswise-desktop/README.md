# linuswise-desktop (experimental)

A thin native window around the Linuswise review UI, built with
[Tauri](https://tauri.app).

It doesn't run any logic itself — it waits for the local Linuswise backend to come
up on `http://127.0.0.1:8765`, then shows it in a native window. For most people
the simplest native UI is `uv run linuswise app` (a pywebview window); this
directory is an optional alternative for folks who'd rather ship a Tauri app.

## Run it

In one terminal, start the backend:

```bash
uv run linuswise serve --no-browser
```

In another, from this folder:

```bash
npm install
npm run tauri dev
```

## Build

```bash
npm run tauri build
```

Requires the Tauri prerequisites (Rust toolchain + platform libraries):
<https://v2.tauri.app/start/prerequisites/>
