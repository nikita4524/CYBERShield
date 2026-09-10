"""
CyberShield AI — FastAPI Application Entry Point
"""

import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Suppress noisy ML logs
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

from fastapi import FastAPI, Request, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import engine, Base, get_db
from utils.exceptions import setup_exception_handlers
from dependencies import rate_limit_dependency

# Import routers (will be created in subsequent steps)
from routes import auth, analyze, awareness, reports, admin, demo, chatbot, iot, incidents


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # ─── STARTUP ───
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Create any new tables (SQLite dev / first run)
    from database import create_all_tables
    create_all_tables()

    # MQTT telemetry subscriber (simulation)
    from services.mqtt_service import mqtt_service
    mqtt_service.start()
    
    # Pre-load ML models (lazy loading available in model_loader)
    # We don't load here to keep startup fast; models load on first request
    print("✅ Application startup complete")
    
    yield
    
    # ─── SHUTDOWN ───
    from services.mqtt_service import mqtt_service
    mqtt_service.stop()
    print("👋 Application shutting down")


def create_application() -> FastAPI:
    """Application factory pattern."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="India-first multi-modal AI platform for cyber threat detection and awareness",
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.DEBUG else None,  # Disable docs in production
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )
    
    # ─── Middleware ───
    # NOTE: add_middleware() builds a stack in LIFO order (last-added = outermost).
    # @app.middleware decorators are appended AFTER that stack resolves, making them
    # innermost. To guarantee CORS runs on EVERY response (including error responses)
    # we register middlewares in this explicit order:
    #   1. Request-metadata (innermost — runs last)
    #   2. TrustedHost
    #   3. CORS (outermost — runs first; always injects Access-Control headers)

    # 1. Request ID + timing  (innermost)
    from starlette.middleware.base import BaseHTTPMiddleware

    async def _add_request_metadata(request: Request, call_next):
        request.state.request_id = os.urandom(8).hex()
        request.state.start_time = datetime.now(timezone.utc)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-API-Version"] = settings.APP_VERSION
        return response

    app.add_middleware(BaseHTTPMiddleware, dispatch=_add_request_metadata)

    # 2. Trusted Host
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"] if settings.DEBUG else ["localhost", "*.cybershield.ai", "testserver", "cybershield-api-t6z7.onrender.com"]
    )

    # 3. CORS  (outermost — added last so it wraps everything and always runs first)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # ─── Exception Handlers ───
    setup_exception_handlers(app)
    
    # ─── Routes ───
    
    # Health check (public, no rate limit)
    @app.get("/health", tags=["Health"])
    async def health_check():
        """
        Health check endpoint for load balancers and monitoring.
        Returns 200 OK if service is running.
        """
        return {
            "status": "healthy",
            "version": settings.APP_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": "development" if settings.DEBUG else "production"
        }
    
    # API Routers
    # Note: rate_limit_dependency applied individually to routes that need it
    app.include_router(
        auth.router,
        prefix="/api/v1/auth",
        tags=["Authentication"]
    )
    app.include_router(
        analyze.router,
        prefix="/api/v1/analyze",
        tags=["Analysis"]
    )
    app.include_router(
        awareness.router,
        prefix="/api/v1/awareness",
        tags=["Awareness"]
    )
    app.include_router(
        reports.router,
        prefix="/api/v1/reports",
        tags=["Reports"]
    )
    app.include_router(
        admin.router,
        prefix="/api/v1/admin",
        tags=["Admin"]
    )
    app.include_router(
        demo.router,
        prefix="/api/v1/demo",
        tags=["Demo"]
    )

    app.include_router(
        chatbot.router,
        prefix="/api/v1/assistant",
        tags=["Assistant"],
    )
    app.include_router(
        iot.router,
        prefix="/api/v1/iot",
        tags=["IoT"],
    )
    app.include_router(
        incidents.router,
        prefix="/api/v1/incidents",
        tags=["Incidents"],
    )
    
    # ─── Temporary Quiz Routes (Fix for 404) ───
    
    class QuizSessionRequest(BaseModel):
        category: str
        language: str = "en"
    
    @app.post("/api/v1/awareness/quiz-sessions")
    async def create_quiz_session_fix(request: QuizSessionRequest, db: Session = Depends(get_db)):
        try:
            from models.quiz import QuizQuestion
            import uuid
            
            questions = db.query(QuizQuestion).filter(
                QuizQuestion.category == request.category,
                QuizQuestion.language == request.language
            ).all()
            
            if not questions:
                return {
                    "session_id": "fix_123", 
                    "category": request.category, 
                    "total_questions": 0, 
                    "questions": []
                }
            
            session_id = str(uuid.uuid4())
            questions_response = []
            for q in questions[:10]:
                # Handle options if stored as JSON string
                options = q.options
                if isinstance(options, str):
                    import json
                    try:
                        options = json.loads(options)
                    except:
                        options = [options]
                
                questions_response.append({
                    "id": str(q.id),
                    "question_text": q.question_text,
                    "options": options,
                    "difficulty": q.difficulty
                })
            
            return {
                "session_id": session_id,
                "category": request.category,
                "total_questions": len(questions_response),
                "questions": questions_response
            }
        except Exception as e:
            return {"error": str(e), "session_id": "error"}
    
    @app.post("/api/v1/awareness/quiz-sessions/{session_id}/answers")
    async def submit_quiz_answers_fix(
        session_id: str, 
        request: Request, 
        db: Session = Depends(get_db)
    ):
        try:
            body = await request.json()
            answers = body.get('answers', [])
            category = body.get('category', 'unknown')
            
            from models.quiz import QuizQuestion
            import json
            
            correct_count = 0
            results = []
            
            for answer in answers:
                question_id = answer.get('question_id')
                selected = answer.get('selected_option_index')
                
                question = db.query(QuizQuestion).filter(QuizQuestion.id == question_id).first()
                if question:
                    is_correct = (selected == question.correct_option_index)
                    if is_correct:
                        correct_count += 1
                    
                    # Parse options
                    options = question.options
                    if isinstance(options, str):
                        try:
                            options = json.loads(options)
                        except:
                            options = [options]
                    
                    results.append({
                        "question_id": str(question.id),
                        "question_text": question.question_text,
                        "options": options,
                        "selected_option_index": selected,
                        "correct_option_index": question.correct_option_index,
                        "is_correct": is_correct,
                        "explanation": question.explanation or "Correct answer!" if is_correct else "Incorrect. The correct answer is different."
                    })
            
            score_pct = int((correct_count / len(answers)) * 100) if answers else 0
            badge = None
            if score_pct >= 90:
                badge = "Gold"
            elif score_pct >= 70:
                badge = "Silver"
            elif score_pct >= 50:
                badge = "Bronze"
            
            return {
                "session_id": session_id,
                "category": category,
                "total_questions": len(answers),
                "correct_count": correct_count,
                "score_pct": score_pct,
                "badge_earned": badge,
                "results": results
            }
        except Exception as e:
            return {"error": str(e)}
    
    # Root redirect to docs
    @app.get("/", include_in_schema=False)
    async def root():
        return {"message": "CyberShield AI API", "docs": "/docs"}
    
    return app


# Create the application instance
app = create_application()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )