FROM docker.io/python:3.12.2-slim

ENV TZ=Europe/Stockholm
ENV PATH=/root/.cargo/bin:$PATH

# Enable Swedish locale
RUN apt-get update && apt-get -y install locales
RUN sed -i '/sv_SE.UTF-8/s/^# //g' /etc/locale.gen && locale-gen

WORKDIR /app
RUN mkdir build
COPY . ./build
RUN pip install uv --no-cache-dir
RUN cd build && uv pip install --system --no-cache .
RUN pip uninstall --yes uv
RUN rm -rf ./build

CMD python -m tempapp run