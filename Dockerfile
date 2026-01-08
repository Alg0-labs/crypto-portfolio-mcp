
FROM python:3.12-slim


WORKDIR /app


ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1


RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .


RUN pip install --no-cache-dir -r requirements.txt


COPY src/ ./src/




RUN useradd -m -u 1000 mcpuser && \
    chown -R mcpuser:mcpuser /app


USER mcpuser


EXPOSE 8000


HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"


CMD ["python", "-m", "src.server"]
