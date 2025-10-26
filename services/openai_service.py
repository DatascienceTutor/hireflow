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
        "'prompt' (string), 'reference_answer' (string), 'keywords' (array of short strings). "
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
    Returns a list of dicts: {'prompt','reference_answer','keywords'}.

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
            print(client.models.list())
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
            text = ""
            # Get the assistant text
            text = response.choices[0].message["content"]
            parsed = _safe_parse_json(text)
            if parsed is None:
                # If parsing fails, attempt a second-pass: ask the model to return only JSON
                # Not ideal to call again blindly; but we can do a retry loop
                logging.warning(
                    "OpenAI response JSON parse failed. Attempting fallback."
                )

                # Try a second call instructing to only return JSON (shorter response)
                fallback_prompt = (
                    "You previously returned an invalid format. Return ONLY the JSON array, nothing else. "
                    f"Array must contain {n_questions} items with keys prompt, reference_answer, keywords."
                )
                response2 = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.2,
                    max_tokens=2500,
                    n=1,
                )
                text2 = response2.choices[0].message["content"]
                parsed = _safe_parse_json(text2)
                if parsed is None:
                    raise RuntimeError("Failed to parse JSON from OpenAI output.")
            # Validate shape
            items = []
            if not isinstance(parsed, list):
                raise RuntimeError("Parsed output is not a JSON list.")
            for it in parsed:
                if not isinstance(it, dict):
                    continue
                prompt = it.get("prompt") or it.get("question") or ""
                ref = it.get("reference_answer") or it.get("answer") or ""
                kws = it.get("keywords") or []

                if isinstance(kws, str):
                    # attempt to split by commas
                    kws = [k.strip() for k in kws.split(",") if k.strip()]
                # ensure prompt and ref present
                items.append(
                    {
                        "prompt": str(prompt).strip(),
                        "reference_answer": str(ref).strip(),
                        "keywords": [str(k).strip() for k in (kws or [])],
                    }
                )
            # If fewer items than requested, it's okay — return whatever we have
            return items
        except Exception as exc:
            logging.exception("OpenAI generation attempt failed: %s", exc)
            if attempt > max_retries:
                raise RuntimeError(
                    f"OpenAI generation failed after {attempt} attempts: {exc}"
                ) from exc
            time.sleep(1 + attempt * 1.5)
    # fallback
    raise RuntimeError("OpenAI generation failed unexpectedly.")
