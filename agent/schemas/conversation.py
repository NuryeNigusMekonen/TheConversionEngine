from typing import Literal

from pydantic import BaseModel, Field


class ConversationDecision(BaseModel):
    next_action: Literal["send_email", "send_sms", "book_meeting", "handoff_human"]
    channel: Literal["email", "sms", "calendar", "human"]
    reply_draft: str
    needs_human: bool = False
    risk_flags: list[str] = Field(default_factory=list)
    trace_tags: list[str] = Field(default_factory=list)
