from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from models.candidate import Candidate
from models.question import Question
from models.candidate_answer import CandidateAnswer
from models.interview import Interview
from models.job import Job  # <-- Added Job model import
from services.openai_service import evaluate_answer_with_llm
import hashlib
import numpy as np
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _next_candidate_code(db: Session) -> str:
    """Generates the next sequential candidate code (e.g., CAND-2025-001)."""
    year = datetime.utcnow().year
    last = db.query(Candidate).order_by(Candidate.id.desc()).first()
    idx = 1
    if last:
        try:
            tail = last.candidate_code.split("-")[-1]
            idx = int(tail) + 1
        except Exception:
            # Fallback if parsing fails
            idx = (last.id or 0) + 1
    return f"CAND-{year}-{str(idx).zfill(3)}"


def create_candidate(
    db: Session,
    name: str,
    tech: str,
    email: str,
    resume: str = "",
    job_code: str = "",
    job_description: str = "",
) -> Candidate:
    """
    Creates a new candidate and also creates their initial Interview record
    linking them to the job.
    """
    
    # --- Find the Job's integer ID ---
    job = db.query(Job).filter(Job.job_code == job_code).first()
    if not job:
        raise ValueError(f"No job found with code {job_code}")

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
        created_at=datetime.utcnow(),  # Use datetime object
        interview_completed=False,
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)  # Refresh to get the new cand.id

    # --- NEW LOGIC: Create the Interview record ---
    new_interview = Interview(
        job_id=job.job_code,  # Use the job's integer PK
        candidate_id=cand.candidate_code,  # Use the new candidate's integer PK
        status="Pending",
        evaluation_status="Not Evaluated",
        created_at=datetime.utcnow()
    )
    db.add(new_interview)
    db.commit()
    # --- END NEW LOGIC ---
    
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
    Updates the candidate's 'interview_completed' flag.
    Updates the 'Interview' record with status and final score.
    """
    saved = []
    similarities = []
    llm_scores = []  # <-- Create a list to hold scores
    
    try:
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
                    semantic_similarity = cosine_similarity(
                        question.model_answer_embedding, emb
                    )
                    similarities.append(semantic_similarity)
                except Exception as exc:
                    logger.exception(
                        "Failed to compute similarity for q=%s: %s", qid, exc
                    )
            
            # 3. Get LLM Score (Synchronous Call)
            llm_score = None
            llm_feedback = None
            
            if question.model_answer and answer_text:
                try:
                    evaluation = evaluate_answer_with_llm(
                        question_text=question.question_text,
                        model_answer=question.model_answer,
                        candidate_answer=answer_text,
                    )
                    if evaluation:
                        llm_score = evaluation.get("score")
                        llm_feedback = evaluation.get("feedback")
                        if llm_score is not None:
                            llm_scores.append(llm_score)  # <-- Add score to list
                            
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
        
        # 5. Mark candidate's interview as completed
        candidate.interview_completed = True
        db.add(candidate)
        
        # --- NEW LOGIC: Update the Interview record ---
        interview_to_update = (
            db.query(Interview)
            .filter(Interview.candidate_id == candidate.candidate_code)
            .first()
        )
        
        if interview_to_update:
            interview_to_update.status = "Completed"
            interview_to_update.evaluation_status = "LLM Evaluvation Completed"
            
            # Calculate and store the final average score
            if llm_scores:
                final_avg_score = sum(llm_scores) / len(llm_scores)
                # Store the 0-100 average score directly
                interview_to_update.final_score = final_avg_score 
                
            db.add(interview_to_update)
        # --- END NEW LOGIC ---

        # 6. Commit all answers, the candidate update, and interview update at once
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
        # try to align by truncation
        min_len = min(va.size, vb.size)
        va = va[:min_len]
        vb = vb[:min_len]
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)

