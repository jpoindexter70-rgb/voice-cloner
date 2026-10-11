FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=7860
WORKDIR /app
COPY requirements.txt requirements-dev.txt requirements-engine.txt requirements-engine-lock.txt ./
RUN --mount=type=secret,id=cloud_ca,required=false if [ -f /run/secrets/cloud_ca ]; then export PIP_CERT=/run/secrets/cloud_ca; fi; python -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu && python -m pip install -r requirements-engine.txt -c requirements-engine-lock.txt && python -m pip check
COPY studio ./studio
RUN useradd --uid 1000 --create-home studio && mkdir -p /data/studio2 && chown -R studio:studio /data /app
USER studio
ENV STUDIO2_DATA_DIR=/data/studio2 HF_HOME=/data/studio2/model-cache NUMBA_CACHE_DIR=/data/studio2/numba-cache
EXPOSE 7860
CMD ["python", "-m", "studio.hosted"]
