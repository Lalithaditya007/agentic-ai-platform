from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from uuid import UUID
import json

router = APIRouter()

# Simple in-memory connection manager
class ConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, run_id: str, ws: WebSocket):
        await ws.accept()
        self.active[run_id] = ws

    def disconnect(self, run_id: str):
        self.active.pop(run_id, None)

    async def send(self, run_id: str, data: dict):
        ws = self.active.get(run_id)
        if ws:
            await ws.send_text(json.dumps(data))

    async def broadcast(self, data: dict):
        for ws in self.active.values():
            await ws.send_text(json.dumps(data))


manager = ConnectionManager()


@router.websocket("/ws/workflow/{run_id}")
async def workflow_websocket(websocket: WebSocket, run_id: str):
    """Real-time workflow updates via WebSocket."""
    await manager.connect(run_id, websocket)
    try:
        while True:
            # Keep connection alive; updates are pushed from workflow engine
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(run_id)
