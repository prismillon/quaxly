FROM python:3.15-slim AS builder

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
# Each package (and its bundled .libs) is staged in its own subdir; the
# production stage puts the *contents* of those dirs on PYTHONPATH, so this does
# not depend on the interpreter's versioned site-packages path.
RUN SP=$(/app/.venv/bin/python -c 'import sysconfig; print(sysconfig.get_path("purelib"))') && \
  for p in pyogrio pandas numpy matplotlib pyproj shapely fontTools; do \
    mkdir -p "/app/heavy/$p" && \
    mv "$SP/$p" "/app/heavy/$p/" && \
    if [ -d "$SP/$p.libs" ]; then mv "$SP/$p.libs" "/app/heavy/$p/" ; fi ; \
  done && \
  mkdir -p /app/heavy/pyogrio.libs && \
  mv /app/heavy/pyogrio/pyogrio.libs /app/heavy/pyogrio.libs/

FROM python:3.15-slim AS production

RUN groupadd -r quaxly && useradd -r -g quaxly quaxly

# Reassemble the venv from several layers (base venv + one per heavy package) so
# no single pushed blob exceeds the registry's upload limit. The heavy packages
# go to a version-independent path on PYTHONPATH instead of being copied back
# into the interpreter's site-packages directory.
COPY --from=builder --chown=quaxly:quaxly /app/.venv /app/.venv
COPY --from=builder --chown=quaxly:quaxly /app/heavy/pyogrio/ /app/heavy/
COPY --from=builder --chown=quaxly:quaxly /app/heavy/pyogrio.libs/ /app/heavy/
COPY --from=builder --chown=quaxly:quaxly /app/heavy/pandas/ /app/heavy/
COPY --from=builder --chown=quaxly:quaxly /app/heavy/numpy/ /app/heavy/
COPY --from=builder --chown=quaxly:quaxly /app/heavy/matplotlib/ /app/heavy/
COPY --from=builder --chown=quaxly:quaxly /app/heavy/pyproj/ /app/heavy/
COPY --from=builder --chown=quaxly:quaxly /app/heavy/shapely/ /app/heavy/
COPY --from=builder --chown=quaxly:quaxly /app/heavy/fontTools/ /app/heavy/
COPY --chown=quaxly:quaxly . /app/

ENV PATH="/app/.venv/bin:$PATH" \
  PYTHONPATH="/app/heavy" \
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
USER quaxly

CMD ["python", "main.py"]
