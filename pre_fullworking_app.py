import gradio as gr
from openai import OpenAI
import PyPDF2
import docx
import os
import json
from docx import Document
from datetime import datetime

# Login credentials
USERNAME = "admin"
PASSWORD = "letmein123"

# Initialize OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Extract resume text
def extract_text(file_path):
    ext = os.path.splitext(file_path)[-1].lower()
    if ext == ".pdf":
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    elif ext == ".docx":
        doc = docx.Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs])
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return "❌ Unsupported file type."

# Write editable resume content to docx
def save_edited_resume(text):
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    filename = f"Final_Resume_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    doc.save(filename)
    return filename

# Generate resume from scratch
def generate_resume(user_info, job_description):
    full_name, email, phone, location, education, experience, skills = user_info
    prompt = f"""
You are a professional resume writer. Write a resume from scratch for someone applying to this job:
"{job_description}"

Personal Info:
Full Name: {full_name}
Email: {email}
Phone: {phone}
Location: {location}
Education: {education}
Experience: {experience}
Skills: {skills}

Format it clearly using sections like Summary, Experience, Education, Skills, etc.
Respond with only the resume text.
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content

# Resume feedback or generation handler
def get_resume_feedback_and_rewrite(file_path, job_description, *user_info):
    try:
        if not file_path:
            resume_text = generate_resume(user_info, job_description)
            original_text = resume_text
        else:
            resume_text = extract_text(file_path)
            original_text = resume_text

        prompt = f"""
You are a resume coach. Review the resume below and respond strictly in JSON:
{{
  "scores": {{"grammar": 0-10, "structure": 0-10, "job_fit": 0-10}},
  "suggestions": ["..."],
  "rewritten_summary": "...",
  "improved_bullet_point": "...",
  "missing_keywords": ["..."],
  "rewritten_resume": "...",
  "mock_interview_questions": ["..."]
}}
Resume: {resume_text}
Job Description: {job_description}
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
        rewritten_resume = data["rewritten_resume"]
        questions = "\n- " + "\n- ".join(data["mock_interview_questions"])

        return scores, suggestions, summary, bullet, keywords, original_text, rewritten_resume, questions, data["mock_interview_questions"]
    except Exception as e:
        return [f"❌ Error: {str(e)}"] * 9 + [[]]

# Audio feedback
def get_audio_feedback(audio_path, question):
    try:
        if not audio_path:
            return "❌ Please record an answer."
        with open(audio_path, "rb") as f:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=f).text
        prompt = f"""You are an interview coach.
Question: {question}
Answer: {transcript}
Give constructive, concise feedback on content and delivery."""
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"❌ Error: {e}"

# Login check
def check_login(username, password):
    if username == USERNAME and password == PASSWORD:
        return gr.update(visible=False), gr.update(visible=True), ""
    else:
        return gr.update(), gr.update(visible=False), "❌ Incorrect login"

# App UI
with gr.Blocks(title="Resume Builder & Reviewer") as app:
    with gr.Column(visible=True) as login_section:
        gr.Markdown("### 🔐 Login")
        username_input = gr.Textbox(label="Username")
        password_input = gr.Textbox(label="Password", type="password")
        login_btn = gr.Button("Login")
        login_error = gr.Textbox(label="", interactive=False)

    with gr.Column(visible=False) as main_app:
        gr.Markdown("## ✍️ Fill info or upload resume to get feedback or generate one")

        with gr.Row():
            resume_file = gr.File(label="📄 Upload Resume (optional)", type="filepath")
            job_input = gr.Textbox(label="📋 Job Title or Description", lines=4)

        gr.Markdown("### 👤 Your Information (optional if uploading resume)")
        full_name = gr.Textbox(label="Full Name")
        email = gr.Textbox(label="Email")
        phone = gr.Textbox(label="Phone")
        location = gr.Textbox(label="Location")
        education = gr.Textbox(label="Education")
        experience = gr.Textbox(label="Experience")
        skills = gr.Textbox(label="Skills")

        submit = gr.Button("🧠 Analyze / Generate Resume")

        with gr.Row():
            scores_out = gr.Textbox(label="📊 Scores")
            suggestions_out = gr.Textbox(label="🛠 Suggestions")
        with gr.Row():
            summary_out = gr.Textbox(label="✍️ Summary")
            bullet_out = gr.Textbox(label="🔁 Bullet Point")
            keywords_out = gr.Textbox(label="❗ Missing Keywords")

        gr.Markdown("### 📝 View & Edit Resume")
        original_out = gr.Textbox(label="📄 Original Resume", lines=20)
        rewritten_out = gr.Textbox(label="✍️ Rewritten Resume (Editable)", lines=20)

        download_btn = gr.Button("⬇️ Download Final Resume")
        final_file_out = gr.File(label="📥 Download Link")

        gr.Markdown("### 🎤 Interview Questions")
        interview_out = gr.Textbox(label="🧠 Mock Interview Questions", lines=8)
        question_dropdown = gr.Dropdown(label="Select Question", choices=[], interactive=True)
        audio_input = gr.Audio(sources="microphone", type="filepath", label="🎤 Answer")
        feedback_btn = gr.Button("🔍 Get Audio Feedback")
        feedback_out = gr.Textbox(label="🎯 Interview Feedback")

    # Bind actions
    login_btn.click(check_login, [username_input, password_input], [login_section, main_app, login_error])
    submit.click(get_resume_feedback_and_rewrite,
        [resume_file, job_input, full_name, email, phone, location, education, experience, skills],
        [scores_out, suggestions_out, summary_out, bullet_out, keywords_out,
         original_out, rewritten_out, interview_out, question_dropdown]
    )
    download_btn.click(save_edited_resume, [rewritten_out], final_file_out)
    feedback_btn.click(get_audio_feedback, [audio_input, question_dropdown], feedback_out)

if __name__ == "__main__":
    print("✅ Launching app...")
    app.queue().launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 8080))
    )
