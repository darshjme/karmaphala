# agent-feedback

Human-in-the-loop feedback collection for LLM agents — pure Python, zero dependencies.

**Approval gates · Correction capture · Feedback storage · Learning from rejections**

## Install

```bash
pip install agent-feedback
```

## Quick Start

```python
from agent_feedback import FeedbackCollector, ApprovalGate, RejectionLearner, FeedbackStore

# Collect corrections
collector = FeedbackCollector(session_id="session-001")
collector.correction("The sky is green", "The sky is blue")
collector.rate("Good summary of the document", 4.5)
collector.reject("Hallucinated URL", reason="fabricated", tags=["hallucination"])
report = collector.report()

# Approval gate (with callback reviewer)
gate = ApprovalGate(timeout=30.0)
gate.set_reviewer(lambda fb: "harmful" not in str(fb.agent_output))
status = gate.request_approval("I will help you with that.")
# ApprovalStatus.APPROVED

# Learn from rejections
store = FeedbackStore()
learner = RejectionLearner(store)
addendum = learner.build_system_prompt_addendum()
# "# Learned from past rejections:\nCommon failure areas: hallucination..."
```

## Features

| Module | What it provides |
|--------|-----------------|
| `models` | `Feedback`, `FeedbackType`, `ApprovalStatus` data classes |
| `store` | `FeedbackStore` — thread-safe in-memory + JSON persistence |
| `gates` | `ApprovalGate` (sync + timeout), `AsyncApprovalGate` (non-blocking) |
| `collector` | `FeedbackCollector` — high-level API for corrections, ratings, comments |
| `learner` | `RejectionLearner` — pattern analysis, prompt addendum generation |

## Zero Dependencies

Only the Python standard library (`threading`, `json`, `uuid`, `dataclasses`, `enum`).
