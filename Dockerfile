FROM docker.io/python:3.12.2-slim
COPY --from=ghcr.io/astral-sh/uv:0.3.1 /uv /bin/uv

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Stockholm
ENV UV_SYSTEM_PYTHON=true
ENV UV_NO_CACHE=true
ENV UV_LINK_MODE=copy

# Enable Swedish locale
RUN apt-get update && apt-get -y install locales
RUN sed -i '/sv_SE.UTF-8/s/^# //g' /etc/locale.gen && locale-gen

WORKDIR /app
COPY pyproject.toml .
RUN uv pip install -r pyproject.toml
COPY . .
RUN uv pip install -e .
RUN rm -rf /bin/uv

ENTRYPOINT ["python", "-m", "tempapp", "run"]