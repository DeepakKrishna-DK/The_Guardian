"""
Guardian Hub Remote Gateway Server
==================================
Exposes an authenticated remote interface over WireGuard/private network:
- REST API (Status, query, pairing lifecycle)
- WebSocket (Full-duplex real-time events, presence, voice interaction)
- Reuses PresenceBroadcaster architecture from presence_server.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Set

from fastapi import Depends, FastAPI, HTTPException, Header, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from guardian.core.presence_server import PresenceBroadcaster
from guardian.gateway.choke_point import GatewayChokePoint, GatewayProcessingResult
from guardian.gateway.network import get_bind_address
from guardian.gateway.pairing import DeviceRegistry, PairedDevice, get_device_registry
from guardian.logging.logger import get_logger

log = get_logger(__name__)

# Re-use global broadcaster singleton pattern
gateway_broadcaster = PresenceBroadcaster()


# ── Pydantic Request/Response Models ───────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    service: str = "guardian-hub-gateway"
    version: str = "0.1.0"
    timestamp: float


class PairInitiateRequest(BaseModel):
    device_name: str = Field(..., min_length=1, max_length=100)
    client_nonce: str = Field(..., min_length=8, max_length=128)


class PairInitiateResponse(BaseModel):
    request_id: str
    pairing_code: str
    expires_in_seconds: int
    message: str


class PairCompleteRequest(BaseModel):
    request_id: str
    client_nonce: str


class PairCompleteResponse(BaseModel):
    status: str
    device_id: Optional[str] = None
    token: Optional[str] = None
    message: str


class PairApproveRequest(BaseModel):
    code_or_request_id: str
    operator: str = "hub_operator"


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    success: bool
    content: str
    session_id: str
    error: Optional[str] = None
    blocked_by: Optional[str] = None
    metadata: Dict = Field(default_factory=dict)


# ── Dependency: Token Authentication ───────────────────────────────────────────

async def get_current_device(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> PairedDevice:
    """Validates the Authorization: Bearer <token> header against paired devices."""
    reg: DeviceRegistry = getattr(request.app.state, "registry", None) or get_device_registry()
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization scheme. Use 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    device = reg.validate_token(token)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, unapproved, or revoked device token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return device


# ── Application Factory ────────────────────────────────────────────────────────

def create_gateway_app(
    choke_point: Optional[GatewayChokePoint] = None,
    registry: Optional[DeviceRegistry] = None,
) -> FastAPI:
    """Factory function creating the FastAPI Gateway application."""
    app = FastAPI(
        title="Guardian Hub Remote Gateway",
        description="WireGuard-bound, auth-gated API for mobile and PWA clients.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    cp = choke_point or GatewayChokePoint()
    reg = registry or get_device_registry()

    app.state.registry = reg
    app.state.choke_point = cp

    start_time = time.time()

    # ── Public Endpoints ───────────────────────────────────────────────────────

    @app.get("/api/health", response_model=HealthResponse)
    async def health_check():
        return HealthResponse(
            status="ok",
            timestamp=time.time(),
        )

    # ── Pairing Lifecycle Endpoints ────────────────────────────────────────────

    @app.post("/api/pair/initiate", response_model=PairInitiateResponse)
    async def initiate_pairing(req: PairInitiateRequest):
        pending = reg.initiate_pairing(device_name=req.device_name, client_nonce=req.client_nonce)
        # Broadcast to local hub listeners that a device wants to pair
        gateway_broadcaster.broadcast_sync({
            "type": "pairing_requested",
            "device_name": req.device_name,
            "pairing_code": pending.pairing_code,
            "request_id": pending.request_id,
        })
        return PairInitiateResponse(
            request_id=pending.request_id,
            pairing_code=pending.pairing_code,
            expires_in_seconds=int(pending.expires_at - pending.created_at),
            message="Pairing initiated. Enter the pairing code displayed on the Guardian Hub to approve.",
        )

    @app.post("/api/pair/complete", response_model=PairCompleteResponse)
    async def complete_pairing(req: PairCompleteRequest):
        res = reg.complete_pairing(request_id=req.request_id, client_nonce=req.client_nonce)
        if res is None:
            # Check if pending or expired
            pending_list = [p for p in reg.list_pending() if p.request_id == req.request_id]
            if pending_list:
                return PairCompleteResponse(
                    status="pending_approval",
                    message="Device pairing is awaiting operator approval on the Guardian Hub.",
                )
            return PairCompleteResponse(
                status="rejected_or_expired",
                message="Pairing request not found, expired, or rejected.",
            )

        raw_token, device = res
        return PairCompleteResponse(
            status="paired",
            device_id=device.device_id,
            token=raw_token,
            message="Device paired successfully. Keep this token secure.",
        )

    @app.get("/api/pair/pending")
    async def list_pending_pairings():
        """Lists pending pairing requests (for hub operator review)."""
        pending = reg.list_pending()
        return [
            {
                "request_id": p.request_id,
                "pairing_code": p.pairing_code,
                "device_name": p.device_name,
                "created_at": p.created_at,
                "expires_at": p.expires_at,
                "is_approved": p.is_approved,
            }
            for p in pending
        ]

    @app.post("/api/pair/approve")
    async def approve_pairing_endpoint(req: PairApproveRequest):
        """Allows operator to approve a pending device pairing."""
        approved = reg.approve_pairing(code_or_request_id=req.code_or_request_id, operator=req.operator)
        if not approved:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pending pairing request not found or expired.",
            )
        return {
            "status": "approved",
            "request_id": approved.request_id,
            "device_name": approved.device_name,
            "approved_by": approved.approved_by,
        }

    # ── Authenticated Endpoints ────────────────────────────────────────────────

    @app.get("/api/status")
    async def get_hub_status(device: PairedDevice = Depends(get_current_device)):
        """Returns verified hub status and constitution hash."""
        from guardian.core.status import collect_status
        hub_status = collect_status()
        return {
            "device": {
                "device_id": device.device_id,
                "device_name": device.device_name,
                "paired_at": device.paired_at,
            },
            "hub": hub_status,
            "uptime_seconds": time.time() - start_time,
        }

    @app.post("/api/query", response_model=QueryResponse)
    async def submit_query(
        req: QueryRequest,
        device: PairedDevice = Depends(get_current_device),
    ):
        """Processes a query through the unified choke point."""
        # Broadcast thought/activity to all listeners
        gateway_broadcaster.broadcast_sync({
            "type": "query_started",
            "device_id": device.device_id,
            "device_name": device.device_name,
        })

        result: GatewayProcessingResult = cp.process_remote_request(
            user_input=req.query,
            device_id=device.device_id,
            device_name=device.device_name,
            session_id=req.session_id,
        )

        gateway_broadcaster.broadcast_sync({
            "type": "query_completed",
            "device_id": device.device_id,
            "success": result.success,
        })

        return QueryResponse(
            success=result.success,
            content=result.content,
            session_id=result.session_id,
            error=result.error,
            blocked_by=result.blocked_by,
            metadata=result.metadata,
        )

    # ── Authenticated WebSocket Endpoint ───────────────────────────────────────

    @app.websocket("/ws/gateway")
    async def websocket_gateway(
        websocket: WebSocket,
        token: Optional[str] = Query(None),
    ):
        """
        Full-duplex WebSocket stream for remote clients (voice, events, queries).
        Requires paired device token in query parameter (?token=...) or initial handshake.
        """
        active_reg = getattr(websocket.app.state, "registry", reg)
        device: Optional[PairedDevice] = None
        if token:
            device = active_reg.validate_token(token)
            if not device:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

        if not device:
            # Try waiting for an initial auth handshake message
            await websocket.accept()
            try:
                raw_auth = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                auth_data = json.loads(raw_auth)
                if auth_data.get("type") == "auth" and "token" in auth_data:
                    device = active_reg.validate_token(auth_data["token"])
            except Exception:
                pass

            if not device:
                await websocket.send_json({"type": "error", "message": "Authentication failed: invalid or revoked token"})
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        else:
            await websocket.accept()

        gateway_broadcaster.active_connections.add(websocket)
        await websocket.send_json({
            "type": "authenticated",
            "device_id": device.device_id,
            "device_name": device.device_name,
            "timestamp": time.time(),
        })

        try:
            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": time.time()})
                elif msg_type == "query":
                    query_text = msg.get("text", "")
                    sess_id = msg.get("session_id")
                    if query_text:
                        await websocket.send_json({"type": "status", "stage": "processing"})
                        res = cp.process_remote_request(
                            user_input=query_text,
                            device_id=device.device_id,
                            device_name=device.device_name,
                            session_id=sess_id,
                        )
                        await websocket.send_json({
                            "type": "response",
                            "success": res.success,
                            "content": res.content,
                            "session_id": res.session_id,
                            "error": res.error,
                            "blocked_by": res.blocked_by,
                        })
        except WebSocketDisconnect:
            gateway_broadcaster.disconnect(websocket)
        except Exception as e:
            log.warning(f"WebSocket client error: {e}")
            gateway_broadcaster.disconnect(websocket)

    return app


def run_gateway(
    host: Optional[str] = None,
    port: int = 8000,
    allow_insecure: bool = False,
) -> None:
    """
    Validates network binding constraints and starts the Gateway server via uvicorn.
    """
    bind_ip = get_bind_address(preferred_ip=host, allow_insecure=allow_insecure)
    log.info(f"Starting Guardian Hub Gateway on {bind_ip}:{port} (WireGuard-ready)")
    app = create_gateway_app()

    import uvicorn
    uvicorn.run(app, host=bind_ip, port=port)
