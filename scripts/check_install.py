"""Small post-install smoke test. Never touches user recordings or Excel."""
from __future__ import annotations

import hashlib
import importlib
import os

MODEL_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
REQUIRED = ("av", "mcap", "mediapipe", "numpy", "openpyxl", "PIL")


def main() -> int:
    errors = []
    for name in REQUIRED:
        try:
            importlib.import_module(name)
            print(f"OK import {name}")
        except Exception as exc:
            errors.append(f"import {name}: {type(exc).__name__}: {exc}")
    model = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "hand_landmarker.task")
    if not os.path.isfile(model):
        errors.append(f"model tidak ditemukan: {model}")
    else:
        h = hashlib.sha256()
        with open(model, "rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        got = h.hexdigest()
        if got != MODEL_SHA256:
            errors.append(f"hash model berbeda: {got}")
        else:
            print("OK model MediaPipe SHA256")
    try:
        import av
        frame = av.VideoFrame(64, 48, "rgb24")
        frame.reformat(format="yuv420p")
        print("OK PyAV frame smoke")
    except Exception as exc:
        errors.append(f"PyAV smoke: {type(exc).__name__}: {exc}")
    if errors:
        print("\nGAGAL:")
        print("\n".join(f"- {e}" for e in errors))
        return 1
    print("\nZYWtool install OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
