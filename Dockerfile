FROM python:3.11.7-slim

ENV PIP_DEFAULT_TIMEOUT=100
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV TZ=Europe/Stockholm

WORKDIR /app
RUN mkdir build
COPY . ./build
RUN cd build && pip install --no-cache-dir .
RUN rm -rf ./build

RUN apt-get update && apt-get -y install locales

# Enable Swedish locale
RUN sed -i '/sv_SE.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen

CMD python -m tempapp