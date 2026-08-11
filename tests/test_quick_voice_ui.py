import json
import subprocess
import sys


def test_ai_voice_uses_native_chrome_and_manual_fallbacks() -> None:
    code = r'''
import json
import run  # noqa: F401
import backend.quick_write_canvas_fix_ext as quick_canvas
html = quick_canvas.HTML
print(json.dumps({
    "native": "window.KiranaVoice && typeof window.KiranaVoice.start==='function'" in html,
    "chrome": "window.SpeechRecognition||window.webkitSpeechRecognition" in html,
    "permission": "navigator.mediaDevices.getUserMedia({audio:true})" in html,
    "manual": "box.id='aiManualVoice2'" in html,
    "ui": "kirana-quick-write-ui-174" in html,
    "version": quick_canvas.VERSION,
    "runtime_join_ok": "load().catch(function(e){show(e.message,true)})\n(function(){" not in html,
}))
'''
    result = subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)
    checks = json.loads(result.stdout.strip())
    assert checks == {
        "native": True,
        "chrome": True,
        "permission": True,
        "manual": True,
        "ui": True,
        "version": "175",
        "runtime_join_ok": True,
    }


def test_quick_write_runtime_scripts_are_separated() -> None:
    source = subprocess.run(
        [sys.executable, "-c", "import run,backend.quick_write_canvas_fix_ext as q;print(q.VERSION)"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert source.stdout.strip() == "175"
