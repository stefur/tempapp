FROM docker.io/python:3.12-slim-bookworm AS base
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Stockholm
ENV PATH=/app/.venv/bin:$PATH

# Enable Swedish locale
RUN apt-get update && apt-get -y --no-install-recommends install locales
RUN sed -i "/sv_SE.UTF-8/s/^# //g" /etc/locale.gen && locale-gen

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=true
ENV UV_LINK_MODE=copy

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev --no-editable
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM base

COPY --from=builder /app/.venv /app/.venv

ENTRYPOINT ["tempapp", "run"]
