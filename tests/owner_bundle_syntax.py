from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

os.environ.setdefault("KIRANA_DB_PATH", str(Path(tempfile.gettempdir()) / "kirana-owner-bundle-test.db"))

# Importing run registers the same extension order used by Railway.
import run  # noqa: F401,E402
from backend.owner_self_contained_ext import _ASSEMBLED_OWNER_PAGE, _inline_owner_assets  # noqa: E402


def main() -> None:
    assembled = _ASSEMBLED_OWNER_PAGE("owner-bundle-test-token")
    html = _inline_owner_assets(assembled.body.decode("utf-8"))

    assert 'kirana-owner-build" content="116' in html
    assert 'id="kirana-owner-safety-runtime"' in html

    remaining_scripts = re.findall(r'<script\b[^>]*\bsrc=["\']/[^"\']+', html, flags=re.I)
    remaining_styles = re.findall(
        r'<link\b(?=[^>]*\brel=["\']stylesheet["\'])(?=[^>]*\bhref=["\']/)',
        html,
        flags=re.I,
    )
    assert not remaining_scripts, f"External owner scripts remain: {remaining_scripts}"
    assert not remaining_styles, f"External owner styles remain: {remaining_styles}"

    scripts = re.findall(r'<script\b[^>]*>(.*?)</script>', html, flags=re.I | re.S)
    assert scripts, "No inline scripts found"

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for index, script in enumerate(scripts):
            script_path = root / f"owner-inline-{index}.js"
            script_path.write_text(script.replace("<\\/script", "</script"), encoding="utf-8")
            result = subprocess.run(
                ["node", "--check", str(script_path)],
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                raise AssertionError(
                    f"Inline script {index} failed syntax check:\n{result.stdout}\n{result.stderr}"
                )

    print(f"OWNER_BUNDLE_SYNTAX_OK scripts={len(scripts)} bytes={len(html)}")


if __name__ == "__main__":
    main()
