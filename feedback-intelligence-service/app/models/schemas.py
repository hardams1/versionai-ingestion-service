from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class CaptureRequest(BaseModel):
    target_user_id: str = Field(..., min_length=1)
    asker_user_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = None


class CaptureResponse(BaseModel):
    id: str
    category: Optional[str] = None
    confidence: Optional[float] = None
    status: str


class FaqCategoryItem(BaseModel):
    category: str
    question_count: int
    sample_questions: List[str] = Field(default_factory=list)


class FaqListResponse(BaseModel):
    items: List[FaqCategoryItem]
    total: int


class FaqActionRequest(BaseModel):
    category: str = Field(..., min_length=1)
    action: Literal["answer", "skip"]
    answer_text: Optional[str] = None


class FaqActionResponse(BaseModel):
    category: str
    action: str
    status: str


class AnsweredFaqItem(BaseModel):
    category: str
    answer_text: str


class AnsweredFaqListResponse(BaseModel):
    items: List[AnsweredFaqItem]
    total: int
