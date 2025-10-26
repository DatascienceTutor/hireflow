"""
Evaluation service: runs AI evaluation for a given interview.
Currently uses local scorer (services.ai_service.score_answer_against_references).
This file is the single place to swap in true GPT-based scoring later.
"""

from sqlalchemy.orm import Session
from models.question import Question
from models.answer import Answer
from models.knowledge_question import KnowledgeQuestion
from models.interview import Interview
from services.ai_service import score_answer_against_references
import datetime


def _now_iso():
    return datetime.datetime.utcnow().isoformat()


def evaluate_interview(db: Session, interview_id: int) -> dict:
    """
    For each question linked to the interview, gather candidate answers,
    find matching knowledge references (by source_knowledge_id or by matching prompt),
    compute ai_score for each answer, mark validated flag (score>=threshold),
    update the answers and compute overall interview final_score (1-10).
    Returns summary dict.
    """
    threshold_for_validation = 60.0  # demo threshold, adjust as needed

    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        return {"ok": False, "message": "Interview not found."}

    questions = db.query(Question).filter(Question.interview_id == interview_id).all()
    if not questions:
        return {"ok": False, "message": "No questions for interview."}

    per_question_results = []
    best_scores_for_questions = []

    for q in questions:
        # find references: priority: source_knowledge_id -> fallback find by prompt substring
        refs = []
        if q.source_knowledge_id:
            k = (
                db.query(KnowledgeQuestion)
                .filter(KnowledgeQuestion.id == q.source_knowledge_id)
                .all()
            )
            refs = k
        if not refs:
            # substring match fallback
            refs = (
                db.query(KnowledgeQuestion)
                .filter(KnowledgeQuestion.question_prompt.like(f"%{q.prompt[:60]}%"))
                .all()
            )

        # build list of (ref_text, keywords)
        ref_list = []
        for r in refs:
            kws = (
                [k.strip() for k in (r.keywords or "").split(",") if k.strip()]
                if r.keywords
                else None
            )
            ref_list.append((r.reference_answer or "", kws))

        # get candidate answers for this q
        answers = db.query(Answer).filter(Answer.question_id == q.id).all()
        q_best = 0.0
        ans_results = []
        for a in answers:
            score = score_answer_against_references(a.answer_text or "", ref_list)
            validated = 1 if score >= threshold_for_validation else 0
            a.ai_score = score
            a.validated = validated
            db.add(a)
            db.commit()
            db.refresh(a)
            ans_results.append(
                {
                    "answer_id": a.id,
                    "text": a.answer_text,
                    "score": score,
                    "validated": bool(validated),
                }
            )
            if score > q_best:
                q_best = score

        per_question_results.append(
            {
                "question_id": q.id,
                "prompt": q.prompt,
                "best_score": q_best,
                "answers": ans_results,
            }
        )
        best_scores_for_questions.append(q_best)

    # compute overall raw average (0-100), then normalize to 1-10 scale for final_score
    overall_raw = 0.0
    if best_scores_for_questions:
        overall_raw = sum(best_scores_for_questions) / len(best_scores_for_questions)

    # map 0-100 -> 1-10 (clamp)
    final_score = round(max(1.0, min(10.0, (overall_raw / 10.0))), 2)

    # update interview record
    interview.evaluation_status = "Evaluated"
    interview.final_score = final_score
    db.add(interview)
    db.commit()
    db.refresh(interview)

    return {
        "ok": True,
        "message": "Evaluation completed.",
        "overall_raw_score": overall_raw,
        "final_score": final_score,
        "details": per_question_results,
    }
