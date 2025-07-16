import gradio as gr
from openai import OpenAI
import PyPDF2
import docx
import os
import json
from docx import Document
from datetime import datetime

# ✅ Credentials
USERNAME = "admin"
PASSWORD = "letmein123"

# ✅ OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ Extract uploaded resume text
def extract_text(file_path):
    ext = os.path.splitext(file_path)[-1].lower()
    if ext == ".pdf":
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            return "\n".join([page.extract_text() for page in reader.pages])
    elif ext == ".docx":
        doc = docx.Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs])
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return "❌ Unsupported file type."

# ✅ Resume from scratch
def generate_resume_from_scratch(full_name, email, phone, location, education, experience, skills, job_description):
    user_info = f"""
Full Name: {full_name}
Email: {email}
Phone: {phone}
Location: {location}
Education: {education}
Experience: {experience}
Skills: {skills}
"""
    prompt = f"""
You are a professional resume writer. Using the personal info and job description below, generate a complete professional resume with clear formatting.

User Info:
{user_info}

Target Job Description:
{job_description}

Format sections as: Summary, Experience, Education, Skills, etc. Write in a clean and formal tone. Output only the final resume text.
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    resume_text = response.choices[0].message.content
    return "", "", "", "", "", "", "", resume_text, "", []

# ✅ Analyze or generate resume
def get_resume_feedback_and_rewrite(resume_file, job_description,
    full_name, email, phone, location, education, experience, skills):

    try:
        if not resume_file:
            return generate_resume_from_scratch(
                full_name, email, phone, location, education, experience, skills, job_description
            )

        resume_text = extract_text(resume_file)
        prompt = f"""
You are a professional resume coach. Review the resume below and return your response strictly in this JSON format:
{{
  "scores": {{"grammar": 0-10, "structure": 0-10, "job_fit": 0-10}},
  "suggestions": ["..."],
  "rewritten_summary": "...",
  "improved_bullet_point": "...",
  "missing_keywords": ["..."],
  "rewritten_resume": "Full rewritten resume text here, with formatting and sections clearly labeled.",
  "mock_interview_questions": ["..."]
}}

Resume: {resume_text}
Job Description: {job_description or "N/A"}
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        data = json.loads(response.choices[0].message.content)

        scores = (
            f"📝 Grammar: {data['scores']['grammar']}/10\n"
            f"📐 Structure: {data['scores']['structure']}/10\n"
            f"🎯 Job Fit: {data['scores']['job_fit']}/10"
        )
        suggestions = "\n- " + "\n- ".join(data["suggestions"])
        summary = data["rewritten_summary"]
        bullet = data["improved_bullet_point"]
        keywords = ", ".join(data["missing_keywords"])
        rewritten_resume_text = data["rewritten_resume"]
        interview_questions = "\n- " + "\n- ".join(data["mock_interview_questions"])
        question_list = data["mock_interview_questions"]

        return (
            scores, suggestions, summary, bullet, keywords,
            resume_text, rewritten_resume_text, interview_questions, question_list
        )
    except Exception as e:
        return [f"❌ Error: {str(e)}"] * 9 + [[]]

# ✅ Download resume after editing
def save_and_download(edited_resume_text):
    filename = f"Edited_Resume_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    doc = Document()
    for line in edited_resume_text.splitlines():
        doc.add_paragraph(line)
    doc.save(filename)
    return filename

# ✅ Audio feedback
def get_audio_feedback(audio_path, selected_question):
    try:
        if not audio_path or not os.path.exists(audio_path):
            return "❌ Please record an answer first."
        with open(audio_path, "rb") as f:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=f).text
        prompt = f"""
You are an interview coach. Here's a mock interview question and the candidate's spoken answer.

Question: "{selected_question}"
Answer: "{transcript}"

Give constructive feedback on content, clarity, and relevance. Be professional and concise.
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Error: {e}"

# ✅ Login
def check_login(username, password):
    if username == USERNAME and password == PASSWORD:
        return gr.update(visible=False), gr.update(visible=True), ""
    else:
        return gr.update(), gr.update(visible=False), "❌ Incorrect username or password."

# ✅ UI
with gr.Blocks(title="AI Resume Tool") as app:
    with gr.Column(visible=True) as login_section:
        gr.Markdown("### 🔐 Login")
        username_input = gr.Textbox(label="Username")
        password_input = gr.Textbox(label="Password", type="password")
        login_btn = gr.Button("🔓 Login")
        login_error = gr.Textbox(interactive=False)

    with gr.Column(visible=False) as main_app:
        gr.Markdown("## 📄 Upload your resume *or* generate one from scratch.")

        with gr.Accordion("📥 Personal Info (for resume generation)", open=True):
            full_name = gr.Textbox(label="Full Name")
            email = gr.Textbox(label="Email")
            phone = gr.Textbox(label="Phone")
            location = gr.Textbox(label="Location")
            education = gr.Textbox(label="Education", lines=2)
            experience = gr.Textbox(label="Experience", lines=2)
            skills = gr.Textbox(label="Skills", lines=2)

        with gr.Row():
            resume_file = gr.File(label="📄 Upload Resume (.pdf, .docx, .txt)", type="filepath")
            job_input = gr.Textbox(label="Job Title or Job Description", lines=4)

        submit = gr.Button("🧠 Analyze or Generate Resume")

        with gr.Row():
            scores_out = gr.Textbox(label="📊 Scores")
            suggestions_out = gr.Textbox(label="🛠 Suggestions")
        with gr.Row():
            summary_out = gr.Textbox(label="✍️ Rewritten Summary")
            bullet_out = gr.Textbox(label="🔁 Improved Bullet Point")
            keywords_out = gr.Textbox(label="❗ Missing Keywords")
        with gr.Row():
            original_out = gr.Textbox(label="📄 Original Resume", lines=10)
            edited_resume_out = gr.Textbox(label="✍️ Editable Resume", lines=20)

        download_btn = gr.Button("⬇️ Download Edited Resume")
        download_file = gr.File(label="📥 Download Link")

        gr.Markdown("## 🎤 Mock Interview Questions")
        interview_out = gr.Textbox(label="Questions", lines=6)
        with gr.Row():
            question_dropdown = gr.Dropdown(label="Select Question", choices=[], interactive=True)
            audio_input = gr.Audio(sources="microphone", type="filepath", label="🎤 Record Answer")
        feedback_btn = gr.Button("🔍 Get Feedback")
        feedback_out = gr.Textbox(label="🧠 Feedback")

    # ✅ Link logic
    login_btn.click(check_login, [username_input, password_input], [login_section, main_app, login_error])
    submit.click(get_resume_feedback_and_rewrite, [
        resume_file, job_input, full_name, email, phone, location, education, experience, skills
    ], [
        scores_out, suggestions_out, summary_out, bullet_out, keywords_out,
        original_out, edited_resume_out, interview_out, question_dropdown
    ])
    download_btn.click(save_and_download, edited_resume_out, download_file)
    feedback_btn.click(get_audio_feedback, [audio_input, question_dropdown], feedback_out)

if __name__ == "__main__":
    print("✅ Launching app...")
    app.queue().launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 8080)))
