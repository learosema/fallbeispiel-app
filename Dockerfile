FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 HF_HOME=/models
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
# Vorab vertonte Clips (tools/tts; Referenzstimmen bleiben draußen, .dockerignore). Vor dem Code, weil sie sich seltener
# ändern – so bleibt die Schicht bei Code-Änderungen im Build-Cache. Die Piper-Stimmen (Leitstelle, AED) lädt der Server
# beim Start nach /models.
COPY audio ./audio
COPY backend ./backend
COPY public ./public
COPY content ./content
EXPOSE 8000
# Client-IP aus X-Forwarded-For übernehmen (für RATE_LIMIT). Port 8000 ist nur lokal erreichbar, also kommt jede
# Verbindung vom Reverse Proxy; der muss den Header mit der echten Client-IP überschreiben. In .env änderbar.
ENV FORWARDED_ALLOW_IPS="*"
CMD ["uv", "run", "--no-sync", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
