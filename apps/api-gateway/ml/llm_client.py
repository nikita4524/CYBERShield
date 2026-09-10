"""
Groq LLM client for CyberShield AI.

Uses the Groq OpenAI-compatible REST API directly via httpx.
No SDK dependency needed.

Free tier (as of 2025):
  llama-3.3-70b-versatile  → 30 RPM, 6K RPD, 128K ctx, 32K output
  llama-3.1-8b-instant     → 30 RPM, 14.4K RPD, 128K ctx, 8K output

We use the 70B for chat (quality) and 8B for quiz gen (speed + higher quota).
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


async def _call_groq(
    messages: list[dict],
    system_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    api_key: Optional[str] = None,
) -> str:
    """
    Call Groq chat completions API.

    Args:
        messages:      [{role, content}, ...] conversation history
        system_prompt: system-level instruction
        model:         override model name
        temperature:   sampling temperature
        max_tokens:    max output tokens
        api_key:       override API key (for separate quota)
    """
    key = api_key or settings.GROQ_API_KEY
    if not key:
        return _offline_fallback()

    used_model = model or settings.GROQ_CHAT_MODEL

    all_msgs = [{"role": "system", "content": system_prompt}] + messages

    body = {
        "model": used_model,
        "messages": all_msgs,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(GROQ_CHAT_URL, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"]


async def _call_groq_stream(
    messages: list[dict],
    system_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    api_key: Optional[str] = None,
) -> AsyncIterator[str]:
    """Call Groq chat completions API with streaming enabled, yielding text deltas."""
    key = api_key or settings.GROQ_API_KEY
    if not key:
        yield _offline_fallback()
        return

    used_model = model or settings.GROQ_CHAT_MODEL
    all_msgs = [{"role": "system", "content": system_prompt}] + messages

    body = {
        "model": used_model,
        "messages": all_msgs,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", GROQ_CHAT_URL, json=body, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = line[len("data: "):].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta


# ── Public functions ─────────────────────────────────────────────


async def ask_chatbot(
    messages: list[dict],
    system_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """
    Send chat to the 70B model (best quality).
    Falls back gracefully on error.
    """
    try:
        return await _call_groq(
            messages=messages,
            system_prompt=system_prompt,
            model=settings.GROQ_CHAT_MODEL,       # 70B
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.GROQ_API_KEY,
        )
    except httpx.HTTPStatusError as exc:
        logger.error("Groq chat API error: %s — %s", exc.response.status_code, exc.response.text)
        if exc.response.status_code == 429:
            return (
                "⚠️ I've hit my rate limit. Please wait a minute and try again.\n\n"
                "In the meantime: report cyber fraud at **cybercrime.gov.in** or call **1930**."
            )
        return _offline_fallback()
    except Exception as exc:
        logger.exception("Groq chat call failed: %s", exc)
        return _offline_fallback()


async def ask_chatbot_stream(
    messages: list[dict],
    system_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> AsyncIterator[str]:
    """
    Stream chat from the 70B model, yielding text deltas as they arrive.
    Falls back gracefully (single-chunk) on error.
    """
    try:
        async for delta in _call_groq_stream(
            messages=messages,
            system_prompt=system_prompt,
            model=settings.GROQ_CHAT_MODEL,       # 70B
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.GROQ_API_KEY,
        ):
            yield delta
    except httpx.HTTPStatusError as exc:
        logger.error("Groq chat stream API error: %s — %s", exc.response.status_code, exc.response.text)
        if exc.response.status_code == 429:
            yield (
                "⚠️ I've hit my rate limit. Please wait a minute and try again.\n\n"
                "In the meantime: report cyber fraud at **cybercrime.gov.in** or call **1930**."
            )
        else:
            yield _offline_fallback()
    except Exception as exc:
        logger.exception("Groq chat stream call failed: %s", exc)
        yield _offline_fallback()


async def generate_quiz_llm(
    user_prompt: str,
    system_prompt: str,
    temperature: float = 0.8,
    max_tokens: int = 4096,
) -> str:
    """
    Send quiz-generation request to the 8B model (fast, higher daily quota).
    Uses a separate API key if configured, otherwise shares the main key.
    """
    try:
        return await _call_groq(
            messages=[{"role": "user", "content": user_prompt}],
            system_prompt=system_prompt,
            model=settings.GROQ_QUIZ_MODEL,        # 8B
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.GROQ_QUIZ_API_KEY or settings.GROQ_API_KEY,
        )
    except httpx.HTTPStatusError as exc:
        logger.error("Groq quiz API error: %s — %s", exc.response.status_code, exc.response.text)
        return ""
    except Exception as exc:
        logger.exception("Groq quiz call failed: %s", exc)
        return ""


def _offline_fallback() -> str:
    """Useful response when Groq is unreachable or not configured."""
    return (
        "🔒 **CyberShield Assistant (Offline)**\n\n"
        "I'm running without an AI backend right now. Quick tips:\n\n"
        "1. **Never share OTP** — no bank or UPI app will ever ask for it.\n"
        "2. **Verify UPI payee** name before confirming QR payments.\n"
        "3. **Report fraud** at cybercrime.gov.in or call **1930**.\n"
        "4. **Check domains** — `sbi.co.in` is real; `sbi-alerts.xyz` is fake.\n"
        "5. **Enable 2FA** on all banking and email accounts.\n\n"
        "Add `GROQ_API_KEY` to your `.env` to enable the full assistant (free at console.groq.com)."
    )