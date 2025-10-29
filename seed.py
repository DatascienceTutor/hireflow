import contextlib
import logging
from db.session import get_db, Base, engine
from models.knowledge_question import KnowledgeQuestion
from services.openai_service import generate_knowledge_for_tech # Assuming this is your API call
from dotenv import load_dotenv
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURE YOUR TECHNOLOGIES AND QUESTIONS PER TECH ---
TECHNOLOGIES_TO_SEED = [
    "Python",
    "JavaScript",
    "React.js",
    "Node.js",
    "Java",
    "SQL",
    "Docker",
    "Kubernetes",
    "C# / .NET",
    "TypeScript",
]
QUESTIONS_PER_TECH = 50 # Ask for 50, you might get 45-50


def _build_generation_prompt(job_description: str, n_questions: int = 5) -> tuple[str, str]:
    # --- Make the prompt even more explicit about the ARRAY structure ---
    sys = (
        "You are an expert technical interviewer and content generator. "
        "Your task is to generate a JSON array containing EXACTLY {n_questions} distinct interview question objects " # Specify number again
        "based on the provided technology description. "
        "The final output MUST be ONLY a valid JSON array starting with '[' and ending with ']'. "
        "Each object in the array MUST contain ONLY the keys: 'question' (string), 'answer' (string), and 'keywords' (array of 2-6 short strings). "
        "Do NOT include any introductory text, closing remarks, or any other text outside the main JSON array structure. "
        "Ensure the 'answer' provides a concise explanation suitable for a mid-level developer (4-8 short paragraphs)."
        "Ensure approximately 40% of the questions are coding-related."
    ).format(n_questions=n_questions) # Inject n_questions into system prompt

    user = (
        f"Generate the JSON array with {n_questions} interview question items for the technology: '{job_description}'. "
        f"Remember to include theory, practical, debugging, and coding questions (approx 40% coding). "
        f"Format: [{{'question': '...', 'answer': '...', 'keywords': [...]}}, ...]" # Show example format again
    )
    return sys, user

def seed_database():
    """
    This is the one-time build script.
    It calls the OpenAI API for each technology and saves the
    results to the KnowledgeQuestion (master bank) table.
    """
    
    # Load environment variables (like OPENAI_API_KEY)
    load_dotenv()
    
    logger.info("Starting database seed...")
    
    with contextlib.closing(next(get_db())) as db:
        for tech in TECHNOLOGIES_TO_SEED:
            logger.info(f"--- Seeding technology: {tech} ---")
            
            # Check if questions already exist for this tech
            existing_count = db.query(KnowledgeQuestion).filter(KnowledgeQuestion.tech == tech).count()
            if existing_count > 0:
                logger.warning(f"'{tech}' already has {existing_count} questions. Skipping.")
                continue
                
            # 1. Call the OpenAI API
            try:
                logger.info(f"Calling OpenAI API for {QUESTIONS_PER_TECH} {tech} questions...")
                # This is your existing function. We use a generic JD description.
                jd_prompt = f"Generate a comprehensive list of interview questions for a mid-level developer specializing in {tech}."
                sys_msg, user_msg = _build_generation_prompt(jd_prompt, QUESTIONS_PER_TECH)
                questions_data = generate_knowledge_for_tech(jd_prompt, n_questions=QUESTIONS_PER_TECH)
                
                if not questions_data:
                    logger.error(f"No questions returned from API for {tech}.")
                    continue
                    
            except Exception as e:
                logger.error(f"Failed to generate questions for {tech}: {e}")
                continue

            # 2. Save questions to the master bank
            inserted = 0
            for qa in questions_data:
                if not isinstance(qa, dict):
                    continue
                
                q_text = qa.get("question")
                a_text = qa.get("answer")
                keywords_list = qa.get("keywords", [])

                if not q_text or not a_text:
                    continue

                if not isinstance(keywords_list, list):
                     logger.warning(f"Keywords field was not a list for question '{q_text[:50]}...'. Skipping keywords.")
                     keywords_list = [] # Default to empty list if not a list

                # --- FIX: Convert list to JSON string ---
                keywords_json_string = json.dumps(keywords_list)
                    
                kq = KnowledgeQuestion(
                    tech=tech,
                    question_prompt=q_text,
                    reference_answer=a_text,
                    keywords=keywords_json_string
                )
                db.add(kq)
                inserted += 1
            
            db.commit()
            logger.info(f"Successfully saved {inserted} new questions for {tech}.")

    logger.info("Database seeding complete!")

if __name__ == "__main__":
    seed_database()
