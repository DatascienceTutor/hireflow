from sqlalchemy.orm import Session
from models.knowledge_question import KnowledgeQuestion
from models.question import Question
from models.question_feedback import QuestionFeedback
import datetime
from typing import List, Optional


def _now_iso():
    return datetime.datetime.utcnow().isoformat()


from models.question_feedback import QuestionFeedback

def fetch_knowledge_questions_by_tech(
    db: Session, tech: str, limit: int = 20
) -> List[KnowledgeQuestion]:
    """
    Returns a list of KnowledgeQuestion objects for the technology,
    excluding questions that have received negative feedback.
    """
    # Get all question IDs that have negative feedback
    negatively_feedbacked_question_ids = (
        db.query(QuestionFeedback.question_id)
        .filter(QuestionFeedback.is_good == False)
        .distinct()
        .all()
    )
    # Flatten the list of tuples into a simple list of IDs
    exclude_question_ids = [item[0] for item in negatively_feedbacked_question_ids]

    # Fetch questions, filtering out the ones with negative feedback
    return (
        db.query(KnowledgeQuestion)
        .filter(KnowledgeQuestion.tech == tech)
        .filter(KnowledgeQuestion.id.notin_(exclude_question_ids))
        .limit(limit)
        .all()
    )


def create_question_for_interview(
    db: Session,
    interview_id: int,
    prompt: str,
    source_knowledge_id: Optional[int] = None,
    approved: int = 1,
) -> Question:
    q = Question(
        interview_id=interview_id,
        prompt=prompt,
        source_knowledge_id=source_knowledge_id,
        approved=approved,
        created_at=_now_iso(),
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


def list_questions_for_interview(db: Session, interview_id: int):
    return (
        db.query(Question)
        .filter(Question.interview_id == interview_id)
        .order_by(Question.id.asc())
        .all()
    )


def delete_question(db: Session, question_id: int):
    q = db.query(Question).filter(Question.id == question_id).first()
    if q:
        db.delete(q)
        db.commit()
        return True
    return False


def update_question_prompt(db: Session, question_id: int, new_prompt: str):
    q = db.query(Question).filter(Question.id == question_id).first()
    if q:
        q.prompt = new_prompt
        db.add(q)
        db.commit()
        db.refresh(q)
        return q
    return None
