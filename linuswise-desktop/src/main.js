// Wait for the local Linuswise backend to come up, then hand the whole webview
// over to it. On desktop the Rust side starts the Python server; here we just
// poll until it answers and navigate. (For mobile, point BACKEND at a hosted URL.)
const BACKEND = "http://127.0.0.1:8765";

async function reachable() {
  try {
    await fetch(BACKEND, { mode: "no-cors", cache: "no-store" });
    return true;
  } catch (_e) {
    return false;
  }
}

(async () => {
  for (let i = 0; i < 120; i++) {
    if (await reachable()) {
      window.location.href = BACKEND;
      return;
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  document.getElementById("msg").textContent =
    "Couldn't reach the Linuswise backend. Is it installed? (uv run linuswise serve)";
})();
