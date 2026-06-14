use std::net::TcpStream;
use std::path::PathBuf;
use std::process::Command;
use std::time::Duration;

// On desktop the Linuswise backend is the local Python server. We start it if it
// isn't already running, so launching the app "just works" — crucially even when
// the .app is double-clicked from Finder, where PATH is minimal and no shell env
// is inherited. On mobile there's no local Python; the loader targets a hosted
// backend instead.

#[cfg(desktop)]
const BACKEND_ADDR: &str = "127.0.0.1:8765";

#[cfg(desktop)]
fn backend_up() -> bool {
    TcpStream::connect_timeout(&BACKEND_ADDR.parse().unwrap(), Duration::from_millis(300)).is_ok()
}

// Finder-launched apps don't inherit your shell PATH, so `uv` can't be found by
// name. Resolve it from the UV env var or the usual install locations.
#[cfg(desktop)]
fn find_uv() -> Option<PathBuf> {
    if let Ok(p) = std::env::var("UV") {
        let pb = PathBuf::from(p);
        if pb.is_file() {
            return Some(pb);
        }
    }
    let home = std::env::var("HOME").unwrap_or_default();
    [
        format!("{home}/.local/bin/uv"),
        "/opt/homebrew/bin/uv".to_string(),
        "/usr/local/bin/uv".to_string(),
    ]
    .into_iter()
    .map(PathBuf::from)
    .find(|p| p.is_file())
}

// Locate the linuswise source checkout (holds pyproject.toml + the package).
// Priority: LINUSWISE_PROJECT_DIR env -> the dir this app was built from (baked
// in at compile time by build.rs) -> ~/coding/readwise.
#[cfg(desktop)]
fn project_dir() -> Option<PathBuf> {
    let mut candidates: Vec<PathBuf> = Vec::new();
    if let Ok(dir) = std::env::var("LINUSWISE_PROJECT_DIR") {
        candidates.push(PathBuf::from(dir));
    }
    candidates.push(PathBuf::from(env!("LINUSWISE_DEFAULT_DIR")));
    if let Ok(home) = std::env::var("HOME") {
        candidates.push(PathBuf::from(format!("{home}/coding/readwise")));
    }
    candidates
        .into_iter()
        .find(|p| p.join("pyproject.toml").is_file())
}

#[cfg(desktop)]
fn ensure_backend() {
    if backend_up() {
        return;
    }
    let (Some(uv), Some(dir)) = (find_uv(), project_dir()) else {
        // Toolchain/source not found; the loader page surfaces a hint instead.
        return;
    };
    let home = std::env::var("HOME").unwrap_or_default();
    let path = format!("{home}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin");
    let _ = Command::new(uv)
        .args(["run", "linuswise", "serve", "--no-browser"])
        .current_dir(&dir)
        .env("PATH", path)
        .spawn();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|_app| {
            #[cfg(desktop)]
            ensure_backend();
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
