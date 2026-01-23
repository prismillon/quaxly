FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --locked --no-install-project --no-editable

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --locked --no-editable

FROM python:3.14-slim AS production

RUN groupadd -r quaxly && useradd -r -g quaxly quaxly

COPY --from=builder --chown=quaxly:quaxly /app/.venv /app/.venv
COPY --chown=quaxly:quaxly . /app/

ENV PATH="/app/.venv/bin:$PATH" \
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
USER quaxly

CMD ["python", "main.py"]