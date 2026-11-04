FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --locked --no-install-project --no-editable

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --locked --no-editable

# Split the heavy geospatial/data packages out of the venv so each becomes its
# own image layer. Otherwise the whole venv (geopandas + GDAL/PROJ/GEOS) ships
# as one ~270MB layer that exceeds the registry's per-blob upload limit and the
# push fails with 413. Keep this list in sync with the heavy dependencies.
# Each package (and its bundled .libs) is staged in its own subdir so that
# copying the subdir's *contents* in the production stage preserves the package
# directory layout as its own image layer.
RUN SP=/app/.venv/lib/python3.14/site-packages && \
  for p in pyogrio pandas numpy matplotlib pyproj shapely fontTools; do \
    mkdir -p "/app/heavy/$p" && \
    mv "$SP/$p" "/app/heavy/$p/" && \
    if [ -d "$SP/$p.libs" ]; then mv "$SP/$p.libs" "/app/heavy/$p/" ; fi ; \
  done && \
  mkdir -p /app/heavy/pyogrio.libs && \
  mv /app/heavy/pyogrio/pyogrio.libs /app/heavy/pyogrio.libs/

FROM python:3.14-slim AS production

RUN groupadd -r quaxly && useradd -r -g quaxly quaxly

# Reassemble the venv from several layers (base venv + one per heavy package) so
# no single pushed blob exceeds the registry's upload limit.
ARG SP=/app/.venv/lib/python3.14/site-packages
COPY --from=builder --chown=quaxly:quaxly /app/.venv /app/.venv
COPY --from=builder --chown=quaxly:quaxly /app/heavy/pyogrio/ ${SP}/
COPY --from=builder --chown=quaxly:quaxly /app/heavy/pyogrio.libs/ ${SP}/
COPY --from=builder --chown=quaxly:quaxly /app/heavy/pandas/ ${SP}/
COPY --from=builder --chown=quaxly:quaxly /app/heavy/numpy/ ${SP}/
COPY --from=builder --chown=quaxly:quaxly /app/heavy/matplotlib/ ${SP}/
COPY --from=builder --chown=quaxly:quaxly /app/heavy/pyproj/ ${SP}/
COPY --from=builder --chown=quaxly:quaxly /app/heavy/shapely/ ${SP}/
COPY --from=builder --chown=quaxly:quaxly /app/heavy/fontTools/ ${SP}/
COPY --chown=quaxly:quaxly . /app/

ENV PATH="/app/.venv/bin:$PATH" \
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
USER quaxly

CMD ["python", "main.py"]
