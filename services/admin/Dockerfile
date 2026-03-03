FROM python:3.11-slim

WORKDIR /app

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

COPY services/admin/pyproject.toml .
RUN uv pip install --system --no-cache -r pyproject.toml

COPY services/admin/src ./src

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
