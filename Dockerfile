
FROM python:3.12-slim


WORKDIR /app


ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MCP_TRANSPORT=http \
    PORT=8000


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


HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request,sys; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\",\"8000\")}/health'); sys.exit(0)"


# Runs the remote (HTTP) MCP transport because MCP_TRANSPORT=http is set above.
CMD ["python", "-m", "src.server"]
