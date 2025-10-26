"""
Knowledge DB persistence helpers.
"""

from sqlalchemy.orm import Session
from typing import List, Dict, Any
import datetime
from models.knowledge_question import KnowledgeQuestion


def _now_iso():
    return datetime.datetime.utcnow().isoformat()


def create_knowledge_question(
    db: Session,
    tech: str,
    prompt: str,
    reference_answer: str = "",
    keywords: List[str] = None,
) -> KnowledgeQuestion:
    kws = ",".join([k.strip() for k in (keywords or []) if k and k.strip()])
    kq = KnowledgeQuestion(
        tech=tech,
        question_prompt=prompt,
        reference_answer=reference_answer,
        keywords=kws,
        created_at=_now_iso(),
    )
    db.add(kq)
    db.commit()
    db.refresh(kq)
    return kq


def bulk_create_knowledge_questions(
    db: Session, tech: str, items: List[Dict[str, Any]]
) -> List[KnowledgeQuestion]:
    """
    items: list of dicts: {'prompt','reference_answer','keywords'(list)}
    Saves them and returns list of created KnowledgeQuestion objects.
    """
    created = []
    for it in items:
        k = create_knowledge_question(
            db,
            tech=tech,
            prompt=it.get("prompt", ""),
            reference_answer=it.get("reference_answer", ""),
            keywords=it.get("keywords") or [],
        )
        created.append(k)
    return created
