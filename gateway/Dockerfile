FROM python:3.12-slim

WORKDIR /app

COPY gateway/requirements.txt gateway/requirements.txt
RUN pip install --no-cache-dir -r gateway/requirements.txt

COPY proto proto
COPY gateway gateway

# Generate the pb2 stubs at the repo root, matching `make proto`.
RUN python -m grpc_tools.protoc -I proto --python_out=. --grpc_python_out=. proto/node_registry.proto

ENV GRPC_TARGET=grpc-server:50051
EXPOSE 8080

CMD ["uvicorn", "gateway.app:app", "--host", "0.0.0.0", "--port", "8080"]
