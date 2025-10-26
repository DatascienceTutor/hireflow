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

import openai
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")


if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
else:
    logging.warning(
        "OPENAI_API_KEY is not set. OpenAI calls will fail until you provide an API key."
    )


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
        f"Generate {n_questions} interview question items for the technology '{job_description}'. "
        "Make questions varied (theory, practical, debugging, short coding concept). "
        "Reference answers should be concise (1-4 short paragraphs). "
        "Keywords should be 2-6 important keywords for automatic matching. "
        "Return only the JSON array."
    )
    # We'll combine system+user into messages for chat completion
    return sys, user


def generate_knowledge_for_tech(
    job_description: str, n_questions: int = 5, max_retries: int = 2
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

            return items

        except Exception as exc:
            logging.exception("OpenAI generation attempt failed: %s", exc)
            if attempt > max_retries:
                raise RuntimeError(
                    f"OpenAI generation failed after {attempt} attempts: {exc}"
                ) from exc
            time.sleep(1 + attempt * 1.5)

    raise RuntimeError("OpenAI generation failed unexpectedly.")

