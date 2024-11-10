FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:$PATH"
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Stockholm

# Enable Swedish locale
RUN apt-get update && apt-get -y --no-install-recommends install locales
RUN sed -i "/sv_SE.UTF-8/s/^# //g" /etc/locale.gen && locale-gen

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENTRYPOINT ["tempapp", "run"]