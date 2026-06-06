# Go2 × DimOS agentic blueprint — portable container.
#
# Image runs `dimos run unitree-go2-agentic` against a real Unitree Go2 over
# WebRTC. Use `--network host` so the container shares the host's NIC (Go2 on
# 192.168.123.x) and loopback (dimos's LCM multicast).
#
# Build:   docker build -t go2-agentic -f docker/Dockerfile .
# Run:     ./docker/run.sh
# Send NL: ./docker/say.sh "前に進んで"

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python \
    VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:/usr/local/bin:/usr/bin:/bin

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.12 python3.12-venv python3.12-dev \
        iproute2 iputils-ping netcat-openbsd \
        ca-certificates curl tini \
        libgl1 libglib2.0-0 libgomp1 \
        libturbojpeg0-dev \
        libxext6 libxrender1 libxrandr2 libxcursor1 libxinerama1 libxi6 libxfixes3 \
    && rm -rf /var/lib/apt/lists/*

# uv pinned to the version used to build the local venv (reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /usr/local/bin/uv

WORKDIR /app

# 1) Python deps — frozen from the working local venv
COPY docker/requirements.txt /app/requirements.txt
RUN uv venv --python python3.12 /app/.venv \
 && uv pip install --python /app/.venv/bin/python --no-cache -r /app/requirements.txt

# 2) Drop the dimos_interface stub into site-packages (upstream packaging gap)
COPY docker/dimos_interface_stub /tmp/dimos_interface
RUN cp -r /tmp/dimos_interface /app/.venv/lib/python3.12/site-packages/dimos/web/dimos_interface \
 && rm -rf /tmp/dimos_interface

# 3) Application scripts (run_robot.sh, say.sh, say_robot.py, standup.py).
#    Build context is `dimensional-applications/` (see run.sh / docker-compose.yml),
#    so these paths are relative to that.
COPY run_robot.sh say.sh say_robot.py standup.py /app/dimensional-applications/
RUN chmod +x /app/dimensional-applications/*.sh /app/dimensional-applications/*.py \
 && ln -s /app/.venv /app/dimensional-applications/.venv

# 4) Entrypoint — set up LCM multicast on the (shared host) loopback, then exec
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
CMD ["dimos", "run", "unitree-go2-agentic"]
