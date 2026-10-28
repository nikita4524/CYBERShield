"""
Awareness routes — quizzes, scenarios, learning resources, user summary.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user_optional, get_current_user_required, rate_limit_dependency
from services.quiz_service import quiz_service

from schemas.quiz import (
    QuizQuestionResponse,
    QuizQuestionsListResponse,
    StartQuizSessionRequest,
    QuizSessionResponse,
    SubmitQuizAnswersRequest,
    QuizAnswerResult,
    QuizResultResponse,
    ScenarioSummary,
    ScenarioListResponse,
    ScenarioDetailResponse,
    ScenarioStep,
    AwarenessSummaryResponse,
    CategoryScore,
    BadgeInfo,
)
from schemas.common import QuizCategory

router = APIRouter()


# ═══════════════════════════════════════════
# QUIZ QUESTIONS
# ═══════════════════════════════════════════

@router.get(
    "/quizzes",
    response_model=QuizQuestionsListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get quiz questions",
    description="Fetch randomized quiz questions for a category. No auth required.",
)
async def get_quizzes(
    category: QuizCategory = Query(..., description="Quiz category"),
    language: str = Query("en", max_length=5, description="Language code"),
    db: Session = Depends(get_db),
):
    questions = quiz_service.get_questions(db, category.value, language)

    if not questions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No questions found for category '{category.value}' in language '{language}'",
        )

    return QuizQuestionsListResponse(
        category=category,
        language=language,
        total_questions=len(questions),
        questions=[
            QuizQuestionResponse(
                id=str(q.id),
                question_text=q.question_text,
                options=q.options,
                difficulty=q.difficulty,
            )
            for q in questions
        ],
    )


@router.get(
    "/quizzes/categories",
    status_code=status.HTTP_200_OK,
    summary="Get available quiz categories",
    description="Returns categories that have active questions with counts.",
)
async def get_categories(
    language: str = Query("en", max_length=5),
    db: Session = Depends(get_db),
):
    categories = quiz_service.get_available_categories(db, language)
    return {"categories": categories}


# ═══════════════════════════════════════════
# QUIZ SESSIONS (WORKING)
# ═══════════════════════════════════════════

@router.post("/quiz-sessions")
async def create_quiz_session(
    request: Request,
    current_user=Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Create a new quiz session, persist to database, and return questions"""
    try:
        body = await request.json()
        category = body.get('category')
        language = body.get('language', 'en')

        from models.quiz import QuizQuestion, QuizSession
        from datetime import datetime, timezone
        import uuid
        import json
        import random

        # Get questions for category
        questions = db.query(QuizQuestion).filter(
            QuizQuestion.category == category,
            QuizQuestion.language == language,
            QuizQuestion.is_active == True,
        ).all()

        if not questions:
            # Fallback across languages if specific language not seeded
            questions = db.query(QuizQuestion).filter(
                QuizQuestion.category == category,
                QuizQuestion.is_active == True,
            ).all()

        if not questions:
            raise HTTPException(status_code=404, detail=f"No questions found for category '{category}'")

        # Pick up to 10 questions
        selected_questions = list(questions)
        random.shuffle(selected_questions)
        selected_questions = selected_questions[:min(10, len(selected_questions))]

        # PERSIST QUIZ SESSION TO DB
        user_id = current_user.id if current_user else None
        session = QuizSession(
            id=uuid.uuid4(),
            user_id=user_id,
            category=category,
            total_questions=len(selected_questions),
            correct_count=0,
            score_pct=0,
            badge_earned=None,
            started_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        questions_response = []
        for q in selected_questions:
            opts = q.options
            if isinstance(opts, str):
                try:
                    opts = json.loads(opts)
                except Exception:
                    opts = [opts]
            questions_response.append({
                "id": str(q.id),
                "question_text": q.question_text,
                "options": opts if isinstance(opts, list) else list(opts),
                "difficulty": q.difficulty,
            })

        return {
            "session_id": str(session.id),
            "category": category,
            "total_questions": len(questions_response),
            "questions": questions_response,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quiz-sessions/{session_id}/answers")
async def submit_quiz_answers(
    session_id: str,
    request: Request,
    current_user=Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Submit answers, grade them, persist QuizSession and QuizAnswer records to DB, and return results"""
    try:
        body = await request.json()
        answers = body.get('answers', [])
        category = body.get('category', 'unknown')

        from models.quiz import QuizQuestion, QuizSession, QuizAnswer
        from datetime import datetime, timezone
        import json
        import uuid

        # Retrieve or create session
        try:
            sid = uuid.UUID(session_id)
        except Exception:
            sid = uuid.uuid4()

        session = db.query(QuizSession).filter(QuizSession.id == sid).first()
        if not session:
            user_id = current_user.id if current_user else None
            session = QuizSession(
                id=sid,
                user_id=user_id,
                category=category,
                total_questions=len(answers),
                correct_count=0,
                score_pct=0,
                started_at=datetime.now(timezone.utc),
            )
            db.add(session)
            db.flush()
        elif current_user and not session.user_id:
            session.user_id = current_user.id

        correct_count = 0
        results = []

        for answer in answers:
            question_id = answer.get('question_id')
            selected = answer.get('selected_option_index')

            try:
                q_id = uuid.UUID(question_id) if isinstance(question_id, str) else question_id
            except Exception:
                continue

            question = db.query(QuizQuestion).filter(QuizQuestion.id == q_id).first()
            if question:
                is_correct = (selected == question.correct_option_index)
                if is_correct:
                    correct_count += 1

                # Save answer record to DB
                try:
                    existing_ans = db.query(QuizAnswer).filter(
                        QuizAnswer.quiz_session_id == session.id,
                        QuizAnswer.question_id == question.id
                    ).first()
                    if not existing_ans:
                        ans_rec = QuizAnswer(
                            id=uuid.uuid4(),
                            quiz_session_id=session.id,
                            question_id=question.id,
                            selected_option_index=selected if selected is not None else -1,
                            is_correct=is_correct,
                            answered_at=datetime.now(timezone.utc),
                        )
                        db.add(ans_rec)
                except Exception:
                    pass

                # Parse options
                options = question.options
                if isinstance(options, str):
                    try:
                        options = json.loads(options)
                    except Exception:
                        options = [options]

                results.append({
                    "question_id": str(question.id),
                    "question_text": question.question_text,
                    "options": options,
                    "selected_option_index": selected,
                    "correct_option_index": question.correct_option_index,
                    "is_correct": is_correct,
                    "explanation": question.explanation or ("Correct answer!" if is_correct else "Incorrect."),
                })

        total = max(1, len(answers))
        score_pct = int(round((correct_count / total) * 100))

        badge = None
        if score_pct >= 90:
            badge = "gold"
        elif score_pct >= 70:
            badge = "silver"
        elif score_pct >= 50:
            badge = "bronze"

        # UPDATE AND COMMIT SESSION
        session.correct_count = correct_count
        session.score_pct = score_pct
        session.badge_earned = badge
        session.completed_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "session_id": str(session.id),
            "category": session.category,
            "total_questions": len(answers),
            "correct_count": correct_count,
            "score_pct": score_pct,
            "badge_earned": badge,
            "results": results,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════
# SCENARIOS
# ═══════════════════════════════════════════

@router.get(
    "/scenarios",
    response_model=ScenarioListResponse,
    status_code=status.HTTP_200_OK,
    summary="List available scenarios",
    description="Get all active scenario simulations, optionally filtered by category.",
)
async def list_scenarios(
    category: QuizCategory = Query(None, description="Filter by category"),
    language: str = Query("en", max_length=5),
    db: Session = Depends(get_db),
):
    cat_value = category.value if category else None
    scenarios = quiz_service.get_scenarios(db, category=cat_value, language=language)

    return ScenarioListResponse(
        scenarios=[
            ScenarioSummary(
                id=str(s.id),
                title=s.title,
                description=s.description,
                category=s.category,
                scenario_type=s.scenario_type,
                estimated_time_minutes=s.estimated_time_minutes or 5,
            )
            for s in scenarios
        ]
    )


@router.get(
    "/scenarios/{scenario_id}",
    response_model=ScenarioDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get scenario details",
    description="Get full scenario with all interactive steps.",
)
async def get_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
):
    scenario = quiz_service.get_scenario_by_id(db, scenario_id)

    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )

    steps = []
    for i, step_data in enumerate(scenario.steps or []):
        steps.append(ScenarioStep(
            step=i + 1,
            type=step_data.get("type", "message"),
            role=step_data.get("role"),
            message=step_data.get("message"),
            prompt=step_data.get("prompt"),
            options=step_data.get("options"),
            correct_index=step_data.get("correct_index"),
            feedback=step_data.get("feedback"),
        ))

    return ScenarioDetailResponse(
        id=str(scenario.id),
        title=scenario.title,
        description=scenario.description,
        category=scenario.category,
        scenario_type=scenario.scenario_type,
        steps=steps,
        estimated_time_minutes=scenario.estimated_time_minutes or 5,
    )


# ═══════════════════════════════════════════
# AWARENESS SUMMARY
# ═══════════════════════════════════════════

@router.get(
    "/summary",
    response_model=AwarenessSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get awareness summary",
    description="Returns aggregated quiz and scenario stats for the authenticated user.",
)
async def get_awareness_summary(
    current_user=Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    user_id = current_user.id if current_user else None
    summary = quiz_service.get_user_summary(db, user_id=user_id)

    badges = []
    for b in summary.get("badges", []):
        badges.append(BadgeInfo(
            category=b["category"],
            badge=b["badge"],
            earned_at=b.get("earned_at", ""),
        ))

    category_scores = {}
    for cat, scores in summary.get("category_scores", {}).items():
        category_scores[cat] = CategoryScore(
            attempts=scores["attempts"],
            best_score=scores["best_score"],
            average_score=scores["average_score"],
        )

    return AwarenessSummaryResponse(
        user_id=summary["user_id"],
        total_quizzes_completed=summary["total_quizzes_completed"],
        average_score_pct=summary["average_score_pct"],
        badges=badges,
        category_scores=category_scores,
        weakest_category=summary.get("weakest_category"),
        scenarios_completed=summary.get("scenarios_completed", 0),
    )