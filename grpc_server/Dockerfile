FROM python:3.12-slim

WORKDIR /app

# Root-level proto and gateway deps aren't needed here; grpc_server only.
COPY grpc_server/requirements.txt grpc_server/requirements.txt
RUN pip install --no-cache-dir -r grpc_server/requirements.txt

COPY proto proto
COPY grpc_server grpc_server

# Generate the pb2 stubs at the repo root, matching `make proto`.
RUN python -m grpc_tools.protoc -I proto --python_out=. --grpc_python_out=. proto/node_registry.proto

ENV GRPC_PORT=50051
EXPOSE 50051

CMD ["python", "-m", "grpc_server.server"]
