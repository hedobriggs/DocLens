# syntax=docker/dockerfile:1
# Build the existing portable images first; no dependencies install at Pod boot.
ARG FRONTEND_IMAGE=doclens-portable-frontend:compose-auto
ARG BACKEND_IMAGE=doclens-portable-backend:compose-auto
FROM qdrant/qdrant:v1.15.5@sha256:0fb8897412abc81d1c0430a899b9a81eb8328aa634e7242d1bc804c1fe8fe863 AS qdrant
FROM ${FRONTEND_IMAGE} AS bundle
USER root
RUN mkdir -p /bundle/opt/frontend /bundle/opt/qdrant /bundle/opt/runpod /bundle/usr/local/bin && cp -a /app/. /bundle/opt/frontend/ && cp /usr/local/bin/node /bundle/usr/local/bin/node
# Preserve Qdrant's matching runtime loader/libraries (Debian 13), isolated from
# Python/Node's Debian 12 libraries. Do not replace system libc.
COPY --from=qdrant /qdrant/qdrant /bundle/opt/qdrant/qdrant
COPY --from=qdrant /lib/x86_64-linux-gnu/ /bundle/opt/qdrant/lib/
COPY --chmod=0444 supervisor.py /bundle/opt/runpod/supervisor.py
FROM ${BACKEND_IMAGE}
USER root
COPY --from=bundle /bundle/ /
ENV QDRANT__SERVICE__HOST=127.0.0.1 QDRANT__SERVICE__HTTP_PORT=6333 QDRANT__SERVICE__GRPC_PORT=6334 QDRANT__TELEMETRY_DISABLED=true
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=4 CMD ["python", "/opt/runpod/supervisor.py", "health"]
ENTRYPOINT ["python", "/opt/runpod/supervisor.py"]
