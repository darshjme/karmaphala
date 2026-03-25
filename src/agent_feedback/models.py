"""Data models for the feedback system."""

from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FeedbackType(str, Enum):
    APPROVAL = "approval"
    REJECTION = "rejection"
    CORRECTION = "correction"
    RATING = "rating"
    COMMENT = "comment"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class Feedback:
    """A single piece of human feedback on an agent action/response."""

    feedback_type: FeedbackType
    agent_output: Any                         # What the agent produced
    status: ApprovalStatus = ApprovalStatus.PENDING

    # Optional fields
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    corrected_output: Any = None              # What the human changed it to
    rating: Optional[float] = None           # e.g. 1-5 star
    comment: str = ""                        # Free text
    context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "feedback_type": self.feedback_type.value,
            "status": self.status.value,
            "agent_output": self.agent_output,
            "corrected_output": self.corrected_output,
            "rating": self.rating,
            "comment": self.comment,
            "context": self.context,
            "tags": self.tags,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Feedback":
        return cls(
            id=data["id"],
            feedback_type=FeedbackType(data["feedback_type"]),
            status=ApprovalStatus(data["status"]),
            agent_output=data["agent_output"],
            corrected_output=data.get("corrected_output"),
            rating=data.get("rating"),
            comment=data.get("comment", ""),
            context=data.get("context", {}),
            tags=data.get("tags", []),
            session_id=data.get("session_id"),
            timestamp=data.get("timestamp", time.time()),
        )

    @property
    def was_corrected(self) -> bool:
        return self.corrected_output is not None

    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp
