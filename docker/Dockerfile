FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y python3 python3-pip git \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m sandbox
USER sandbox

WORKDIR /workspace
