# syntax=docker/dockerfile:1
# Context: repository root. Existing portable images contain dependencies/models.
ARG FRONTEND_IMAGE=doclens-portable-frontend:compose-auto
ARG BACKEND_IMAGE=doclens-portable-backend:compose-auto
ARG GRAFANA_IMAGE=grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f
FROM ${FRONTEND_IMAGE} AS frontend
FROM qdrant/qdrant:v1.15.5@sha256:0fb8897412abc81d1c0430a899b9a81eb8328aa634e7242d1bc804c1fe8fe863 AS qdrant
FROM prom/prometheus@sha256:fa3302279710be2f21a8301ec17a8b4f2301fd829bd113839b3b6b02b6f191a2 AS prometheus
FROM ${GRAFANA_IMAGE} AS grafana
FROM ${BACKEND_IMAGE}
USER root
# One assembly step also avoids excessive temporary copies on VFS Docker hosts.
RUN --mount=type=bind,from=frontend,source=/app,target=/tmp/frontend \
    --mount=type=bind,from=frontend,source=/usr/local/bin/node,target=/tmp/node \
    --mount=type=bind,from=qdrant,source=/qdrant/qdrant,target=/tmp/qdrant \
    --mount=type=bind,from=qdrant,source=/lib/x86_64-linux-gnu,target=/tmp/qdrant-lib \
    --mount=type=bind,from=prometheus,source=/,target=/tmp/prometheus-source \
    --mount=type=bind,from=grafana,source=/usr/share/grafana,target=/tmp/grafana \
    --mount=type=bind,source=deploy/runpod/supervisor.py,target=/tmp/supervisor.py \
    --mount=type=bind,source=deploy/runpod/monitoring_gateway.py,target=/tmp/monitoring_gateway.py \
    --mount=type=bind,source=deploy/monitoring,target=/tmp/monitoring \
    mkdir -p /opt/frontend /opt/qdrant/lib /opt/runpod /opt/prometheus /opt/monitoring/dashboards /opt/grafana/bin && \
    cp -a /tmp/frontend/. /opt/frontend/ && cp /tmp/node /usr/local/bin/node && \
    cp /tmp/qdrant /opt/qdrant/qdrant && cp -a /tmp/qdrant-lib/. /opt/qdrant/lib/ && \
    cp /tmp/prometheus-source/bin/prometheus /opt/prometheus/prometheus && cp /tmp/prometheus-source/LICENSE /tmp/prometheus-source/NOTICE /opt/prometheus/ && \
    cp /tmp/grafana/bin/grafana /opt/grafana/bin/grafana && \
    cp -a /tmp/grafana/data /tmp/grafana/conf /tmp/grafana/public /tmp/grafana/LICENSE /opt/grafana/ && \
    cp -a /tmp/monitoring/provisioning /opt/monitoring/ && \
    cp /tmp/monitoring/prometheus.yml /opt/monitoring/prometheus.yml && \
    cp /tmp/monitoring/dashboards/doclens.json /opt/monitoring/dashboards/doclens.json && \
    cp /tmp/supervisor.py /opt/runpod/supervisor.py && cp /tmp/monitoring_gateway.py /opt/runpod/monitoring_gateway.py && chmod 0444 /opt/runpod/*.py && \
    sed -i "s|http://prometheus:9090|http://prometheus:19090|" /opt/monitoring/provisioning/datasources/prometheus.yml && \
    find /opt/monitoring -type d -exec chmod 0755 {} + && \
    find /opt/monitoring -type f -exec chmod 0444 {} + && \
    chmod -R a+rX /opt/grafana && chmod 0755 /opt/prometheus/prometheus
ENV DOCLENS_MONITORING=1 QDRANT__SERVICE__HOST=127.0.0.1 QDRANT__SERVICE__HTTP_PORT=6333 QDRANT__SERVICE__GRPC_PORT=6334 QDRANT__TELEMETRY_DISABLED=true
EXPOSE 3000 3001 9090
HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=4 CMD ["python", "/opt/runpod/supervisor.py", "health"]
ENTRYPOINT ["python", "/opt/runpod/supervisor.py"]
