from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from core.workshop_manager import workshop_manager, WorkshopPhase
from api.websocket_handler import handle_workshop_websocket

router = APIRouter(prefix="/api/workshops", tags=["workshops"])


# ============ Workshop Schemas ============

class CreateRoomRequest(BaseModel):
    topic: str
    host_name: str
    max_participants: int = 10


class RoomResponse(BaseModel):
    room_id: str
    topic: str
    host_id: str
    phase: str
    participant_count: int
    websocket_url: str


class JoinRoomRequest(BaseModel):
    room_id: str
    participant_name: str


class ViewpointRequest(BaseModel):
    room_id: str
    participant_id: str
    viewpoint: str


class WorkshopSummaryResponse(BaseModel):
    topic: str
    participant_count: int
    viewpoints: List[dict]
    key_tensions: List[str]
    duration_minutes: int


# ============ Workshop Endpoints ============

@router.post("/create", response_model=RoomResponse)
async def create_workshop(request: CreateRoomRequest):
    """
    Create a new workshop room.

    Returns room details and WebSocket URL for joining.
    """
    host_id = f"host_{request.host_name}_{datetime.utcnow().timestamp()}"

    room = workshop_manager.create_room(
        host_id=host_id,
        topic=request.topic,
        max_participants=request.max_participants
    )

    # Add host as first participant
    workshop_manager.join_room(room.room_id, host_id, request.host_name)

    return RoomResponse(
        room_id=room.room_id,
        topic=room.topic,
        host_id=host_id,
        phase=room.phase.value,
        participant_count=len(room.participants),
        websocket_url=f"/ws/workshop/{room.room_id}"
    )


@router.post("/join")
async def join_workshop(request: JoinRoomRequest):
    """
    Join an existing workshop room.

    Returns participant credentials and WebSocket URL.
    """
    room = workshop_manager.get_room(request.room_id)

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.phase == WorkshopPhase.ENDED:
        raise HTTPException(status_code=400, detail="Workshop has ended")

    participant_id = f"p_{request.participant_name}_{datetime.utcnow().timestamp()}"

    result = workshop_manager.join_room(
        room_id=request.room_id,
        participant_id=participant_id,
        name=request.participant_name
    )

    if not result:
        raise HTTPException(status_code=400, detail="Room is full")

    return {
        "room_id": request.room_id,
        "participant_id": participant_id,
        "participant_name": request.participant_name,
        "phase": room.phase.value,
        "websocket_url": f"/ws/workshop/{request.room_id}",
        "topic": room.topic
    }


@router.get("/{room_id}")
async def get_workshop(room_id: str):
    """
    Get workshop room details.
    """
    room = workshop_manager.get_room(room_id)

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    return {
        "room_id": room.room_id,
        "topic": room.topic,
        "phase": room.phase.value,
        "host_id": room.host_id,
        "participant_count": len(room.participants),
        "max_participants": room.max_participants,
        "viewpoints": [
            {
                "participant_id": pid,
                "name": p.name,
                "viewpoint": room.viewpoints.get(pid)
            }
            for pid, p in room.participants.items()
        ]
    }


@router.get("/{room_id}/summary")
async def get_workshop_summary(room_id: str) -> WorkshopSummaryResponse:
    """
    Get workshop summary (only available after workshop ends).
    """
    room = workshop_manager.get_room(room_id)

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    summary = workshop_manager.generate_summary(room_id, room.topic)
    return WorkshopSummaryResponse(**summary)


@router.post("/viewpoint")
async def set_viewpoint(request: ViewpointRequest):
    """
    Set participant's viewpoint on the workshop topic.
    """
    success = workshop_manager.set_viewpoint(
        room_id=request.room_id,
        participant_id=request.participant_id,
        viewpoint=request.viewpoint
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to set viewpoint")

    return {"status": "success", "message": "Viewpoint updated"}


@router.post("/{room_id}/start")
async def start_discussion(room_id: str, host_id: str):
    """
    Start the discussion phase (host only).
    """
    room = workshop_manager.get_room(room_id)

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.host_id != host_id:
        raise HTTPException(status_code=403, detail="Only host can start discussion")

    workshop_manager.start_discussion(room_id)

    return {"status": "success", "phase": WorkshopPhase.DISCUSSION.value}


@router.post("/{room_id}/end")
async def end_workshop(room_id: str, host_id: str):
    """
    End the workshop (host only).
    """
    room = workshop_manager.get_room(room_id)

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.host_id != host_id:
        raise HTTPException(status_code=403, detail="Only host can end workshop")

    summary = workshop_manager.generate_summary(room_id, room.topic)
    workshop_manager.end_workshop(room_id)

    return {
        "status": "success",
        "summary": summary
    }


# ============ WebSocket Endpoint ============

@router.websocket("/ws/{room_id}")
async def workshop_websocket(websocket: WebSocket, room_id: str):
    """
    WebSocket endpoint for real-time workshop communication.

    Query params:
    - participant_id: Participant's unique ID
    """
    participant_id = websocket.query_params.get("participant_id")
    if not participant_id:
        await websocket.close(code=4000, reason="Missing participant_id")
        return

    await handle_workshop_websocket(websocket, room_id, participant_id)
