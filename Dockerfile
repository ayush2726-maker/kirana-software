FROM python:3.13-slim
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
RUN python -m venv /opt/kirana-ocr \
    && /opt/kirana-ocr/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/kirana-ocr/bin/pip install --no-cache-dir paddlepaddle==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/ \
    && /opt/kirana-ocr/bin/pip install --no-cache-dir paddleocr==3.7.0

ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
ENV KIRANA_OCR_PYTHON=/opt/kirana-ocr/bin/python

# Cache the Hindi multilingual model in the Docker image. This is a local model
# download at build time only; bill photos are never sent to Paddle/Gemini APIs.
RUN /opt/kirana-ocr/bin/python -c "from paddleocr import PaddleOCR; PaddleOCR(lang='hi', ocr_version='PP-OCRv3', use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False, device='cpu', enable_mkldnn=True, cpu_threads=2, text_rec_score_thresh=0.12); print('Kirana handwriting model cached')"

COPY . .
ENV PORT=8000
EXPOSE 8000
CMD ["python", "run.py"]
