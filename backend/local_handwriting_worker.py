from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageOps


VERSION = "143"


def _box_values(box):
    try:
        if hasattr(box, "tolist"):
            box = box.tolist()
        if len(box) == 4 and not isinstance(box[0], (list, tuple)):
            x1, y1, x2, y2 = [float(v) for v in box]
            return [x1, y1, x2, y2]
        points = list(box)
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        return [min(xs), min(ys), max(xs), max(ys)]
    except Exception:
        return None


def _result_dict(result):
    payload = getattr(result, "json", None)
    if callable(payload):
        payload = payload()
    if payload is None and hasattr(result, "to_dict"):
        payload = result.to_dict()
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("res")
    return nested if isinstance(nested, dict) else payload


def main() -> int:
    if len(sys.argv) < 2:
        print("KIRANA_JSON:" + json.dumps({"error": "image path missing"}))
        return 2
    image_path = Path(sys.argv[1])
    if not image_path.exists():
        print("KIRANA_JSON:" + json.dumps({"error": "image not found"}))
        return 2

    from paddleocr import PaddleOCR
    import numpy as np

    image = Image.open(image_path)
    image = ImageOps.exif_transpose(image).convert("RGB")
    max_side = max(image.width, image.height)
    if max_side > 3200:
        scale = 3200.0 / max_side
        image = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))))

    # PP-OCRv5 selects the dedicated Devanagari recognizer for lang="hi".
    # It supports Hindi/Devanagari plus English and numeric text, which matches
    # handwritten kirana notes much better than the old PP-OCRv3 Hindi model.
    model = PaddleOCR(
        lang="hi",
        ocr_version="PP-OCRv5",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        device="cpu",
        enable_mkldnn=True,
        cpu_threads=2,
        text_rec_score_thresh=0.18,
    )
    outputs = model.predict(np.asarray(image))
    fragments = []
    for output in outputs:
        data = _result_dict(output)
        texts = list(data.get("rec_texts") or [])
        scores = list(data.get("rec_scores") or [])
        boxes = list(data.get("rec_boxes") or data.get("rec_polys") or [])
        for index, text in enumerate(texts):
            text = str(text or "").strip()
            if not text:
                continue
            score = float(scores[index]) if index < len(scores) else 0.0
            if score < 0.18:
                continue
            box = _box_values(boxes[index]) if index < len(boxes) else None
            fragments.append({"text": text, "score": score, "box": box})

    print(
        "KIRANA_JSON:"
        + json.dumps(
            {
                "width": image.width,
                "height": image.height,
                "fragments": fragments,
                "model": "PP-OCRv5-hi-devanagari",
                "version": VERSION,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
