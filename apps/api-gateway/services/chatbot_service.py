"""
CyberShield AI Chatbot service — India-focused cybersecurity assistant.

Three modes:
  general    → Q&A on scams, safety, best practices
  india_news → Indian cybersecurity context, advisories, threat landscape
  quiz_gen   → Generate quiz questions as structured JSON
"""

from __future__ import annotations

import json
import logging
import random
from typing import AsyncIterator, Optional

from config import settings
from ml.llm_client import ask_chatbot, ask_chatbot_stream, generate_quiz_llm

logger = logging.getLogger(__name__)

DISABLED_MESSAGE = (
    "🔒 **CyberShield Assistant is currently disabled**\n\n"
    "The administrator has turned off AI chat for this deployment. Quick tips:\n\n"
    "1. **Never share OTP** — no bank or UPI app will ever ask for it.\n"
    "2. **Verify UPI payee** name before confirming QR payments.\n"
    "3. **Report fraud** at cybercrime.gov.in or call **1930**.\n"
)

# ─────────────────────────────────────────────────────────────────
# System prompts
# ─────────────────────────────────────────────────────────────────

SYSTEM_GENERAL = """You are **CyberShield Assistant**, an expert cybersecurity advisor built for Indian users.

IDENTITY & SCOPE:
• You are part of CyberShield AI — a platform that detects deepfakes, phishing, QR/UPI fraud.
• You are DEFENSIVE ONLY. You NEVER give exploitation, hacking, or offensive guidance.
• You explain things simply so any non-technical Indian citizen can understand.

INDIA KNOWLEDGE:
• CERT-In advisories, compliance (6-hour incident reporting rule).
• RBI digital-payment guidelines, KYC norms, UPI fraud reporting.
• UPI ecosystem — NPCI, BHIM, Google Pay, PhonePe, Paytm scam patterns.
• National Cyber Crime Portal: cybercrime.gov.in | Helpline: 1930.
• Common Indian scams: fake KYC calls, lottery SMS, OTP phishing, SIM swap, QR tampering, deepfake video calls, fake loan apps, sextortion.
• Cyber Surakshit Bharat, ISEA, Digital Personal Data Protection Act 2023 (DPDPA).
• India has 350M+ UPI users; 175%+ surge in financial-sector phishing in H1 2024.

IOT & SMART HOME SECURITY:
• Smart cameras, plugs, routers, and voice assistants are common attack targets in Indian homes.
• Default passwords, exposed RTSP ports, and fake "ISP/router support" calls are top IoT scam patterns.
• Segment IoT devices on guest Wi-Fi; disable UPnP; update firmware only via official vendor apps.
• Compromised cameras are used for blackmail and fake "CCTV evidence" scams — report at cybercrime.gov.in / 1930.
• CyberShield IoT module monitors device telemetry and flags suspicious DNS, brute-force logins, and unknown devices.

SAFETY RULES — NEVER BREAK:
1. REFUSE any request to hack, exploit, create malware, bypass security, or do anything illegal.
2. If asked about offensive techniques, say: "I only provide defensive guidance. For security research, use authorized bug-bounty programs."
3. Never ask for or store Aadhaar, PAN, passwords, or OTPs.
4. Always recommend cybercrime.gov.in / 1930 for active fraud.

STYLE:
• Markdown with headers, bullets, **bold** for emphasis.
• Relevant emojis sparingly (🔒 🛡️ ⚠️ ✅ ❌).
• Concise but complete (200-400 words).
• Indian examples, laws, institutions when relevant.
• End with an actionable next step."""

SYSTEM_NEWS = """You are **CyberShield News Analyst** for Indian cybersecurity.

Provide a briefing covering:
1. Major cyber incidents affecting India (breaches, scam campaigns, ransomware).
2. CERT-In / government policy updates.
3. RBI / NPCI payment-security developments.
4. Emerging threat trends in the Indian context.
5. Actionable tips.

FORMAT:
• Header: "📰 India Cyber Brief"
• 3-5 news items, each with headline + 2-3 sentence summary.
• End with "🛡️ Stay Safe" section with 2-3 tips.
• Note your knowledge has a cutoff; recommend cert-in.org.in for latest.

RULES: Only factual info from training data. If unsure, say so. Defensive focus only."""

SYSTEM_QUIZ = """You are a cybersecurity quiz generator for Indian users.

RESPOND WITH ONLY VALID JSON — no markdown fences, no explanation text.

Output a JSON array of objects:
[
  {
    "question_text": "...",
    "options": ["A", "B", "C", "D"],
    "correct_option_index": 0,
    "explanation": "...",
    "difficulty": 1,
    "category": "phishing"
  }
]

Rules:
• Every question must be relevant to Indian cybersecurity (UPI, Aadhaar, banking, CERT-In, etc.).
• Exactly 4 options per question.
• One clearly correct answer.
• Educational explanation.
• Valid categories: "deepfake", "phishing", "upi_qr", "kyc_otp", "general", "smart_home".
• Valid difficulty: 1 (easy), 2 (medium), 3 (hard).

IMPORTANT: Output ONLY the JSON array. Nothing else."""

# ─────────────────────────────────────────────────────────────────
# India cyber facts (used offline / as sidebar content)
# ─────────────────────────────────────────────────────────────────

INDIA_FACTS = [
    "🇮🇳 India reported over 14 lakh cyber-security incidents to CERT-In in 2023.",
    "💳 UPI processed 13.4 billion transactions worth ₹20.64 lakh crore in Dec 2023 alone.",
    "📱 India has 350M+ UPI users — the world's largest real-time payment system.",
    "🔒 DPDPA 2023 mandates data protection with penalties up to ₹250 crore.",
    "📞 Call 1930 immediately for financial cyber fraud — India's national helpline.",
    "⚠️ CERT-In requires organisations to report incidents within 6 hours.",
    "🏦 RBI rules: banks must reverse unauthorised e-transactions reported within 3 working days.",
    "🎭 175% surge in phishing attacks on India's financial sector in H1 2024.",
    "📧 Phishing is India's #1 cyber-attack vector; banking & e-commerce are top targets.",
    "🤖 A BSE chief's deepfake video was circulated on social media in India.",
    "💡 Under IT Act Section 66D, impersonation via computer is punishable by up to 3 years.",
    "🌐 India is among the top 3 countries targeted by ransomware globally.",
    "📲 Never install apps from SMS/WhatsApp links — always use official app stores.",
    "🔐 CERT-In recommends enabling 2FA on all critical accounts.",
    "🏢 India's NCIIPC protects critical infrastructure: power, banking, telecom.",
]

IOT_TIPS = [
    "📷 Change default passwords on smart cameras and routers on day one.",
    "📡 Put IoT devices on a separate guest Wi-Fi network from phones and laptops.",
    "🚫 Never install remote-access apps (AnyDesk, TeamViewer) for unsolicited 'support' calls.",
    "🔄 Update smart device firmware only through the official vendor app — not SMS links.",
    "👁️ Review connected devices on your router dashboard weekly.",
    "🔌 Unplug smart devices you are not actively using.",
    "📞 Fake ISP and camera 'support' scams are rising in India — verify via official helpline numbers.",
    "🛡️ CyberShield IoT alerts flag suspicious DNS, brute-force logins, and unknown devices.",
]

IOT_KEYWORDS = (
    "iot", "smart home", "smart camera", "router", "alexa", "google home",
    "smart plug", "wifi camera", "cctv", "connected device", "telemetry",
)

NEWS_KEYWORDS = (
    "news", "latest", "recent", "breaking", "headline",
    "current threat", "trending", "this week", "today's",
)

# ─────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────

def build_iot_context(db, user_id) -> str:
    """Optional snapshot of the user's IoT posture for chat context."""
    try:
        from models.iot import IoTAlert, IoTDevice

        devices = db.query(IoTDevice).filter(IoTDevice.user_id == user_id).all()
        if not devices:
            return ""

        offline = sum(1 for d in devices if d.status == "offline")
        high_alerts = (
            db.query(IoTAlert)
            .filter(
                IoTAlert.user_id == user_id,
                IoTAlert.is_resolved.is_(False),
                IoTAlert.severity == "high",
            )
            .count()
        )
        return (
            f"\nUSER IOT SNAPSHOT: {len(devices)} registered device(s); "
            f"{offline} offline; {high_alerts} open high-severity alert(s)."
        )
    except Exception:
        logger.exception("Failed to build IoT chat context")
        return ""


def _message_mentions_iot(messages: list[dict]) -> bool:
    text = " ".join(m.get("content", "") for m in messages).lower()
    return any(keyword in text for keyword in IOT_KEYWORDS)


def _message_mentions_news(messages: list[dict]) -> bool:
    text = " ".join(m.get("content", "") for m in messages).lower()
    return any(keyword in text for keyword in NEWS_KEYWORDS)


async def build_news_context(limit: int = 5) -> str:
    """Fetch recent India-relevant cyber news headlines to ground the assistant's reply."""
    try:
        from services.news_service import fetch_news

        articles = await fetch_news(limit=limit, india_only=True)
        if not articles:
            return ""

        lines = ["\nRECENT INDIA CYBER NEWS (reference these real, current headlines when relevant):"]
        for a in articles:
            lines.append(f"- {a['title']} — {a['source']}: {a['summary'][:150]}")
        return "\n".join(lines)
    except Exception:
        logger.exception("Failed to build news chat context")
        return ""


async def _resolve_context(messages: list[dict], mode: str, extra_context: str) -> str:
    """Append news context on top of any caller-supplied extra_context (e.g. IoT snapshot)."""
    if mode == "india_news":
        extra_context += await build_news_context(limit=5)
    elif mode == "general" and _message_mentions_news(messages):
        extra_context += await build_news_context(limit=3)
    return extra_context


async def chat_response(
    messages: list[dict],
    mode: str = "general",
    extra_context: str = "",
    db=None,
) -> dict:
    """
    Generate an assistant reply.

    Returns {"reply": str, "facts": list[str]}
    """
    if not settings.CHATBOT_ENABLED:
        facts = random.sample(INDIA_FACTS, min(2, len(INDIA_FACTS)))
        return {"reply": DISABLED_MESSAGE, "facts": facts}

    # ✅ FIX: handle quiz_gen mode by generating quiz and formatting as chat
    if mode == "quiz_gen":
        return await _handle_quiz_mode(messages, db=db)

    system = SYSTEM_GENERAL if mode == "general" else SYSTEM_NEWS
    system = system + await _resolve_context(messages, mode, extra_context)

    reply = await ask_chatbot(
        messages=messages,
        system_prompt=system,
        temperature=0.7,
        max_tokens=4096,
    )

    if _message_mentions_iot(messages):
        facts = random.sample(IOT_TIPS, min(2, len(IOT_TIPS)))
    else:
        facts = random.sample(INDIA_FACTS, min(2, len(INDIA_FACTS)))
    return {"reply": reply, "facts": facts}


async def chat_response_stream(
    messages: list[dict],
    mode: str = "general",
    extra_context: str = "",
    db=None,
) -> AsyncIterator[dict]:
    """
    Stream an assistant reply as it's generated.

    Yields {"type": "delta", "content": str} chunks, then one
    {"type": "facts", "facts": list[str]} chunk at the end.
    """
    if not settings.CHATBOT_ENABLED:
        yield {"type": "delta", "content": DISABLED_MESSAGE}
        yield {"type": "facts", "facts": random.sample(INDIA_FACTS, min(2, len(INDIA_FACTS)))}
        return

    if mode == "quiz_gen":
        result = await _handle_quiz_mode(messages, db=db)
        yield {"type": "delta", "content": result["reply"]}
        yield {"type": "facts", "facts": result["facts"]}
        return

    system = SYSTEM_GENERAL if mode == "general" else SYSTEM_NEWS
    system = system + await _resolve_context(messages, mode, extra_context)

    async for piece in ask_chatbot_stream(
        messages=messages,
        system_prompt=system,
        temperature=0.7,
        max_tokens=4096,
    ):
        yield {"type": "delta", "content": piece}

    if _message_mentions_iot(messages):
        facts = random.sample(IOT_TIPS, min(2, len(IOT_TIPS)))
    else:
        facts = random.sample(INDIA_FACTS, min(2, len(INDIA_FACTS)))
    yield {"type": "facts", "facts": facts}


async def _handle_quiz_mode(messages: list[dict], db=None) -> dict:
    """
    When user is in quiz_gen mode, extract their topic from the last message,
    generate quiz questions, and format them as a readable chat response.
    """
    last_msg = messages[-1]["content"] if messages else "cybersecurity basics"

    questions = await generate_quiz(
        topic=last_msg,
        num_questions=5,
        difficulty=1,
        category="general",
        db=db,
    )

    # Format questions as readable markdown
    lines = [f"## 🧠 Quiz: {last_msg}\n"]
    for i, q in enumerate(questions, 1):
        lines.append(f"### Question {i}")
        lines.append(f"**{q['question_text']}**\n")
        for j, opt in enumerate(q["options"]):
            marker = "🟢" if j == q["correct_option_index"] else "⚪"
            lines.append(f"{marker} **{chr(65 + j)}.** {opt}")
        lines.append(f"\n💡 **Answer:** {chr(65 + q['correct_option_index'])}")
        lines.append(f"📝 {q['explanation']}\n")

    reply = "\n".join(lines)
    facts = random.sample(INDIA_FACTS, min(2, len(INDIA_FACTS)))
    return {"reply": reply, "facts": facts}


async def generate_quiz(
    topic: str,
    num_questions: int = 5,
    difficulty: int = 1,
    category: str = "general",
    db=None,
) -> list[dict]:
    """
    Generate quiz questions via AI.

    Returns list of question dicts or fallback questions on failure.
    When `db` is provided, successfully AI-generated questions are persisted
    to the quiz bank (via quiz_service) so they can be replayed later and
    show up in the Awareness module. Fallback (canned) questions are never
    persisted since they already live in the seed data.
    """
    if not settings.CHATBOT_ENABLED:
        return _fallback_quiz(num_questions, difficulty, category)

    user_prompt = (
        f"Generate exactly {num_questions} cybersecurity quiz questions.\n"
        f"Topic: {topic}\n"
        f"Difficulty: {difficulty} (1=easy, 2=medium, 3=hard)\n"
        f"Category: {category}\n"
        f"All questions MUST be relevant to Indian users and context."
    )

    raw = await generate_quiz_llm(
        user_prompt=user_prompt,
        system_prompt=SYSTEM_QUIZ,
        temperature=0.8,
        max_tokens=4096,
    )

    if not raw:
        return _fallback_quiz(num_questions, difficulty, category)

    # Parse JSON
    try:
        cleaned = raw.strip()
        # strip markdown code fences if present
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        questions = json.loads(cleaned)

        validated = []
        for q in questions:
            validated.append({
                "question_text": str(q.get("question_text", "")),
                "options": list(q.get("options", []))[:4],
                "correct_option_index": int(q.get("correct_option_index", 0)) % 4,
                "explanation": str(q.get("explanation", "")),
                "difficulty": min(max(int(q.get("difficulty", difficulty)), 1), 3),
                "category": q.get("category", category),
            })

        if not validated:
            return _fallback_quiz(num_questions, difficulty, category)

        result = validated[:num_questions]
        if db is not None:
            try:
                from services.quiz_service import quiz_service

                quiz_service.save_ai_generated_questions(db, result)
            except Exception:
                logger.exception("Failed to persist AI-generated quiz questions")
        return result

    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Quiz JSON parse failed: %s — raw: %s", exc, raw[:200])
        return _fallback_quiz(num_questions, difficulty, category)


async def get_daily_tip() -> dict:
    """Random India-specific cybersecurity tip."""
    return {"tip": random.choice(INDIA_FACTS), "source": "CyberShield AI"}


# ─────────────────────────────────────────────────────────────────
# Fallback quiz (when LLM fails)
# ─────────────────────────────────────────────────────────────────

def _fallback_quiz(count: int, difficulty: int, category: str) -> list[dict]:
    bank = [
        {
            "question_text": "You get an SMS: 'Your SBI account is blocked. Click http://sbi-verify.xyz to reactivate.' What should you do?",
            "options": [
                "Click the link and enter your details",
                "Ignore — SBI's real domain is sbi.co.in, not sbi-verify.xyz",
                "Forward it to friends as a warning",
                "Reply STOP to the SMS",
            ],
            "correct_option_index": 1,
            "explanation": "sbi-verify.xyz is NOT an official SBI domain. Banks never send blocking messages with links. Visit sbi.co.in directly.",
            "difficulty": difficulty,
            "category": category,
        },
        {
            "question_text": "Someone calls from 'your bank' and asks for your OTP to 'verify your account'. What's correct?",
            "options": [
                "Share the OTP — they said they're from the bank",
                "Ask them to call back later",
                "Hang up — banks NEVER ask for OTPs over phone",
                "Share only the first 3 digits",
            ],
            "correct_option_index": 2,
            "explanation": "No bank employee will ever ask for your OTP, PIN, or password. Report such calls to 1930.",
            "difficulty": difficulty,
            "category": category,
        },
        {
            "question_text": "What is India's national helpline for reporting cyber fraud?",
            "options": ["100", "112", "1930", "181"],
            "correct_option_index": 2,
            "explanation": "1930 is India's Cyber Crime Helpline. Also report at cybercrime.gov.in. Fast reporting increases recovery chances.",
            "difficulty": difficulty,
            "category": category,
        },
        {
            "question_text": "A QR code at a tea stall shows payee name 'Random Person' instead of the shop name. You should:",
            "options": [
                "Pay anyway, you're at the shop",
                "Refuse this QR and ask for alternative payment",
                "Pay ₹1 to test",
                "Scan with another phone first",
            ],
            "correct_option_index": 1,
            "explanation": "Mismatched payee names = potential QR fraud. Scammers paste their own QR over legitimate ones.",
            "difficulty": difficulty,
            "category": category,
        },
        {
            "question_text": "How quickly must Indian organisations report cyber incidents to CERT-In?",
            "options": ["24 hours", "12 hours", "6 hours", "48 hours"],
            "correct_option_index": 2,
            "explanation": "CERT-In mandates reporting within 6 hours of detection (April 2022 directive).",
            "difficulty": difficulty,
            "category": category,
        },
        {
            "question_text": "What is the maximum penalty under India's DPDPA 2023 for data protection violations?",
            "options": ["₹50 crore", "₹100 crore", "₹250 crore", "₹500 crore"],
            "correct_option_index": 2,
            "explanation": "The Digital Personal Data Protection Act 2023 prescribes penalties up to ₹250 crore for significant data breaches.",
            "difficulty": difficulty,
            "category": category,
        },
    ]
    return bank[:count]


async def explain_threat_context(
    threat_context: dict,
    user_query: Optional[str] = None,
) -> dict:
    """
    Generate an AI explanation and actionable guidance for a detected threat.
    Does NOT override the backend prevention decision.
    """
    threat_type = threat_context.get("threat_type", "unknown threat")
    risk_score = threat_context.get("risk_score", 0)
    action = threat_context.get("action", "WARN")
    severity = threat_context.get("severity", "MEDIUM")
    reasons = threat_context.get("reasons", [])
    input_reference = threat_context.get("input_reference", "")

    # Default fallback structured response
    recs = [
        "Do not click on links, download attachments, or scan this code further.",
        "Verify the sender/caller through official, independent contact channels.",
        "If you already provided OTP/passwords, change them immediately and freeze accounts.",
    ]
    avoids = [
        "Do NOT reply to suspicious emails or forward links to others.",
        "Do NOT share OTP, CVV, UPI PIN, or bank passwords with anyone.",
        "Do NOT trust caller ID or voice alone for financial requests.",
    ]
    channels = [
        "National Cyber Crime Reporting Portal: cybercrime.gov.in",
        "National Cyber Crime Helpline: 1930 (Available 24x7 across India)",
        "RBI Banking Ombudsman & NPCI UPI Dispute Support",
    ]

    prompt = f"""You are the CyberShield AI Security Assistant.
Explain why the following threat was flagged and give defensive advice to an Indian user:

THREAT CONTEXT:
- Threat Type: {threat_type}
- Risk Score: {risk_score}/100
- Prevention Action: {action}
- Severity Level: {severity}
- Detected Reasons: {', '.join(reasons) if reasons else 'Heuristic indicators'}
- Reference: {input_reference or 'N/A'}

USER QUESTION: {user_query or 'Why was this blocked and what should I do?'}

Please provide:
1. Clear explanation of why this was identified as {severity} risk / {action}.
2. Immediate steps the user should take right now.
3. Things the user must NEVER do.
4. How to verify if this was claimed to be from a legitimate bank/institution.
5. Exact steps to take if the user ALREADY shared OTP, PIN, or payment.

Keep your response structured, concise, and focused on defensive cybersecurity guidance with references to 1930 and cybercrime.gov.in."""

    explanation_text = ""
    try:
        if settings.CHATBOT_ENABLED and settings.GROQ_API_KEY:
            messages = [{"role": "user", "content": prompt}]
            explanation_text = await ask_chatbot(messages, SYSTEM_GENERAL)
    except Exception as exc:
        logger.warning("LLM threat explanation failed: %s", exc)

    if not explanation_text:
        explanation_text = (
            f"### 🛡️ Threat Analysis ({severity} — Action: {action})\n\n"
            f"This content was evaluated with a **Risk Score of {risk_score}/100** by CyberShield's multi-modal engine.\n\n"
            f"**Key Findings:**\n"
            + "".join(f"- {r}\n" for r in (reasons or ["Elevated threat indicators detected"]))
            + f"\n**Action Taken:** `{action}` — {action} policy applied deterministically by the Prevention Engine.\n\n"
            f"**Next Steps:**\n"
            f"1. **Never share credentials**: No bank or UPI app asks for OTP or PIN.\n"
            f"2. **Verify independently**: Contact the official institution directly.\n"
            f"3. **Report fraud**: Call **1930** or visit **cybercrime.gov.in** immediately."
        )

    return {
        "explanation": explanation_text,
        "action": action,
        "severity": severity,
        "risk_score": risk_score,
        "recommended_steps": recs,
        "things_to_avoid": avoids,
        "reporting_channels": channels,
    }