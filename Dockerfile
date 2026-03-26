# --------------> The build image
FROM python:3.12-slim-bookworm AS build

WORKDIR /usr/src/app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependencies files
COPY pyproject.toml uv.lock ./

# Install production dependencies
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code files
COPY main.py alembic.ini ./
COPY agent_platform agent_platform
COPY alembic alembic

# --------------> The production image
FROM python:3.12-slim-bookworm

ARG COMMIT_ID
ARG BUILD_DATE

ENV COMMIT_ID=${COMMIT_ID}
ENV BUILD_DATE=${BUILD_DATE}

WORKDIR /usr/src/app

ENV HOME=/usr/src/app

# Copy virtual environment and source code from build stage
COPY --from=build /usr/src/app/.venv /usr/src/app/.venv
COPY --from=build /usr/src/app/main.py /usr/src/app/main.py
COPY --from=build /usr/src/app/alembic.ini /usr/src/app/alembic.ini
COPY --from=build /usr/src/app/agent_platform /usr/src/app/agent_platform
COPY --from=build /usr/src/app/alembic /usr/src/app/alembic

# Add venv to PATH
ENV PATH="/usr/src/app/.venv/bin:$PATH"

CMD ["python", "main.py"]
