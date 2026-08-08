FROM python:3.12-slim
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin \
       libgomp1 libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Main billing app keeps its stable dependency set (including Pydantic v1).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kirana Handwriting AI runs in a completely isolated Python environment so
# PaddleOCR/PaddleX cannot change or break the billing application's packages.
# PaddlePaddle 3.3.x has a known CPU oneDNN/PIR regression; keep the proven
# 3.2.2 + PaddleOCR 3.4.1 combination on Python 3.12.
RUN python -m venv /opt/kirana-ocr \
    && /opt/kirana-ocr/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/kirana-ocr/bin/pip install --no-cache-dir paddlepaddle==3.2.2 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/ \
    && /opt/kirana-ocr/bin/pip install --no-cache-dir paddleocr==3.4.1

ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
ENV KIRANA_OCR_PYTHON=/opt/kirana-ocr/bin/python

# Cache the Hindi multilingual model and run a real inference smoke-test at
# image-build time. A model that only initializes but crashes on predict must
# never be deployed to users.
RUN /opt/kirana-ocr/bin/python - <<'PY'
from paddleocr import PaddleOCR
from PIL import Image, ImageDraw
import numpy as np

ocr = PaddleOCR(
    lang='hi',
    ocr_version='PP-OCRv3',
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    device='cpu',
    enable_mkldnn=True,
    cpu_threads=2,
    text_rec_score_thresh=0.12,
)
img = Image.new('RGB', (640, 320), 'white')
draw = ImageDraw.Draw(img)
draw.rectangle((40, 80, 580, 120), fill='black')
list(ocr.predict(np.asarray(img)))
print('Kirana handwriting local inference smoke-test passed')
PY

COPY . .
ENV PORT=8000
EXPOSE 8000
CMD ["python", "run.py"]
