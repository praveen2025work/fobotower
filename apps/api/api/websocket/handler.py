"""run.progress emitter.

Phase 1 replays node progress for one session so the console can render the
stream. Phase 2 emits it live from the running graph. The event shape is the
contract and does not change between the two.
"""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.contracts.models import RunProgress

router = APIRouter()

NODE_SEQUENCE = ["resolve", "gather", "group", "rank", "draft", "validate", "review"]
TOTAL_BREAKS = 14
STEP_DELAY_SECONDS = 0.15


@router.websocket("/api/ws/runs")
async def runs_socket(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_json()
            session_id = msg.get("session_id")
            if not session_id:
                continue
            for i, node in enumerate(NODE_SEQUENCE, start=1):
                await ws.send_json(
                    RunProgress(
                        session_id=session_id,
                        node=node,
                        breaks_processed=round(TOTAL_BREAKS * i / len(NODE_SEQUENCE)),
                        breaks_total=TOTAL_BREAKS,
                    ).model_dump(mode="json")
                )
                await asyncio.sleep(STEP_DELAY_SECONDS)
    except WebSocketDisconnect:
        return
