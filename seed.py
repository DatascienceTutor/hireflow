import contextlib
import logging
from db.session import get_db, Base, engine
from models.knowledge_question import KnowledgeQuestion
from services.openai_service import generate_knowledge_for_tech # Assuming this is your API call
from dotenv import load_dotenv

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

def seed_database():
    """
    This is the one-time build script.
    It calls the OpenAI API for each technology and saves the
    results to the KnowledgeQuestion (master bank) table.
    """
    
    # Load environment variables (like OPENAI_API_KEY)
    load_dotenv()
    
    # Create the table if it doesn't exist
    Base.metadata.create_all(bind=engine)
    
    logger.info("Starting database seed...")
    
    with contextlib.closing(next(get_db())) as db:
        for tech in TECHNOLOGIES_TO_SEED:
            logger.info(f"--- Seeding technology: {tech} ---")
            
            # Check if questions already exist for this tech
            existing_count = db.query(KnowledgeQuestion).filter(KnowledgeQuestion.technology == tech).count()
            if existing_count > 0:
                logger.warning(f"'{tech}' already has {existing_count} questions. Skipping.")
                continue
                
            # 1. Call the OpenAI API
            try:
                logger.info(f"Calling OpenAI API for {QUESTIONS_PER_TECH} {tech} questions...")
                # This is your existing function. We use a generic JD description.
                jd_prompt = f"Generate a comprehensive list of interview questions for a mid-level developer specializing in {tech}."
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
                
                if not q_text or not a_text:
                    continue
                    
                kq = KnowledgeQuestion(
                    technology=tech,
                    question_text=q_text,
                    model_answer=a_text,
                    keywords=qa.get("keywords", [])
                )
                db.add(kq)
                inserted += 1
            
            db.commit()
            logger.info(f"Successfully saved {inserted} new questions for {tech}.")

    logger.info("Database seeding complete!")

if __name__ == "__main__":
    seed_database()
