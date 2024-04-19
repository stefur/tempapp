FROM docker.io/python:3.12.2-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Stockholm
ENV UV_SYSTEM_PYTHON=true
ENV UV_NO_CACHE=true

# Enable Swedish locale and install uv
RUN apt-get update && apt-get -y install locales
RUN sed -i '/sv_SE.UTF-8/s/^# //g' /etc/locale.gen && locale-gen

RUN pip install uv --no-cache-dir

WORKDIR /app/build
COPY requirements.lock .
RUN sed '/^-e file:/d' requirements.lock > constraints.txt
RUN uv pip sync constraints.txt
COPY . .
RUN uv pip install "tempapp @ ."

WORKDIR /app
RUN rm -rf build

ENTRYPOINT ["python", "-m", "tempapp", "run"]