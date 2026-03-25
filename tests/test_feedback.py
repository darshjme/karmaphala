"""Tests for agent-feedback library"""
import pytest
from agent_feedback.models import Feedback, FeedbackType, ApprovalStatus
from agent_feedback.store import FeedbackStore
from agent_feedback.collector import FeedbackCollector
from agent_feedback.learner import RejectionLearner
from agent_feedback.gates import ApprovalGate, AsyncApprovalGate


# ── Models ──────────────────────────────────────────────────────────────────

def test_feedback_creation():
    fb = Feedback(FeedbackType.REJECTION, agent_output="bad output")
    assert fb.status == ApprovalStatus.PENDING
    assert fb.id is not None
    assert fb.timestamp > 0


def test_feedback_to_dict_roundtrip():
    fb = Feedback(
        FeedbackType.CORRECTION,
        agent_output="wrong",
        corrected_output="right",
        rating=4.0,
        comment="needs work",
        tags=["accuracy"],
        session_id="s1",
    )
    d = fb.to_dict()
    fb2 = Feedback.from_dict(d)
    assert fb2.id == fb.id
    assert fb2.feedback_type == FeedbackType.CORRECTION
    assert fb2.corrected_output == "right"
    assert fb2.tags == ["accuracy"]


def test_was_corrected():
    fb = Feedback(FeedbackType.CORRECTION, agent_output="x", corrected_output="y")
    assert fb.was_corrected is True
    fb2 = Feedback(FeedbackType.REJECTION, agent_output="x")
    assert fb2.was_corrected is False


# ── FeedbackStore ────────────────────────────────────────────────────────────

def test_store_save_and_get():
    store = FeedbackStore()
    fb = Feedback(FeedbackType.APPROVAL, agent_output="x")
    fid = store.save(fb)
    assert store.get(fid) is fb


def test_store_query_by_status():
    store = FeedbackStore()
    fb1 = Feedback(FeedbackType.REJECTION, agent_output="a", status=ApprovalStatus.REJECTED)
    fb2 = Feedback(FeedbackType.APPROVAL, agent_output="b", status=ApprovalStatus.APPROVED)
    store.save(fb1)
    store.save(fb2)
    rejected = store.query(status=ApprovalStatus.REJECTED)
    assert len(rejected) == 1
    assert rejected[0].agent_output == "a"


def test_store_query_by_session():
    store = FeedbackStore()
    fb1 = Feedback(FeedbackType.COMMENT, agent_output="x", session_id="s1")
    fb2 = Feedback(FeedbackType.COMMENT, agent_output="y", session_id="s2")
    store.save(fb1)
    store.save(fb2)
    s1 = store.query(session_id="s1")
    assert len(s1) == 1


def test_store_stats():
    store = FeedbackStore()
    store.save(Feedback(FeedbackType.REJECTION, agent_output="a", status=ApprovalStatus.REJECTED))
    store.save(Feedback(FeedbackType.RATING, agent_output="b", status=ApprovalStatus.APPROVED, rating=5.0))
    stats = store.stats()
    assert stats["total"] == 2
    assert stats["avg_rating"] == 5.0


def test_store_delete():
    store = FeedbackStore()
    fb = Feedback(FeedbackType.COMMENT, agent_output="x")
    fid = store.save(fb)
    assert store.delete(fid) is True
    assert store.get(fid) is None


# ── FeedbackCollector ────────────────────────────────────────────────────────

def test_collector_correction():
    col = FeedbackCollector(session_id="test")
    fb = col.correction("wrong", "right", comment="fix it")
    assert fb.corrected_output == "right"
    assert fb.status == ApprovalStatus.REJECTED


def test_collector_rate_high():
    col = FeedbackCollector()
    fb = col.rate("good output", 4.5)
    assert fb.status == ApprovalStatus.APPROVED


def test_collector_rate_low():
    col = FeedbackCollector()
    fb = col.rate("bad output", 1.0)
    assert fb.status == ApprovalStatus.REJECTED


def test_collector_rate_invalid():
    col = FeedbackCollector()
    with pytest.raises(ValueError):
        col.rate("x", 11.0)


def test_collector_reject():
    col = FeedbackCollector()
    fb = col.reject("bad thing", reason="harmful content", tags=["safety"])
    assert fb.status == ApprovalStatus.REJECTED
    assert "safety" in fb.tags


def test_collector_report():
    col = FeedbackCollector(session_id="report-test")
    col.correction("wrong", "right")
    col.rate("ok", 5.0)
    report = col.report()
    assert report["total"] == 2
    assert report["session_id"] == "report-test"


# ── ApprovalGate ─────────────────────────────────────────────────────────────

def test_approval_gate_with_reviewer_approve():
    gate = ApprovalGate()
    gate.set_reviewer(lambda fb: True)
    status = gate.request_approval("some output")
    assert status == ApprovalStatus.APPROVED


def test_approval_gate_with_reviewer_reject():
    gate = ApprovalGate()
    gate.set_reviewer(lambda fb: False)
    status = gate.request_approval("bad output")
    assert status == ApprovalStatus.REJECTED


def test_approval_gate_timeout():
    gate = ApprovalGate(timeout=0.05)
    status = gate.request_approval("waiting output")
    assert status == ApprovalStatus.TIMEOUT


# ── AsyncApprovalGate ────────────────────────────────────────────────────────

def test_async_gate_submit_and_decide():
    gate = AsyncApprovalGate()
    fb = gate.submit("agent said X")
    assert fb.status == ApprovalStatus.PENDING
    result = gate.decide(fb.id, approved=True, comment="looks good")
    assert result is True
    updated = gate._store.get(fb.id)
    assert updated.status == ApprovalStatus.APPROVED


def test_async_gate_pending_list():
    gate = AsyncApprovalGate()
    gate.submit("item 1")
    gate.submit("item 2")
    pending = gate.pending()
    assert len(pending) == 2


# ── RejectionLearner ─────────────────────────────────────────────────────────

def test_learner_top_tags():
    store = FeedbackStore()
    col = FeedbackCollector(store=store)
    col.reject("bad", tags=["hallucination", "accuracy"])
    col.reject("worse", tags=["hallucination"])
    learner = RejectionLearner(store)
    top = learner.top_rejection_tags(n=1)
    assert top[0][0] == "hallucination"
    assert top[0][1] == 2


def test_learner_correction_pairs():
    store = FeedbackStore()
    col = FeedbackCollector(store=store)
    col.correction("wrong answer", "right answer")
    learner = RejectionLearner(store)
    pairs = learner.correction_pairs()
    assert len(pairs) == 1
    assert pairs[0] == ("wrong answer", "right answer")


def test_learner_prompt_addendum():
    store = FeedbackStore()
    col = FeedbackCollector(store=store)
    col.reject("bad", tags=["factuality"])
    col.correction("old", "new")
    learner = RejectionLearner(store)
    addendum = learner.build_system_prompt_addendum()
    assert "Learned from past rejections" in addendum
    assert "factuality" in addendum
