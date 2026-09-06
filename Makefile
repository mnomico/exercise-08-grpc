proto:
	python -m grpc_tools.protoc -I proto --python_out=. --grpc_python_out=. proto/node_registry.proto

run-grpc: proto
	python -m grpc_server.server

run-gateway:
	uvicorn gateway.app:app --host 0.0.0.0 --port 8080

up:
	docker compose up --build

down:
	docker compose down -v

test:
	pytest tests/ -v --tb=short
