from __future__ import annotations

import os

import requests


BASE_URL = os.getenv("OWNER_UI_BASE_URL", "http://127.0.0.1:8000")


def main() -> None:
    owner = requests.Session()
    login = owner.post(
        f"{BASE_URL}/owner-login",
        data={"username": "admin", "password": "1234"},
        allow_redirects=True,
        timeout=20,
    )
    assert login.ok, login.text[:500]
    assert 'id="app-loading"' in login.text
    assert 'kirana-owner-boot-watchdog' in login.text
    assert '/owner-stable.js?v=113' in login.text
    assert login.headers.get("X-Kirana-Boot-Recovery") == "113"

    script = owner.get(f"{BASE_URL}/owner-stable.js?v=113", timeout=20)
    assert script.ok, script.text[:500]
    assert script.headers.get("X-Kirana-Owner-Bundle") == "113"
    assert "window.__kiranaOwnerBundleLoaded = true" in script.text
    assert "window.__kiranaOwnerBootReady = true" in script.text
    assert "async function fetchWithTimeout" in script.text
    assert "Server response timed out. Please retry." in script.text

    print("OWNER_BOOT_RECOVERY_SMOKE_OK")


if __name__ == "__main__":
    main()
