"""FastAPI gateway that translates REST calls into gRPC calls against the
NodeRegistry service."""
import os
import sys
from contextlib import asynccontextmanager
from typing import Dict, Optional, List

import grpc
from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import node_registry_pb2 as pb2
import node_registry_pb2_grpc as pb2_grpc

GRPC_TARGET = os.environ.get("GRPC_TARGET", "grpc-server:50051")

_channel: Optional[grpc.Channel] = None
_stub: Optional[pb2_grpc.NodeRegistryStub] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _channel, _stub
    _channel = grpc.insecure_channel(GRPC_TARGET)
    _stub = pb2_grpc.NodeRegistryStub(_channel)
    yield
    _channel.close()


app = FastAPI(title="Node Registry Gateway", lifespan=lifespan)


class RegisterBody(BaseModel):
    name: str
    host: Optional[str] = None
    address: Optional[str] = None
    port: int
    metadata: Dict[str, str] = Field(default_factory=dict)

    def get_address(self) -> str:
        return self.address or self.host or ""


def _node_to_dict(node: pb2.NodeResponse) -> dict:
    return {
        "id": node.id,
        "name": node.name,
        "address": node.address,
        "host": node.address,
        "port": node.port,
        "metadata": dict(node.metadata),
        "status": node.status.lower() if node.status else "active",
        "registered_at": node.registered_at,
        "created_at": node.registered_at,
    }


def _grpc_error_to_http(exc: grpc.RpcError):
    code = exc.code()
    detail = exc.details()
    if code == grpc.StatusCode.NOT_FOUND:
        raise HTTPException(status_code=404, detail=detail)
    raise HTTPException(status_code=502, detail=detail or "gRPC call failed")


@app.get("/health")
def health():
    return {"status": "ok"}


# Helper functions
def do_register(body: RegisterBody):
    addr = body.get_address()
    try:
        response = _stub.Register(
            pb2.RegisterRequest(
                name=body.name,
                address=addr,
                port=body.port,
                metadata=body.metadata,
            )
        )
    except grpc.RpcError as exc:
        _grpc_error_to_http(exc)
    return _node_to_dict(response)


def do_list() -> List[dict]:
    try:
        response = _stub.List(pb2.Empty())
    except grpc.RpcError as exc:
        _grpc_error_to_http(exc)
    return [_node_to_dict(n) for n in response.nodes]


def do_get(node_id: str):
    try:
        response = _stub.Get(pb2.GetRequest(id=node_id))
    except grpc.RpcError as exc:
        _grpc_error_to_http(exc)
    return _node_to_dict(response)


def do_delete(node_id: str):
    try:
        _stub.Delete(pb2.DeleteRequest(id=node_id))
    except grpc.RpcError as exc:
        _grpc_error_to_http(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── /api/nodes routes ───────────────────────────────────────────────────────

@app.post("/api/nodes", status_code=status.HTTP_201_CREATED)
def api_register_node(body: RegisterBody):
    return do_register(body)


@app.get("/api/nodes")
def api_list_nodes():
    return do_list()


@app.get("/api/nodes/{node_id}")
def api_get_node(node_id: str):
    return do_get(node_id)


@app.delete("/api/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_node(node_id: str):
    return do_delete(node_id)


# ── /nodes routes (backward compatibility) ─────────────────────────────────

@app.post("/nodes", status_code=status.HTTP_201_CREATED)
def register_node(body: RegisterBody):
    return do_register(body)


@app.get("/nodes")
def list_nodes():
    return do_list()


@app.get("/nodes/{node_id}")
def get_node(node_id: str):
    return do_get(node_id)


@app.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(node_id: str):
    return do_delete(node_id)
