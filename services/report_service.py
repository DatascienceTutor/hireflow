"""
Service for generating PDF reports.
"""
from fpdf import FPDF
from typing import Dict, Any, List
from datetime import datetime

class PDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 15)
        self.cell(0, 10, 'Candidate Interview Summary Report', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Helvetica', 'B', 12)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 6, title, 0, 1, 'L', 1)
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Helvetica', '', 10)
        self.multi_cell(0, 5, body)
        self.ln()

    def score_metric(self, title, value, color):
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(*color)
        self.cell(0, 6, f"{title}: {value}", ln=1) # FIX: Explicitly add a line break
        self.set_text_color(0, 0, 0) # Reset color
        self.ln(2)

def generate_summary_report_pdf(
    candidate_data: Dict[str, Any],
    job_data: Dict[str, Any],
    interview_data: Dict[str, Any],
    answers_data: List[Dict[str, Any]]
) -> bytes:
    """
    Generates a comprehensive PDF report for a candidate's interview.
    """
    pdf = PDF()
    pdf.add_page()

    # --- Section 1: Overview ---
    pdf.chapter_title('Interview Overview')
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(40, 7, "Candidate Name:")
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 7, candidate_data.get('name', 'N/A'), 0, 1)

    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(40, 7, "Job Title:")
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 7, job_data.get('title', 'N/A'), 0, 1)

    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(40, 7, "Final Score:")
    pdf.set_font('Helvetica', '', 11)
    score = interview_data.get('final_score')
    pdf.cell(0, 7, f"{score:.1f}/100" if score is not None else "Not Scored", 0, 1)

    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(40, 7, "Final Decision:")
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 7, interview_data.get('final_selection_status', 'N/A'), 0, 1)
    pdf.ln(10)

    # --- Section 2: AI Resume Match Report ---
    match_report = interview_data.get('match_report')
    if match_report:
        pdf.chapter_title('AI Resume Match Report')
        score = match_report.get('score', 0)
        color = (0, 128, 0) if score > 75 else ((255, 165, 0) if score > 50 else (255, 0, 0))
        pdf.score_metric("Resume Match Score", f"{score}%", color)
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 6, "Summary:", 0, 1)
        pdf.chapter_body(match_report.get('summary', 'N/A'))

        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 6, "Strengths:", 0, 1)
        for strength in match_report.get('strengths', []):
            pdf.chapter_body(f"- {strength}")

        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 6, "Gaps:", 0, 1)
        for gap in match_report.get('gaps', []):
            pdf.chapter_body(f"- {gap}")
        pdf.ln(5)

    # --- Section 3: Detailed Question Review ---
    pdf.chapter_title('Detailed Question & Answer Review')
    for i, answer in enumerate(answers_data):
        pdf.set_font('Helvetica', 'B', 11)
        pdf.multi_cell(0, 5, f"Q{i+1}: {answer.get('question_text', 'N/A')}")
        pdf.ln(2)

        pdf.set_font('Helvetica', 'I', 10)
        pdf.multi_cell(0, 5, f"Candidate's Answer: {answer.get('answer_text', 'N/A')}")
        pdf.ln(3)

        pdf.score_metric("Score", f"{answer.get('llm_score', 'N/A')}/100", (0,0,0))

        feedback = answer.get('feedback')
        if isinstance(feedback, dict):
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(0, 5, "AI Feedback:", ln=1) # FIX: Explicitly add a line break
            
            pdf.set_font('Helvetica', 'I', 10)
            pdf.set_fill_color(240, 255, 240) # Light green
            pdf.multi_cell(0, 5, f"What Was Good: {feedback.get('what_was_good', 'N/A')}", border=0, align='L', fill=True, ln=1)
            
            pdf.set_fill_color(255, 240, 240) # Light red
            pdf.multi_cell(0, 5, f"What Was Missing: {feedback.get('what_was_missing', 'N/A')}", border=0, align='L', fill=True, ln=1)
            
            pdf.set_fill_color(245, 245, 245) # Light grey
            pdf.multi_cell(0, 5, f"Technical Accuracy: {feedback.get('technical_accuracy', 'N/A')}", border=0, align='L', fill=True, ln=1)
            pdf.multi_cell(0, 5, f"Clarity & Communication: {feedback.get('clarity_and_communication', 'N/A')}", border=0, align='L', fill=True, ln=1)

        pdf.ln(8)

    # --- Finalize ---
    pdf.set_author("Hire Flow Platform")
    pdf.set_title(f"Report for {candidate_data.get('name', 'candidate')}")
    
    # Return the PDF as bytes
    return bytes(pdf.output(dest='S'))