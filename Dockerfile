FROM python:3.13-slim
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin \
       libgomp1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# PaddlePaddle is the on-server inference engine for Kirana Handwriting AI.
# It runs locally on Railway CPU; no Gemini/API call is required.
RUN python -m pip install --no-cache-dir paddlepaddle==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
RUN pip install --no-cache-dir -r requirements.txt
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
# Bake the Hindi multilingual OCR weights into the image so the first bill scan
# does not need to download a model at request time.
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(lang='hi', ocr_version='PP-OCRv3', use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False, device='cpu', enable_mkldnn=True, cpu_threads=2, text_rec_score_thresh=0.12); print('Kirana handwriting model cached')"
COPY . .
ENV PORT=8000
EXPOSE 8000
CMD ["python", "run.py"]
