# AI Notebook Playground Container
# Headless Jupyter kernel with LLM integration
#
# This container provides isolated code execution for each notebook project.
# It exposes a FastAPI server for kernel operations, code execution, and LLM chat.

FROM python:3.11-slim

# Build arguments for customization
ARG PLAYGROUND_PORT=8888

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYGROUND_PORT=${PLAYGROUND_PORT} \
    # Default to Ollama (can be overridden at runtime)
    LLM_PROVIDER=ollama \
    OLLAMA_URL=http://host.docker.internal:11434/v1 \
    OLLAMA_MODEL=qwen3-coder:30b \
    TOOL_EXECUTION_MODE=manual

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash playground && \
    mkdir -p /app /notebooks /workspace && \
    chown -R playground:playground /app /notebooks /workspace

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.dev.txt /app/

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.dev.txt

# Copy backend code and fix permissions
COPY --chown=playground:playground backend/ /app/backend/

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Health check function\n\
check_health() {\n\
    curl -sf http://localhost:${PLAYGROUND_PORT}/health > /dev/null 2>&1\n\
}\n\
\n\
echo "Starting AI Notebook Playground..."\n\
echo "Port: ${PLAYGROUND_PORT}"\n\
echo "LLM Provider: ${LLM_PROVIDER}"\n\
echo "Ollama URL: ${OLLAMA_URL}"\n\
\n\
# Start the server\n\
exec python -m uvicorn backend.server:app \\\n\
    --host 0.0.0.0 \\\n\
    --port ${PLAYGROUND_PORT} \\\n\
    --log-level info\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Switch to non-root user
USER playground

# Expose the port
EXPOSE ${PLAYGROUND_PORT}

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:${PLAYGROUND_PORT}/health || exit 1

# Default command
CMD ["/app/entrypoint.sh"]
