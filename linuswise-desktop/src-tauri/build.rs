fn main() {
    // Bake the repo root (two levels above src-tauri) into the binary as
    // LINUSWISE_DEFAULT_DIR, so a Finder-launched .app can locate the Python
    // project even with no environment variables set.
    let manifest = std::env::var("CARGO_MANIFEST_DIR").unwrap();
    let repo = std::path::Path::new(&manifest)
        .parent()
        .and_then(|p| p.parent())
        .expect("src-tauri should be two levels below the repo root");
    println!("cargo:rustc-env=LINUSWISE_DEFAULT_DIR={}", repo.display());

    tauri_build::build()
}
