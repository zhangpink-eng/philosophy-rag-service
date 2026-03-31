import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum


class WorkshopPhase(Enum):
    """Workshop phase"""
    WAITING = "waiting"           # 等待开始
    INTRODUCING = "introducing"   # 命题引入
    DISCUSSION = "discussion"      # 讨论中
    CONCLUSION = "conclusion"     # 总结
    ENDED = "ended"              # 已结束


@dataclass
class Participant:
    """Workshop participant"""
    id: str
    name: str
    joined_at: datetime
    viewpoint: Optional[str] = None
    is_active: bool = True


@dataclass
class WorkshopRoom:
    """Workshop room"""
    room_id: str
    topic: str
    host_id: str
    phase: WorkshopPhase = WorkshopPhase.WAITING
    participants: Dict[str, Participant] = field(default_factory=dict)
    speaking_queue: List[str] = field(default_factory=list)  # participant IDs
    viewpoints: Dict[str, str] = field(default_factory=dict)  # participant_id -> viewpoint
    created_at: datetime = field(default_factory=datetime.utcnow)
    max_participants: int = 10


@dataclass
class WorkshopMessage:
    """Workshop message"""
    type: str  # join/leave/speak/viewpoint/intervention/summary
    room_id: str
    participant_id: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Optional[Dict] = None


class WorkshopManager:
    """
    Workshop collaboration manager.

    Handles:
    - Room creation and management
    - Participant tracking
    - Speaking order management
    - Viewpoint tracking
    - AI Oscar interventions
    """

    def __init__(self):
        self.rooms: Dict[str, WorkshopRoom] = {}
        self.room_by_host: Dict[str, str] = {}  # host_id -> room_id

    def create_room(
        self,
        host_id: str,
        topic: str,
        max_participants: int = 10
    ) -> WorkshopRoom:
        """Create a new workshop room"""
        room_id = f"room_{uuid.uuid4().hex[:12]}"
        room = WorkshopRoom(
            room_id=room_id,
            topic=topic,
            host_id=host_id,
            max_participants=max_participants
        )
        self.rooms[room_id] = room
        self.room_by_host[host_id] = room_id
        return room

    def get_room(self, room_id: str) -> Optional[WorkshopRoom]:
        """Get room by ID"""
        return self.rooms.get(room_id)

    def get_room_by_host(self, host_id: str) -> Optional[WorkshopRoom]:
        """Get room by host ID"""
        room_id = self.room_by_host.get(host_id)
        return self.rooms.get(room_id) if room_id else None

    def join_room(
        self,
        room_id: str,
        participant_id: str,
        name: str
    ) -> Optional[WorkshopRoom]:
        """Add participant to room"""
        room = self.rooms.get(room_id)
        if not room:
            return None

        if len(room.participants) >= room.max_participants:
            return None

        participant = Participant(
            id=participant_id,
            name=name,
            joined_at=datetime.utcnow()
        )
        room.participants[participant_id] = participant
        return room

    def leave_room(self, room_id: str, participant_id: str) -> bool:
        """Remove participant from room"""
        room = self.rooms.get(room_id)
        if not room:
            return False

        if participant_id in room.participants:
            del room.participants[participant_id]
            if participant_id in room.speaking_queue:
                room.speaking_queue.remove(participant_id)
            return True
        return False

    def set_viewpoint(
        self,
        room_id: str,
        participant_id: str,
        viewpoint: str
    ) -> bool:
        """Append participant's viewpoint to history (never overwrites)"""
        room = self.rooms.get(room_id)
        if not room:
            return False

        # Append to history list, never overwrite
        if participant_id not in room.viewpoints:
            room.viewpoints[participant_id] = []
        if not isinstance(room.viewpoints[participant_id], list):
            room.viewpoints[participant_id] = [room.viewpoints[participant_id]]
        room.viewpoints[participant_id].append({
            "text": viewpoint,
            "timestamp": datetime.utcnow().isoformat()
        })
        participant = room.participants.get(participant_id)
        if participant:
            participant.viewpoint = viewpoint
        return True

    def add_to_queue(self, room_id: str, participant_id: str) -> bool:
        """Add participant to speaking queue"""
        room = self.rooms.get(room_id)
        if not room:
            return False

        if participant_id not in room.speaking_queue:
            room.speaking_queue.append(participant_id)
        return True

    def get_next_speaker(self, room_id: str) -> Optional[str]:
        """Get next speaker from queue"""
        room = self.rooms.get(room_id)
        if not room or not room.speaking_queue:
            return None
        return room.speaking_queue.pop(0)

    def start_discussion(self, room_id: str) -> bool:
        """Start discussion phase"""
        room = self.rooms.get(room_id)
        if not room:
            return False

        room.phase = WorkshopPhase.DISCUSSION
        return True

    def end_workshop(self, room_id: str) -> bool:
        """End workshop"""
        room = self.rooms.get(room_id)
        if not room:
            return False

        room.phase = WorkshopPhase.ENDED
        return True

    def get_participant_viewpoints(self, room_id: str) -> List[Dict]:
        """Get all participants' viewpoints"""
        room = self.rooms.get(room_id)
        if not room:
            return []

        return [
            {
                "participant_id": pid,
                "name": p.name,
                "current_viewpoint": room.viewpoints.get(pid, [{"text": ""}])[-1]["text"] if isinstance(room.viewpoints.get(pid), list) else room.viewpoints.get(pid, ""),
                "viewpoint_history": room.viewpoints.get(pid, []),
                "is_active": p.is_active
            }
            for pid, p in room.participants.items()
        ]

    def generate_summary(
        self,
        room_id: str,
        topic: str
    ) -> Dict:
        """Generate workshop summary"""
        room = self.rooms.get(room_id)
        if not room:
            return {}

        viewpoints = self.get_participant_viewpoints(room_id)

        # Find key tensions (different viewpoints)
        tensions = []
        viewpoint_list = [v["viewpoint"] for v in viewpoints if v["viewpoint"]]
        if len(viewpoint_list) >= 2:
            tensions.append(f"关于'{topic}'，参与者有不同的理解")

        return {
            "topic": topic,
            "participant_count": len(room.participants),
            "viewpoints": viewpoints,
            "key_tensions": tensions,
            "duration_minutes": int(
                (datetime.utcnow() - room.created_at).total_seconds() / 60
            )
        }


# Global instance
workshop_manager = WorkshopManager()
