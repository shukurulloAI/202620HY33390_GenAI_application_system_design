# The website in a container (docs/WEBSITE.md "Running in Docker").
#
#   docker build --target offline -t waste-assistant:offline .   # recorded answers, no torch
#   docker build -t waste-assistant .                            # the full system (CPU torch)
#
# Versions come from requirements.lock (the environment the reported results were made with),
# used as constraints. The live image does not contain the index or the models: compose.yaml
# mounts qdrant_data/ (python -m ingest...) and a model cache, and Ollama runs beside it.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 HF_HOME=/app/.cache/huggingface
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY requirements.lock requirements.txt requirements-app.txt ./
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"]
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.address=0.0.0.0", \
     "--server.port=8501", "--server.headless=true"]

# Offline demo: rag/service.py answers from docs/answer_examples.json, no models.
FROM base AS offline
RUN pip install -c requirements.lock streamlit pydantic tzdata
COPY --chown=app:app . .
RUN mkdir -p traces && chown app:app traces
ENV RAG_OFFLINE=1
USER app

# Full system (the default target).
FROM base AS live
RUN pip install --index-url https://download.pytorch.org/whl/cpu \
        "torch==$(grep -i '^torch==' requirements.lock | cut -d= -f3)" \
 && pip install -c requirements.lock -r requirements-app.txt tzdata
COPY --chown=app:app . .
RUN mkdir -p traces qdrant_data .cache && chown app:app traces qdrant_data .cache
USER app
