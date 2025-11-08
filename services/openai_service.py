"""
OpenAI helper service.

- Uses the OpenAI Python package.
- Exposes a function to generate a batch of knowledge Q&A items for a given technology.
- The call is intentionally conservative (low temperature, limited tokens) to produce repeatable results.
- Returns a list of dicts: {'prompt': str,

'reference_answer': str, 'keywords': List[str]}.

Note: set OPENAI_API_KEY and OPENAI_MODEL in .env before use.
"""

import os
import json
import time
import logging
from typing import List, Dict, Any, Optional
import requests
from sqlalchemy.orm import Session
from models.question import Question
from models.interview import Interview
from models.question_feedback import QuestionFeedback
from db.session import get_db


import openai
from dotenv import load_dotenv
from openai import OpenAI
import httpx


load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")


if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
else:
    logging.warning(
        "OPENAI_API_KEY is not set. OpenAI calls will fail until you provide an API key."
    )

logger = logging.getLogger(__name__)

try:
    # newer OpenAI python client (supports OpenAI().embeddings.create)
    from openai import OpenAI as _OpenAIClientClass  # type: ignore
    _client = _OpenAIClientClass()
    _client_create_fn = getattr(_client.embeddings, "create", None)
    CLIENT_STYLE = "OpenAI()"
except Exception:
    try:
        import openai as _openai  # type: ignore
        _openai_api_key = os.getenv("OPENAI_API_KEY")
        if _openai_api_key:
            _openai.api_key = _openai_api_key
        _client = _openai
        _client_create_fn = getattr(_client.Embedding, "create", None) or getattr(_client, "Embedding", None) or getattr(_client, "embeddings", None) or getattr(_client, "Embedding")  # best effort
        CLIENT_STYLE = "openai"
    except Exception:
        _client = None
        _client_create_fn = None
        CLIENT_STYLE = None

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")


def get_embedding(text: str):
    """
    Return list[float] embedding for `text` or raise an exception.
    Supports both `OpenAI().embeddings.create` and `openai.Embedding.create`.
    """
    if not _client or not _client_create_fn:
        raise RuntimeError("No OpenAI client available; set OPENAI_API_KEY and install openai package.")
    # Use the two common call shapes
    try:
        # New client style: OpenAI().embeddings.create(input=..., model=...)
        if CLIENT_STYLE == "OpenAI()":
            resp = _client.embeddings.create(input=text, model=EMBEDDING_MODEL)
            # response shape: resp.data[0].embedding
            return resp.data[0].embedding
        else:
            # Classic openai style
            # Some versions: openai.Embedding.create(input=..., model=...)
            create_fn = getattr(_client, "Embedding", None) or getattr(_client, "embeddings", None) or getattr(_client, "Embedding", None)
            if create_fn and hasattr(create_fn, "create"):
                resp = create_fn.create(input=text, model=EMBEDDING_MODEL)
            else:
                # fallback to openai.embeddings.create if present
                resp = _client.embeddings.create(input=text, model=EMBEDDING_MODEL)
            return resp["data"][0]["embedding"]
    except Exception:
        # Re-raise with stack for calling code to handle/log
        raise

def _safe_parse_json(text: str) -> Optional[Any]:
    """
    Try robust JSON extraction from model text. Many prompts instruct model to return JSON,
    but the model may include extraneous text. This helper tries to find a JSON object/array substring.
    """
    text = text.strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except Exception:
        start = None
        end = None
        for i, ch in enumerate(text):
            if ch in "[{":
                start = i
                break
        if start is None:
            return None
        # find the matching closing brace by simple heuristics (last occurrence)
        # prefer ']' if '[' was found, otherwise '}'
        if text[start] == "[":
            end = text.rfind("]")
        else:
            end = text.rfind("}")
        if end == -1:
            return None
        sub = text[start : end + 1]
        try:
            return json.loads(sub)
        except Exception:
            return None


def _build_generation_prompt(job_description: str, n_questions: int = 5) -> str:
    """
    Build the system + user prompt to instruct the model to output JSON array of Q&A items.
    Each item should be:
    {
      "prompt": "Question text",
      "reference_answer": "An ideal/concise reference answer",

      "keywords": ["keyword1","keyword2"]
    }
    """
    sys = (
        "You are an expert technical interviewer and content generator. "
        "Produce high-quality interview questions and reference answers for the specified job description. "
        "Output MUST be valid JSON — an array of objects. Each object must contain keys: "
        "'question' (string), 'answer' (string), 'keywords' (array of short strings). "
        "Do NOT include any other keys or explanatory text outside the JSON array."
    )
    user = (
        f"""
            Generate {n_questions} interview question items for the technology '{job_description}'.

            Ensure that approximately 40% of the total questions are coding-related.
            For example:
            - If 5 questions are generated, at least 2 must be coding questions.
            - If 10 questions are generated, at least 4 must be coding questions.

            The questions should cover different types:
            - Theory / Conceptual
            - Practical / Scenario-based
            - Debugging / Error identification
            - Short coding tasks (for the coding-type questions)

            Each question item must include:
            - "question": the question text
            - "answer": a concise explanation (4–8 short paragraphs)
            - "keywords": 2–6 relevant keywords for automatic matching

            Return only a valid JSON array of question items.
            """
    )
    # We'll combine system+user into messages for chat completion
    return sys, user


def generate_knowledge_for_tech(
    db: Session, job_description: str, job_id: int, n_questions: int = 5, max_retries: int = 2
) -> List[Dict[str, Any]]:
    """
    Generate n_questions knowledge items for the given 'tech' using OpenAI chat completions.
    Returns a list of dicts: {'question','answer','keywords'}.

    Raises RuntimeError if API key not configured or if output cannot be parsed.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Populate .env with your key before generating."
        )

    sys_msg, user_msg = _build_generation_prompt(job_description, n_questions)

    attempt = 0
    while attempt <= max_retries:
        attempt += 1
        try:
            client = OpenAI()
            # (optional) avoid listing models on every call — it can be slow and isn't needed for generation
            # response = client.models.list()  # remove or uncomment for debugging

            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.2,
                max_tokens=2500,
                n=1,
            )

            # ACCESS THE CONTENT CORRECTLY:
            # 'message' is a ChatCompletionMessage object; access .content attribute instead of indexing.
            text = ""
            if hasattr(response, "choices") and len(response.choices) > 0:
                # support both object-style and dict-like access just in case
                choice = response.choices[0]
                if hasattr(choice, "message") and hasattr(choice.message, "content"):
                    text = choice.message.content
                elif isinstance(choice, dict) and "message" in choice:
                    # fallback if the response is a plain dict
                    msg = choice["message"]
                    if isinstance(msg, dict):
                        text = msg.get("content", "")
                    else:
                        # last resort: try attribute
                        text = getattr(msg, "content", "")
                else:
                    # fallback to raw text fields if present
                    text = getattr(choice, "text", "")
            else:
                raise RuntimeError("OpenAI response didn't contain any choices.")

            parsed = _safe_parse_json(text)
            if parsed is None:
                logging.warning("OpenAI response JSON parse failed. Attempting fallback.")

                # Use a clear fallback prompt and actually send it
                fallback_user = (
                    "You previously returned an invalid format. Return ONLY the JSON array, nothing else. "
                    f"Array must contain {n_questions} items with keys prompt, reference_answer, keywords."
                )
                response2 = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": user_msg},
                        {"role": "user", "content": fallback_user},
                    ],
                    temperature=0.0,
                    max_tokens=2500,
                    n=1,
                )

                # extract text from second response similarly
                text2 = ""
                if hasattr(response2, "choices") and len(response2.choices) > 0:
                    c2 = response2.choices[0]
                    if hasattr(c2, "message") and hasattr(c2.message, "content"):
                        text2 = c2.message.content
                    elif isinstance(c2, dict) and "message" in c2:
                        msg = c2["message"]
                        if isinstance(msg, dict):
                            text2 = msg.get("content", "")
                        else:
                            text2 = getattr(msg, "content", "")
                    else:
                        text2 = getattr(c2, "text", "")

                parsed = _safe_parse_json(text2)
                if parsed is None:
                    raise RuntimeError("Failed to parse JSON from OpenAI output.")

            # Validate shape and normalize
            items: List[Dict[str, Any]] = []
            if not isinstance(parsed, list):
                raise RuntimeError("Parsed output is not a JSON list.")
            for it in parsed:
                if not isinstance(it, dict):
                    continue
                prompt = it.get("prompt") or it.get("question") or ""
                ref = it.get("reference_answer") or it.get("answer") or ""
                kws = it.get("keywords") or []

                if isinstance(kws, str):
                    kws = [k.strip() for k in kws.split(",") if k.strip()]

                items.append(
                    {
                        "question": str(prompt).strip(),
                        "answer": str(ref).strip(),
                        "keywords": [str(k).strip() for k in (kws or [])],
                    }
                )
            bad_question_texts_query = (
                db.query(Question.question_text) # Select the text of the bad question
                .join(QuestionFeedback, Question.id == QuestionFeedback.question_id) # Join with feedback
                .join(Interview, Question.interview_id == Interview.id) # Join Question -> Interview
                .filter(QuestionFeedback.is_good == False) # Filter for "bad" feedback
                .filter(Interview.job_id == job_id) # Filter by the correct job_id from the Interview table
            )
            bad_question_texts = {q[0].lower().strip() for q in bad_question_texts_query.all()}

            filtered_items = [
                item for item in items
                if item['question'].lower().strip() not in bad_question_texts
            ]

            return filtered_items

        except Exception as exc:
            logging.exception("OpenAI generation attempt failed: %s", exc)
            if attempt > max_retries:
                raise RuntimeError(
                    f"OpenAI generation failed after {attempt} attempts: {exc}"
                ) from exc
            time.sleep(1 + attempt * 1.5)

    raise RuntimeError("OpenAI generation failed unexpectedly.")

def evaluate_answer_with_llm(question_text: str, model_answer: str, candidate_answer: str) -> Optional[Dict[str, Any]]:
    """
    Calls the OpenAI API to evaluate a candidate's answer against a model answer.

    Returns:
        A dictionary like {"score": 85, "feedback": "Good answer..."} or None on failure.
    """
    
    # 1. Get API Key from environment variables
    API_KEY = os.environ.get("OPENAI_API_KEY")
    if not API_KEY:
        logging.error("OPENAI_API_KEY environment variable not set.")
        return None
        
    API_URL = "https://api.openai.com/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    # 2. Define the prompts
    system_prompt = (
        "You are an expert technical interviewer. "
        "Your task is to evaluate a candidate's answer to a technical question. "
        "You will be given the question, an ideal 'model answer', and the candidate's answer.\n\n"
        "Your evaluation MUST follow these steps:\n"
        "1. First, determine if the candidate's answer is a *relevant attempt* to answer the question.\n"
        "2. **If the answer is irrelevant, blank, nonsensical, or just metadata (like 'I don't know' or 'Interview Question'), you MUST give a score of 0.**\n"
        "3. If the answer *is* a relevant attempt, compare it to the model answer and provide a score from 0 to 100 based on its quality, accuracy, and completeness.\n"
        "4. Provide concise, constructive feedback explaining the score.\n\n"
        "You MUST respond in this specific JSON format:\n"
        '{"score": <number>, "feedback": "<string>"}'
    )
    
    user_prompt = f"""
    **Question:**
    {question_text}

    **Ideal Model Answer (for your reference):**
    {model_answer}

    **Candidate's Answer (to evaluate):**
    {candidate_answer}

    Please provide your evaluation in the specified JSON format.
    """

    # 3. Construct the payload for OpenAI
    payload = {
        "model": OPENAI_MODEL, # Using a modern, fast, and JSON-capable model
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": { "type": "json_object" }, # Ask for JSON mode
        "temperature": 0.2
    }

    # 4. Make the API call using 'requests'
    try:
        response = requests.post(API_URL, headers=headers, data=json.dumps(payload), timeout=30)

        if response.status_code != 200:
            logging.error(f"OpenAI API request failed with status {response.status_code}: {response.text}")
            return None

        result = response.json()
        
        # The response content is a JSON *string*
        json_text = result['choices'][0]['message']['content']
        evaluation = json.loads(json_text)
        
        return evaluation

    except Exception as e:
        logging.error(f"Error during OpenAI LLM evaluation: {e}")
        return None


def get_match_report(resume_text: str, job_description: str) -> Optional[Dict[str, Any]]:
    """
    Analyzes a candidate's resume against a job description.
    Returns a dictionary with 'score', 'summary', 'strengths', and 'gaps'.
    """
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set.")
        return None

    system_prompt = (
        "You are an expert technical recruiter and hiring manager. "
        "Your task is to analyze a candidate's resume against a specific job description. "
        "You MUST return ONLY a valid JSON object with four keys: "
        "'score' (an integer from 0-100 representing the percentage match), "
        "'summary' (a 2-sentence professional summary of the candidate's fit), "
        "'strengths' (a list of 3-5 bullet points of their key qualifications that match the job), and "
        "'gaps' (a list of 2-3 bullet points of key requirements from the job that appear to be missing from the resume)."
    )
    
    user_prompt = f"""
    **Job Description:**
    ---
    {job_description}
    ---

    **Candidate's Resume:**
    ---
    {resume_text}
    ---

    Please provide your analysis as a JSON object: 
    {{"score": <int>, "summary": "<string>", "strengths": ["<string>"], "gaps": ["<string>"]}}
    """

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL, # Use a strong model for this, gpt-4o-mini or gpt-4-turbo
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1, # Be factual and consistent
    }

    try:
        with httpx.Client(timeout=90.0) as client:
            OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
            response = client.post(OPENAI_API_URL, headers=headers, json=payload)
            response.raise_for_status()

            response_data = response.json()
            content = response_data.get("choices", [{}])[0].get("message", {}).get("content")

            if content:
                parsed_json = json.loads(content)
                # Ensure all keys are present
                parsed_json.setdefault('score', 0)
                parsed_json.setdefault('summary', 'No summary provided.')
                parsed_json.setdefault('strengths', [])
                parsed_json.setdefault('gaps', [])
                return parsed_json
            else:
                logger.error("Failed to get match report: No content in API response.")
                return None

    except httpx.HTTPStatusError as http_err:
        logger.error(f"HTTP error getting match report: {http_err} - {http_err.response.text}")
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON from get_match_report response.")
    except Exception as e:
        logger.error(f"Error in get_match_report: {e}", exc_info=True)
    
    return None


def get_answer_from_resume(resume_text: str, user_question: str) -> str:
    """
    Answers a user's question based *only* on the provided resume text.
    (This is the "Ask the Resume" chatbot function).
    """
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set.")
        return "Error: The AI service is not configured."

    system_prompt = (
        "You are a helpful HR assistant. Your only job is to answer questions "
        "about a candidate's resume. You must answer *only* using the information "
        "provided in the 'Resume Text' below. "
        "Do not make assumptions or add any information that is not in the resume. "
        "If the answer is not in the resume, you MUST say 'I cannot find that information in the resume.' "
        "Keep your answers concise."
    )
    user_prompt = f"""
    **Resume Text:**
    ---
    {resume_text}
    ---

    **Manager's Question:**
    {user_question}

    **Answer:**
    """

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0, # Be factual
    }

    try:
        with httpx.Client(timeout=45.0) as client:
            OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
            response = client.post(OPENAI_API_URL, headers=headers, json=payload)
            response.raise_for_status()

            response_data = response.json()
            content = response_data.get("choices", [{}])[0].get("message", {}).get("content")

            return content or "Sorry, I could not generate a response."

    except Exception as e:
        logger.error(f"Error in get_answer_from_resume: {e}", exc_info=True)
        return f"Sorry, an error occurred while processing your request: {e}"
