"""gRPC server exposing the NodeRegistry service, with health-check and
reflection enabled, backed by Postgres via SQLAlchemy."""
import logging
import os
import sys
from concurrent import futures

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection
from sqlalchemy import or_

# Make the repo root importable so the generated *_pb2 modules (which live
# at the repo root, per the Makefile's --python_out=.) can be found both
# when run locally and inside the container.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import node_registry_pb2 as pb2
import node_registry_pb2_grpc as pb2_grpc

from grpc_server.db import Node, SessionLocal, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("grpc_server")

GRPC_PORT = os.environ.get("GRPC_PORT", "50051")


def _node_to_response(node: Node) -> pb2.NodeResponse:
    return pb2.NodeResponse(
        id=str(node.id),
        name=node.name,
        address=node.address,
        port=node.port,
        metadata=node.metadata_json or {},
        status=node.status,
        registered_at=node.registered_at.isoformat() if node.registered_at else "",
    )


class NodeRegistryServicer(pb2_grpc.NodeRegistryServicer):
    def Register(self, request, context):
        db = SessionLocal()
        try:
            node = Node(
                name=request.name,
                address=request.address,
                port=request.port,
                metadata_json=dict(request.metadata),
                status="ACTIVE",
            )
            db.add(node)
            db.commit()
            db.refresh(node)
            logger.info("Registered node %s (%s:%s)", node.id, node.address, node.port)
            return _node_to_response(node)
        finally:
            db.close()

    def List(self, request, context):
        db = SessionLocal()
        try:
            nodes = db.query(Node).order_by(Node.registered_at.asc()).all()
            return pb2.NodeList(nodes=[_node_to_response(n) for n in nodes])
        finally:
            db.close()

    def Get(self, request, context):
        db = SessionLocal()
        try:
            node = db.query(Node).filter(
                or_(Node.id == request.id, Node.name == request.id)
            ).first()
            if node is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Node {request.id} not found")
                return pb2.NodeResponse()
            return _node_to_response(node)
        finally:
            db.close()

    def Delete(self, request, context):
        db = SessionLocal()
        try:
            node = db.query(Node).filter(
                or_(Node.id == request.id, Node.name == request.id)
            ).first()
            if node is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Node {request.id} not found")
                return pb2.Empty()
            db.delete(node)
            db.commit()
            logger.info("Deleted node %s", request.id)
            return pb2.Empty()
        finally:
            db.close()


def serve():
    init_db()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_NodeRegistryServicer_to_server(NodeRegistryServicer(), server)

    # Health check service (grpc.health.v1.Health)
    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    health_servicer.set(
        "noderegistry.NodeRegistry", health_pb2.HealthCheckResponse.SERVING
    )

    # Server reflection, so tools like grpcurl / grpcui can introspect the API
    service_names = (
        pb2.DESCRIPTOR.services_by_name["NodeRegistry"].full_name,
        health_pb2.DESCRIPTOR.services_by_name["Health"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    bind_addr = f"[::]:{GRPC_PORT}"
    server.add_insecure_port(bind_addr)
    server.start()
    logger.info("gRPC server listening on %s", bind_addr)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
