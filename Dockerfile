FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY backend ./backend
ARG PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN pip install --upgrade pip \
    && pip install torch --index-url "${PYTORCH_INDEX_URL}" \
    && pip install '.[ml]'

EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}"]
