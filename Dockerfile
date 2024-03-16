FROM debian:stable-slim

ENV TZ=Europe/Stockholm
ENV PATH=/root/.rye/shims:$PATH

WORKDIR /app
COPY . .

RUN apt update && apt install curl locales --yes
RUN export RYE_TOOLCHAIN_VERSION=$(cat .python-version) && \
    curl -sSf https://rye-up.com/get | RYE_VERSION="0.29.0" RYE_TOOLCHAIN_VERSION="$RYE_TOOLCHAIN_VERSION" RYE_INSTALL_OPTION="--yes" bash
RUN rye sync --no-lock --no-dev

# Enable Swedish locale
RUN sed -i '/sv_SE.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen

CMD rye run tempapp