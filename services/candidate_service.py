from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from models.candidate import Candidate
import hashlib
import numpy as np
import logging
from datetime import datetime
from models.candidate import Candidate
from models.question import Question
from models.candidate_answer import CandidateAnswer
from models.interview import Interview
from services.openai_service import evaluate_answer_with_llm 

logger = logging.getLogger(__name__)

def _now_iso():
    return datetime.datetime.utcnow().isoformat()


def _next_candidate_code(db: Session) -> str:
    year = datetime.datetime.utcnow().year
    last = db.query(Candidate).order_by(Candidate.id.desc()).first()
    idx = 1
    if last:
        try:
            tail = last.candidate_code.split("-")[-1]
            idx = int(tail) + 1
        except Exception:
            idx = last.id + 1
    return f"CAND-{year}-{str(idx).zfill(3)}"


def create_candidate(
    db: Session,
    name: str,
    tech=str,
    email=str,
    resume: str = "",
    job_code: str = "",
    job_description: str = "",
) -> Candidate:
    code = _next_candidate_code(db)
    resume_hash = hashlib.sha256(resume.encode()).hexdigest()
    existing_resume_content = (
        db.query(Candidate).filter(Candidate.resume_hash == resume_hash).first()
    )
    if existing_resume_content:
        raise ValueError("A Resume with this content has already been uploaded.")
    cand = Candidate(
        candidate_code=code,
        job_code=job_code,
        email=email,
        name=name,
        resume=resume,
        resume_hash=resume_hash,
        tech=tech,
        job_description=job_description,
        created_at=_now_iso(),
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    return cand


def save_candidate_answers(
    db: Session,
    candidate: Candidate,
    answers: Dict[int, str],
    answer_embeddings: Optional[Dict[int, List[float]]] = None,
) -> Dict[str, Any]:
    """
    Persist CandidateAnswer rows.
    Calls the OpenAI LLM evaluator sequentially inside the loop.
    """
    saved = []
    similarities = []
    
    try:
        # --- We now use a single loop, as the async logic is removed ---
        
        for qid, answer_text in answers.items():
            question: Question = db.query(Question).filter(Question.id == qid).first()
            if not question:
                logger.warning("Question id %s not found, skipping", qid)
                continue

            # 1. Get Answer Embedding
            emb = None
            if answer_embeddings and qid in answer_embeddings:
                emb = answer_embeddings[qid]

            # 2. Calculate Semantic Similarity
            semantic_similarity = None
            if question.model_answer_embedding and emb:
                try:
                    semantic_similarity = cosine_similarity(question.model_answer_embedding, emb)
                    similarities.append(semantic_similarity)
                except Exception as exc:
                    logger.exception("Failed to compute similarity for q=%s: %s", qid, exc)
            
            # 3. Get LLM Score (Synchronous Call)
            llm_score = None
            llm_feedback = None
            
            # Check if we have enough info to call the LLM
            if question.model_answer and answer_text:
                try:
                    # This is the synchronous call to the function in your openai_service.py
                    evaluation = evaluate_answer_with_llm(
                        question_text=question.question_text,
                        model_answer=question.model_answer,
                        candidate_answer=answer_text
                    )
                    if evaluation:
                        llm_score = evaluation.get("score")
                        llm_feedback = evaluation.get("feedback")
                        
                except Exception as e:
                    logger.error(f"Error calling LLM evaluation for QID {qid}: {e}")
            
            # 4. Create the DB Object with all new data
            candidate_answer = CandidateAnswer(
                candidate_id=candidate.candidate_code,
                question_id=question.id,
                answer_text=answer_text,
                answer_embedding=emb,
                semantic_similarity=semantic_similarity,
                llm_score=llm_score,
                feedback=llm_feedback,
                created_at=datetime.utcnow(),
            )
            db.add(candidate_answer)
            saved.append(candidate_answer)
        candidate.interview_completed = True
        db.add(candidate)
        # 5. Commit all answers at once
        db.commit()
        
        return {"saved_count": len(saved), "similarities": similarities}

    except Exception as e:
        db.rollback() 
        logger.exception("Error saving candidate answers: %s", e)
        return {"saved_count": 0, "error": str(e)}

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Compute cosine similarity between two vectors. Accepts lists or numpy arrays.
    """
    va = np.array(a, dtype=np.float64)
    vb = np.array(b, dtype=np.float64)
    if va.size == 0 or vb.size == 0:
        raise ValueError("Empty vectors")
    if va.shape != vb.shape:
        # try to align by truncation or padding with zeros (best-effort)
        min_len = min(va.size, vb.size)
        va = va[:min_len]
        vb = vb[:min_len]
    denom = (np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)