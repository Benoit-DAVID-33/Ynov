# One image for the three services (application, admin console, worker); the
# command differs, see docker-compose.yml.
#
#   docker build --build-arg DEVICE=cpu -t subtitle-app:cpu .
#   docker build --build-arg DEVICE=gpu -t subtitle-app:gpu .

# --- One-off conversion of the translation model; PyTorch stays out of the final image.
FROM python:3.11-slim AS translation-model
WORKDIR /build
COPY requirements-convert.txt scripts/convert_translation_model.py ./
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements-convert.txt \
    && python convert_translation_model.py --output /translation/opus-mt-en-fr


FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt requirements-ml.txt requirements-gpu.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-ml.txt

# cpu (default) or gpu. The GPU image adds the CUDA libraries (close to 4 GB);
# only the NVIDIA driver and the NVIDIA Container Toolkit are needed on the host.
ARG DEVICE=cpu
RUN if [ "$DEVICE" = "gpu" ]; then pip install --no-cache-dir -r requirements-gpu.txt; fi
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib

COPY --from=translation-model /translation /translation
COPY app app
COPY web web

# Unprivileged user; /data and /models are the two volumes.
RUN useradd --create-home app \
    && mkdir -p /data /models \
    && chown app:app /data /models
USER app

ENV PYTHONUNBUFFERED=1 \
    STORAGE_DIR=/data \
    HF_HOME=/models \
    TRANSLATION_MODELS_DIR=/translation \
    DEVICE=${DEVICE}

EXPOSE 8000 8001
CMD ["uvicorn", "app.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
