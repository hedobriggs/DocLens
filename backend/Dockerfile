FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

# CPU inference is the default. Override the index explicitly for a GPU build.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

# Optional trust bundle for development environments with an HTTPS proxy.
# BuildKit mounts it only for this step; verification remains enabled.
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    pip install --no-cache-dir --index-url "$TORCH_INDEX_URL" "$(sed -n '/^torch==/p' requirements.txt)" && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
