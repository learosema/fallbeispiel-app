FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 HF_HOME=/models
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend ./backend
COPY public ./public
COPY content ./content
EXPOSE 8000
# Client-IP aus X-Forwarded-For übernehmen (für RATE_LIMIT): Port 8000 ist nur lokal und für Caddy erreichbar,
# Caddy setzt den Header selbst.
CMD ["uv", "run", "--no-sync", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
