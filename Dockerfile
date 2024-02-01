FROM python:3.11.7-slim

ENV ARGS=

ENV PIP_DEFAULT_TIMEOUT=100
ENV PYTHONUNBUFFERED=1 
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get -y install locales

# Enable Swedish locale
RUN sed -i '/sv_SE.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen

RUN mkdir /db

CMD uvicorn $ARGS