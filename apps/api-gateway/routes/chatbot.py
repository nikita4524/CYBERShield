"""
CyberShield AI Assistant — FastAPI routes.

POST /assistant/chat             → Conversational cybersecurity Q&A
POST /assistant/generate-quiz    → AI-generated quiz questions
GET  /assistant/news             → India cyber news feed
GET  /assistant/tip              → Random daily tip
GET  /assistant/resources        → Curated India cyber resources
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from dependencies import get_current_user_optional
from database import get_db
from schemas.chat import (
    ChatRequest, ChatResponse,
    QuizGenRequest, QuizGenResponse, QuizGenQuestion,
    DailyTipResponse, NewsResponse, NewsItem,
    ThreatExplanationRequest, ThreatExplanationResponse,
)
from services.chatbot_service import (
    chat_response, chat_response_stream, generate_quiz, get_daily_tip, build_iot_context,
    explain_threat_context,
)
from services.news_service import fetch_news, get_india_resources

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Prompt-injection blocklist ───────────────────────────────────

_INJECTION_PHRASES = [
    "ignore previous instructions", "ignore all instructions",
    "you are now", "act as a hacker", "forget your rules",
    "system prompt", "reveal your prompt", "disregard",
    "pretend you are", "jailbreak",
]


@router.post("/chat", response_model=ChatResponse)
async def assistant_chat(
    request: ChatRequest,
    current_user=Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Chat with the cybersecurity assistant. Supports general, india_news, and quiz_gen modes."""
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Block prompt injection (skip for quiz_gen since topics can look unusual)
    if request.mode != "quiz_gen":
        last = messages[-1]["content"].lower()
        if any(p in last for p in _INJECTION_PHRASES):
            return ChatResponse(
                reply=(
                    "⚠️ I detected a potential prompt-injection attempt. "
                    "I only provide **defensive** cybersecurity guidance. "
                    "Please rephrase your question."
                ),
                facts=[],
                mode=request.mode,
            )

    extra_context = ""
    if current_user and request.mode == "general":
        extra_context = build_iot_context(db, current_user.id)

    result = await chat_response(
        messages=messages,
        mode=request.mode,
        extra_context=extra_context,
        db=db,
    )

    return ChatResponse(
        reply=result["reply"],
        facts=result["facts"],
        mode=request.mode,
    )


@router.post("/chat/stream")
async def assistant_chat_stream(
    request: ChatRequest,
    current_user=Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Same as /chat but streams the reply token-by-token as Server-Sent Events.

    Each event is `data: <json>\\n\\n` where json is one of:
      {"type": "delta", "content": "..."}   — incremental text
      {"type": "facts", "facts": [...]}     — sidebar facts, sent once at the end
      {"type": "done"}                      — stream finished
      {"type": "error", "message": "..."}   — something went wrong
    """
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    if request.mode != "quiz_gen":
        last = messages[-1]["content"].lower()
        if any(p in last for p in _INJECTION_PHRASES):
            async def _blocked():
                payload = {
                    "type": "delta",
                    "content": (
                        "⚠️ I detected a potential prompt-injection attempt. "
                        "I only provide **defensive** cybersecurity guidance. "
                        "Please rephrase your question."
                    ),
                }
                yield f"data: {json.dumps(payload)}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

            return StreamingResponse(_blocked(), media_type="text/event-stream")

    extra_context = ""
    if current_user and request.mode == "general":
        extra_context = build_iot_context(db, current_user.id)

    async def event_gen():
        try:
            async for chunk in chat_response_stream(
                messages=messages,
                mode=request.mode,
                extra_context=extra_context,
                db=db,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            logger.exception("Chat stream failed: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/generate-quiz", response_model=QuizGenResponse)
async def assistant_generate_quiz(
    request: QuizGenRequest,
    current_user=Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Generate cybersecurity quiz questions with AI. Successfully generated
    questions are persisted to the quiz bank so they can be replayed later."""
    raw = await generate_quiz(
        topic=request.topic,
        num_questions=request.num_questions,
        difficulty=request.difficulty,
        category=request.category,
        db=db,
    )
    questions = [QuizGenQuestion(**q) for q in raw]
    return QuizGenResponse(topic=request.topic, questions=questions)


@router.get("/news", response_model=NewsResponse)
async def assistant_news(limit: int = 10, india_only: bool = True):
    """Fetch latest cybersecurity news."""
    raw = await fetch_news(limit=limit, india_only=india_only)
    articles = [NewsItem(**a) for a in raw]
    return NewsResponse(articles=articles, resources=get_india_resources())


@router.get("/tip", response_model=DailyTipResponse)
async def assistant_tip():
    """Random India cybersecurity tip."""
    return DailyTipResponse(**(await get_daily_tip()))


@router.get("/resources")
async def assistant_resources():
    """Curated India cyber resources."""
    return {"resources": get_india_resources()}


@router.post("/analyze-context", response_model=ThreatExplanationResponse)
async def assistant_analyze_context(
    request: ThreatExplanationRequest,
    current_user=Depends(get_current_user_optional),
):
    """
    Explain why a specific threat was flagged/blocked and provide defensive advice.
    Receives security-analysis context deterministically from the Prevention Engine.
    """
    result = await explain_threat_context(
        threat_context=request.threat_context.model_dump() if hasattr(request.threat_context, 'model_dump') else request.threat_context.dict(),
        user_query=request.user_query,
    )
    return ThreatExplanationResponse(**result)