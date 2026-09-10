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
    db: Session = Depends(get_db)
):
    """Create a new quiz session and return questions"""
    try:
        body = await request.json()
        category = body.get('category')
        language = body.get('language', 'en')
        
        from models.quiz import QuizQuestion
        import uuid
        
        # Get questions for category
        questions = db.query(QuizQuestion).filter(
            QuizQuestion.category == category,
            QuizQuestion.language == language
        ).all()
        
        if not questions:
            raise HTTPException(status_code=404, detail=f"No questions for {category}")
        
        # Create session ID
        session_id = str(uuid.uuid4())
        
        # Return questions
        questions_response = []
        for q in questions:
            questions_response.append({
                "id": str(q.id),
                "question_text": q.question_text,
                "options": q.options if isinstance(q.options, list) else eval(q.options) if isinstance(q.options, str) else list(q.options),
                "difficulty": q.difficulty
            })
        
        return {
            "session_id": session_id,
            "category": category,
            "total_questions": len(questions),
            "questions": questions_response
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quiz-sessions/{session_id}/answers")
async def submit_quiz_answers(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Submit answers and get results"""
    try:
        body = await request.json()
        answers = body.get('answers', [])
        
        from models.quiz import QuizQuestion
        import json
        import uuid
        correct_count = 0
        results = []

        for answer in answers:
            question_id = answer.get('question_id')
            selected = answer.get('selected_option_index')

            q_id = uuid.UUID(question_id) if isinstance(question_id, str) else question_id
            question = db.query(QuizQuestion).filter(QuizQuestion.id == q_id).first()
            if question:
                is_correct = (selected == question.correct_option_index)
                if is_correct:
                    correct_count += 1
                
                # Parse options if they're stored as JSON string
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
                    "explanation": question.explanation or "The correct answer is the one you selected." if is_correct else "The correct answer is different."
                })
        
        score_pct = int((correct_count / len(answers)) * 100) if answers else 0
        
        # Determine badge
        badge = None
        if score_pct >= 90:
            badge = "Gold"
        elif score_pct >= 70:
            badge = "Silver"
        elif score_pct >= 50:
            badge = "Bronze"
        
        return {
            "session_id": session_id,
            "category": body.get('category', 'unknown'),
            "total_questions": len(answers),
            "correct_count": correct_count,
            "score_pct": score_pct,
            "badge_earned": badge,
            "results": results
        }
        
    except Exception as e:
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
    current_user=Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    summary = quiz_service.get_user_summary(db, user_id=current_user.id)

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