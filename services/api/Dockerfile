# Multi-stage: build deps in a full image, run in a slim one — keeps the
# image CI pushes to Container Registry small and reduces attack surface.
FROM python:3.11-slim AS builder

WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.11-slim

# Runs as a non-root user — least-privilege inside the container, on top of
# the managed-identity/no-admin-keys posture in infra/bicep/modules/container-apps.bicep.
RUN useradd --create-home --uid 1000 ipacgs
COPY --from=builder /install /usr/local
COPY --from=builder /build/src /app/src

WORKDIR /app
ENV PYTHONPATH=/app/src
USER ipacgs

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

CMD ["uvicorn", "ipacgs.main:app", "--host", "0.0.0.0", "--port", "8000"]
