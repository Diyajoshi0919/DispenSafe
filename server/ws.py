"""WebSocket hub: pushes live updates to every open dashboard."""
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sessions import COOKIE_NAME, staff_from_session

router = APIRouter()


class Hub:
    def __init__(self):
        self.sockets: set[WebSocket] = set()

    async def broadcast(self, event: str, data: dict):
        message = json.dumps({"event": event, "data": data})
        for ws in list(self.sockets):
            try:
                await ws.send_text(message)
            except Exception:
                self.sockets.discard(ws)


hub = Hub()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    if not staff_from_session(ws.cookies.get(COOKIE_NAME)):
        await ws.close(code=4401)  # not logged in
        return
    await ws.accept()
    hub.sockets.add(ws)
    try:
        while True:
            await ws.receive_text()  # pages send "ping" every ~25 s to keep the connection open
    except WebSocketDisconnect:
        hub.sockets.discard(ws)
