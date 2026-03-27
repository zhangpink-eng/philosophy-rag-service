import asyncio
import json
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

from core.workshop_manager import workshop_manager, WorkshopPhase


class ConnectionManager:
    """Manage WebSocket connections for workshops"""

    def __init__(self):
        # room_id -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # websocket -> participant_id
        self.websocket_to_participant: Dict[WebSocket, str] = {}
        # websocket -> room_id
        self.websocket_to_room: Dict[WebSocket, str] = {}

    async def connect(
        self,
        websocket: WebSocket,
        room_id: str,
        participant_id: str
    ):
        """Accept and register websocket connection"""
        await websocket.accept()

        if room_id not in self.active_connections:
            self.active_connections[room_id] = set()

        self.active_connections[room_id].add(websocket)
        self.websocket_to_participant[websocket] = participant_id
        self.websocket_to_room[websocket] = room_id

    def disconnect(self, websocket: WebSocket):
        """Unregister websocket connection"""
        room_id = self.websocket_to_room.get(websocket)
        if room_id and room_id in self.active_connections:
            self.active_connections[room_id].discard(websocket)

        participant_id = self.websocket_to_participant.pop(websocket, None)
        self.websocket_to_room.pop(websocket, None)

        return room_id, participant_id

    async def broadcast(
        self,
        room_id: str,
        message: Dict,
        exclude: WebSocket = None
    ):
        """Broadcast message to all connections in room"""
        if room_id not in self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections[room_id]:
            if connection == exclude:
                continue
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected
        for conn in disconnected:
            self.disconnect(conn)

    async def send_personal(
        self,
        websocket: WebSocket,
        message: Dict
    ):
        """Send message to specific connection"""
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)


# Global connection manager
manager = ConnectionManager()


async def handle_workshop_websocket(websocket: WebSocket, room_id: str, participant_id: str):
    """Handle workshop WebSocket communication"""
    await manager.connect(websocket, room_id, participant_id)

    # Notify others about new participant
    room = workshop_manager.get_room(room_id)
    if room:
        participant = room.participants.get(participant_id)
        name = participant.name if participant else "Unknown"
        await manager.broadcast(room_id, {
            "type": "system",
            "event": "participant_joined",
            "participant_id": participant_id,
            "name": name,
            "participant_count": len(room.participants)
        })

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            await handle_workshop_message(
                websocket=websocket,
                room_id=room_id,
                participant_id=participant_id,
                message=message
            )

    except WebSocketDisconnect:
        room_id, p_id = manager.disconnect(websocket)
        if room_id:
            room = workshop_manager.get_room(room_id)
            if room and p_id:
                workshop_manager.leave_room(room_id, p_id)
                await manager.broadcast(room_id, {
                    "type": "system",
                    "event": "participant_left",
                    "participant_id": p_id,
                    "participant_count": len(room.participants) if room else 0
                })


async def handle_workshop_message(
    websocket: WebSocket,
    room_id: str,
    participant_id: str,
    message: Dict
):
    """Handle different types of workshop messages"""
    msg_type = message.get("type")
    room = workshop_manager.get_room(room_id)

    if not room:
        await manager.send_personal(websocket, {
            "type": "error",
            "message": "Room not found"
        })
        return

    if msg_type == "viewpoint":
        # Participant shares their viewpoint
        viewpoint = message.get("viewpoint", "")
        workshop_manager.set_viewpoint(room_id, participant_id, viewpoint)

        participant = room.participants.get(participant_id)
        name = participant.name if participant else "Unknown"

        await manager.broadcast(room_id, {
            "type": "viewpoint",
            "participant_id": participant_id,
            "name": name,
            "viewpoint": viewpoint
        })

    elif msg_type == "speak":
        # Add to speaking queue
        workshop_manager.add_to_queue(room_id, participant_id)
        await manager.broadcast(room_id, {
            "type": "queue_update",
            "queue": room.speaking_queue
        })

    elif msg_type == "next_speaker":
        # Get next speaker (host only)
        if participant_id == room.host_id:
            next_speaker = workshop_manager.get_next_speaker(room_id)
            if next_speaker:
                speaker_name = room.participants.get(next_speaker, Participant("", "", datetime.utcnow())).name
                await manager.broadcast(room_id, {
                    "type": "current_speaker",
                    "participant_id": next_speaker,
                    "name": speaker_name
                })

    elif msg_type == "start_discussion":
        # Start discussion phase
        if participant_id == room.host_id:
            workshop_manager.start_discussion(room_id)
            await manager.broadcast(room_id, {
                "type": "phase_change",
                "phase": WorkshopPhase.DISCUSSION.value
            })

    elif msg_type == "end_workshop":
        # End workshop
        if participant_id == room.host_id:
            summary = workshop_manager.generate_summary(room_id, room.topic)
            workshop_manager.end_workshop(room_id)
            await manager.broadcast(room_id, {
                "type": "workshop_ended",
                "summary": summary
            })

    elif msg_type == "oscar_intervention":
        # AI Oscar intervention (triggered by host or automatically)
        intervention_text = message.get("content", "")
        await manager.broadcast(room_id, {
            "type": "oscar",
            "participant_id": "oscar",
            "name": "Oscar",
            "content": intervention_text
        })

    elif msg_type == "get_participants":
        # Send participant list
        participants = [
            {
                "id": pid,
                "name": p.name,
                "viewpoint": room.viewpoints.get(pid),
                "is_active": p.is_active
            }
            for pid, p in room.participants.items()
        ]
        await manager.send_personal(websocket, {
            "type": "participants_list",
            "participants": participants,
            "phase": room.phase.value
        })


def cleanup_room(room_id: str):
    """Clean up room when workshop ends"""
    if room_id in manager.active_connections:
        del manager.active_connections[room_id]
