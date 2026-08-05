# MockLegacyAPI, containerised so an experiment can start it the same way it
# starts Redis. Build context is the repository root: the service imports
# aep_core for the connector contract, so the package has to be present.
#
#   docker compose -f experiments/mock_api/compose.mock-api.yml up --build
FROM python:3.13-slim

# The lockfile is the artifact's reproducibility claim; installing without it
# would let this image drift from every other environment in the repository.
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv

WORKDIR /app

# Dependency layer first, so editing the service does not re-resolve.
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY aep_core ./aep_core
RUN uv sync --frozen --no-dev --extra experiments

COPY experiments ./experiments

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8099

# Overridden by compose to point at the mounted configuration.
CMD ["python", "-m", "experiments.mock_api", \
     "--config", "experiments/mock_api/config.example.yaml", \
     "--host", "0.0.0.0", "--port", "8099"]
