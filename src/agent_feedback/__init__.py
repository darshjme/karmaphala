"""
agent-feedback: Human-in-the-loop feedback collection for LLM agents.

Provides approval gates, correction capture, feedback storage,
and learning from rejections — zero dependencies, pure Python.
"""

from .models import Feedback, FeedbackType, ApprovalStatus
from .store import FeedbackStore
from .gates import ApprovalGate, AsyncApprovalGate
from .collector import FeedbackCollector
from .learner import RejectionLearner

__all__ = [
    "Feedback",
    "FeedbackType",
    "ApprovalStatus",
    "FeedbackStore",
    "ApprovalGate",
    "AsyncApprovalGate",
    "FeedbackCollector",
    "RejectionLearner",
]

__version__ = "0.1.0"
