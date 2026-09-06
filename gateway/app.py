"""FastAPI gateway that translates REST calls into gRPC calls against the
NodeRegistry service."""
import os
import sys
from contextlib import asynccontextmanager
from typing import Dict, Optional

import grpc
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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
    address: str
    port: int
    metadata: Dict[str, str] = {}


def _node_to_dict(node: pb2.NodeResponse) -> dict:
    return {
        "id": node.id,
        "name": node.name,
        "address": node.address,
        "port": node.port,
        "metadata": dict(node.metadata),
        "status": node.status,
        "registered_at": node.registered_at,
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


@app.post("/nodes")
def register_node(body: RegisterBody):
    try:
        response = _stub.Register(
            pb2.RegisterRequest(
                name=body.name,
                address=body.address,
                port=body.port,
                metadata=body.metadata,
            )
        )
    except grpc.RpcError as exc:
        _grpc_error_to_http(exc)
    return _node_to_dict(response)


@app.get("/nodes")
def list_nodes():
    try:
        response = _stub.List(pb2.Empty())
    except grpc.RpcError as exc:
        _grpc_error_to_http(exc)
    return {"nodes": [_node_to_dict(n) for n in response.nodes]}


@app.get("/nodes/{node_id}")
def get_node(node_id: str):
    try:
        response = _stub.Get(pb2.GetRequest(id=node_id))
    except grpc.RpcError as exc:
        _grpc_error_to_http(exc)
    return _node_to_dict(response)


@app.delete("/nodes/{node_id}")
def delete_node(node_id: str):
    try:
        _stub.Delete(pb2.DeleteRequest(id=node_id))
    except grpc.RpcError as exc:
        _grpc_error_to_http(exc)
    return {"deleted": node_id}
