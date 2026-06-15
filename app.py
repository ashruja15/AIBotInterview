import streamlit as st
import os
import re
import json
import time
import wave
import random
import statistics
from datetime import datetime

import numpy as np
import speech_recognition as sr
from streamlit_mic_recorder import mic_recorder

try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    import docx
except Exception:
    docx = None


# ================= CONFIG =================
st.set_page_config(
    page_title="HireVoice AI",
    page_icon="🎙️",
    layout="wide"
)

MAX_QUESTIONS = 5
TIME_LIMIT = 120

os.makedirs("recordings", exist_ok=True)
os.makedirs("reports", exist_ok=True)


# ================= CSS =================
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #020617, #0f172a, #111827);
    color: white;
}

.main-title {
    text-align: center;
    font-size: 42px;
    font-weight: 800;
    color: #38bdf8;
    margin-bottom: 5px;
}

.subtitle {
    text-align: center;
    color: #cbd5e1;
    font-size: 18px;
    margin-bottom: 30px;
}

.card {
    background: rgba(30, 41, 59, 0.95);
    padding: 22px;
    border-radius: 18px;
    border: 1px solid #334155;
    margin-bottom: 18px;
}

.question-card {
    background: linear-gradient(135deg, #1e293b, #0f172a);
    padding: 25px;
    border-radius: 18px;
    border-left: 6px solid #38bdf8;
    font-size: 22px;
    font-weight: 600;
    margin-bottom: 20px;
}

.timer {
    background: #facc15;
    color: black;
    padding: 14px;
    border-radius: 14px;
    font-weight: bold;
    text-align: center;
    font-size: 22px;
    margin-bottom: 20px;
}

.metric-card {
    background: #020617;
    padding: 18px;
    border-radius: 14px;
    border: 1px solid #334155;
    text-align: center;
}

.success-box {
    background: #064e3b;
    padding: 15px;
    border-radius: 12px;
    color: #d1fae5;
}

.warning-box {
    background: #713f12;
    padding: 15px;
    border-radius: 12px;
    color: #fef3c7;
}

textarea {
    color: black !important;
}

.stButton button {
    border-radius: 12px;
    font-weight: 700;
    background: #38bdf8;
    color: black;
    border: none;
    padding: 10px;
}
</style>
""", unsafe_allow_html=True)


# ================= TEXT UTILITIES =================
def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_keywords(text):
    stopwords = {
        "and", "or", "the", "a", "an", "to", "of", "in", "on", "for",
        "with", "by", "from", "is", "are", "was", "were", "this", "that",
        "your", "you", "me", "my", "i", "we", "our", "as", "at", "be",
        "can", "will", "have", "has", "had", "it", "using", "used"
    }

    words = clean_text(text).split()
    keywords = []

    for word in words:
        if len(word) > 2 and word not in stopwords:
            keywords.append(word)

    return list(dict.fromkeys(keywords))


# ================= RESUME READING =================
def read_pdf(uploaded_file):
    if PyPDF2 is None:
        return ""

    text = ""
    try:
        reader = PyPDF2.PdfReader(uploaded_file)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception:
        text = ""

    return text


def read_docx(uploaded_file):
    if docx is None:
        return ""

    text = ""
    try:
        document = docx.Document(uploaded_file)
        for para in document.paragraphs:
            text += para.text + "\n"
    except Exception:
        text = ""

    return text


def read_resume(uploaded_file):
    filename = uploaded_file.name.lower()

    if filename.endswith(".pdf"):
        return read_pdf(uploaded_file)

    if filename.endswith(".docx"):
        return read_docx(uploaded_file)

    if filename.endswith(".txt"):
        return uploaded_file.read().decode("utf-8", errors="ignore")

    return ""


# ================= RESUME QUESTION GENERATION =================
def detect_skills(resume_text):
    known_skills = [
        "python", "java", "c", "c++", "sql", "mysql", "mongodb",
        "html", "css", "javascript", "react", "node", "express",
        "flask", "django", "spring", "spring boot",
        "machine learning", "ai", "artificial intelligence",
        "deep learning", "nlp", "rag", "langchain",
        "data structures", "algorithms", "dbms", "operating system",
        "computer networks", "git", "github", "aws", "streamlit",
        "pandas", "numpy", "scikit", "tensorflow", "keras"
    ]

    resume_clean = clean_text(resume_text)
    found = []

    for skill in known_skills:
        if skill in resume_clean:
            found.append(skill)

    return list(dict.fromkeys(found))


def extract_project_lines(resume_text):
    lines = resume_text.splitlines()
    project_lines = []

    project_words = [
        "project", "developed", "built", "created", "implemented",
        "designed", "system", "application", "chatbot", "dashboard",
        "website", "management"
    ]

    for line in lines:
        line_clean = clean_text(line)
        if len(line_clean.split()) >= 4:
            if any(word in line_clean for word in project_words):
                project_lines.append(line.strip())

    return project_lines[:8]


def generate_resume_questions(resume_text):
    skills = detect_skills(resume_text)
    project_lines = extract_project_lines(resume_text)

    questions = []

    questions.append({
        "question": "Tell me about yourself based on your resume.",
        "type": "HR",
        "keywords": ["education", "skills", "project", "internship", "goal"]
    })

    for skill in skills[:8]:
        questions.append({
            "question": f"You mentioned {skill} in your resume. Explain your experience with {skill}.",
            "type": "Resume Skill",
            "keywords": extract_keywords(skill) + ["experience", "project", "used", "learned"]
        })

    for project in project_lines[:5]:
        short_project = project[:120]
        questions.append({
            "question": f"Explain this project from your resume: {short_project}",
            "type": "Resume Project",
            "keywords": extract_keywords(project)[:10]
        })

    questions.extend([
        {
            "question": "Which project in your resume are you most confident about and why?",
            "type": "Project",
            "keywords": ["project", "problem", "technology", "implementation", "result"]
        },
        {
            "question": "What was the biggest technical challenge you faced in your project?",
            "type": "Technical",
            "keywords": ["challenge", "error", "debug", "solution", "learned"]
        },
        {
            "question": "Why should we hire you for this role?",
            "type": "HR",
            "keywords": ["skills", "learning", "hardworking", "project", "contribution"]
        },
        {
            "question": "What are your strengths and weaknesses?",
            "type": "HR",
            "keywords": ["strength", "weakness", "improve", "learning", "team"]
        }
    ])

    if len(questions) < MAX_QUESTIONS:
        questions.extend([
            {
                "question": "Explain any one technical concept you are strong in.",
                "type": "Technical",
                "keywords": ["concept", "example", "use", "advantage"]
            },
            {
                "question": "How do you keep improving your technical skills?",
                "type": "HR",
                "keywords": ["practice", "projects", "learning", "coding"]
            }
        ])

    random.shuffle(questions)
    return questions


# ================= AUDIO FUNCTIONS =================
def save_audio_file(audio_bytes, question_no):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"recordings/q{question_no}_{timestamp}.wav"

    with open(filename, "wb") as f:
        f.write(audio_bytes)

    return filename


def transcribe_audio(audio_file):
    recognizer = sr.Recognizer()

    try:
        with sr.AudioFile(audio_file) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio_data = recognizer.record(source)

        text = recognizer.recognize_google(audio_data)
        return text

    except sr.UnknownValueError:
        return ""

    except sr.RequestError:
        return ""

    except Exception:
        return ""


def read_wav_as_float(audio_file):
    with wave.open(audio_file, "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        frame_rate = wf.getframerate()
        total_frames = wf.getnframes()
        raw_audio = wf.readframes(total_frames)

    if sample_width == 1:
        audio_np = np.frombuffer(raw_audio, dtype=np.uint8).astype(np.float32)
        audio_np = (audio_np - 128) / 128.0

    elif sample_width == 2:
        audio_np = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32)
        audio_np = audio_np / 32768.0

    elif sample_width == 4:
        audio_np = np.frombuffer(raw_audio, dtype=np.int32).astype(np.float32)
        audio_np = audio_np / 2147483648.0

    else:
        audio_np = np.array([], dtype=np.float32)

    if channels > 1 and len(audio_np) > 0:
        audio_np = audio_np.reshape(-1, channels)
        audio_np = audio_np.mean(axis=1)

    duration = len(audio_np) / frame_rate if frame_rate > 0 else 0

    return audio_np, frame_rate, duration


def analyze_voice(audio_file, answer_text):
    try:
        audio_np, frame_rate, duration = read_wav_as_float(audio_file)

        if len(audio_np) == 0 or duration == 0:
            return 0, "No valid voice detected", {}

        chunk_size = int(frame_rate * 0.5)
        rms_values = []

        for i in range(0, len(audio_np), chunk_size):
            chunk = audio_np[i:i + chunk_size]
            if len(chunk) > 0:
                rms = float(np.sqrt(np.mean(chunk ** 2)))
                rms_values.append(rms)

        if not rms_values:
            return 0, "No clear voice found", {}

        avg_volume = statistics.mean(rms_values)
        volume_std = statistics.stdev(rms_values) if len(rms_values) > 1 else 0

        stability = max(
            0,
            100 - ((volume_std / max(avg_volume, 0.0001)) * 100)
        )

        threshold = max(avg_volume * 0.35, 0.005)
        voiced_chunks = [v for v in rms_values if v > threshold]
        speech_ratio = len(voiced_chunks) / len(rms_values)

        words = clean_text(answer_text).split()
        word_count = len(words)

        pace = word_count / duration * 60 if duration > 0 else 0

        filler_words = [
            "um", "uh", "like", "actually", "basically",
            "you know", "i mean", "hmm"
        ]

        answer_clean = clean_text(answer_text)
        filler_count = 0

        for filler in filler_words:
            filler_count += answer_clean.count(filler)

        score = 0
        remarks = []

        if 8 <= duration <= 90:
            score += 1
            remarks.append("Good answer duration")
        elif 4 <= duration < 8 or 90 < duration <= 120:
            score += 0.5
            remarks.append("Average answer duration")
        else:
            remarks.append("Duration needs improvement")

        if avg_volume >= 0.025:
            score += 1
            remarks.append("Voice is clear")
        elif avg_volume >= 0.010:
            score += 0.5
            remarks.append("Voice is slightly low")
        else:
            remarks.append("Voice is too low")

        if stability >= 55:
            score += 1
            remarks.append("Stable voice")
        elif stability >= 30:
            score += 0.5
            remarks.append("Average voice stability")
        else:
            remarks.append("Voice stability needs improvement")

        if speech_ratio >= 0.55:
            score += 1
            remarks.append("Good continuous speaking")
        elif speech_ratio >= 0.30:
            score += 0.5
            remarks.append("Some pauses detected")
        else:
            remarks.append("Too much silence")

        if word_count == 0:
            remarks.append("Speech was recorded but not clearly recognized")
        else:
            if 80 <= pace <= 180 and filler_count <= 2:
                score += 1
                remarks.append("Good pace and fewer filler words")
            elif 50 <= pace <= 230 and filler_count <= 4:
                score += 0.5
                remarks.append("Average speaking pace")
            else:
                remarks.append("Pace or filler words need improvement")

        report = {
            "duration": round(duration, 2),
            "average_volume": round(avg_volume, 4),
            "voice_stability": round(stability, 2),
            "speech_ratio": round(speech_ratio * 100, 2),
            "pace_words_per_minute": round(pace, 2),
            "filler_words": filler_count
        }

        return round(score, 2), ", ".join(remarks), report

    except Exception as e:
        return 0, f"Voice analysis failed: {str(e)}", {}


# ================= SCORING =================
def evaluate_answer(answer_text, keywords):
    answer_clean = clean_text(answer_text)

    if not answer_clean:
        return 0, [], "No answer detected"

    words = answer_clean.split()
    matched = []

    for keyword in keywords:
        if clean_text(keyword) in answer_clean:
            matched.append(keyword)

    keyword_score = 0

    if keywords:
        ratio = len(matched) / len(keywords)

        if ratio >= 0.80:
            keyword_score = 5
        elif ratio >= 0.60:
            keyword_score = 4
        elif ratio >= 0.40:
            keyword_score = 3
        elif ratio >= 0.20:
            keyword_score = 2
        elif ratio > 0:
            keyword_score = 1
        else:
            keyword_score = 0

    length_score = 0

    if len(words) >= 45:
        length_score = 5
    elif len(words) >= 30:
        length_score = 4
    elif len(words) >= 18:
        length_score = 3
    elif len(words) >= 10:
        length_score = 2
    elif len(words) >= 4:
        length_score = 1

    final_content_score = round((keyword_score * 0.7) + (length_score * 0.3), 2)

    if final_content_score >= 4:
        status = "Excellent answer"
    elif final_content_score >= 3:
        status = "Good answer"
    elif final_content_score >= 2:
        status = "Average answer"
    elif final_content_score > 0:
        status = "Weak answer"
    else:
        status = "Answer not relevant"

    return final_content_score, matched, status


# ================= SESSION STATE =================
defaults = {
    "resume_text": "",
    "questions": [],
    "started": False,
    "current_index": 0,
    "start_time": None,
    "answers": [],
    "audio_files": {},
    "transcripts": {}
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


def reset_all():
    st.session_state.resume_text = ""
    st.session_state.questions = []
    st.session_state.started = False
    st.session_state.current_index = 0
    st.session_state.start_time = None
    st.session_state.answers = []
    st.session_state.audio_files = {}
    st.session_state.transcripts = {}


def save_report():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"reports/interview_report_{timestamp}.json"

    data = {
        "created_at": timestamp,
        "total_questions": len(st.session_state.answers),
        "answers": st.session_state.answers
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    return report_path


# ================= UI HEADER =================
st.markdown("<div class='main-title'>🎙️ HireVoice AI</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='subtitle'>Resume-based AI interview practice with voice recording, transcript, scoring and feedback</div>",
    unsafe_allow_html=True
)


# ================= SIDEBAR =================
with st.sidebar:
    st.header("⚙️ Interview Setup")
    uploaded_resume = st.file_uploader(
        "Upload Resume",
        type=["pdf", "docx", "txt"]
    )

    if uploaded_resume:
        resume_text = read_resume(uploaded_resume)

        if resume_text.strip():
            st.session_state.resume_text = resume_text
            st.success("Resume uploaded successfully")

            skills = detect_skills(resume_text)
            if skills:
                st.write("Detected Skills:")
                st.write(", ".join(skills[:10]))
        else:
            st.error("Could not read resume. Try PDF, DOCX or TXT.")

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("Start"):
            if not st.session_state.resume_text.strip():
                st.error("Please upload resume first.")
            else:
                st.session_state.questions = generate_resume_questions(
                    st.session_state.resume_text
                )[:MAX_QUESTIONS]
                st.session_state.started = True
                st.session_state.current_index = 0
                st.session_state.answers = []
                st.session_state.audio_files = {}
                st.session_state.transcripts = {}
                st.session_state.start_time = time.time()
                st.rerun()

    with col_b:
        if st.button("Reset"):
            reset_all()
            st.rerun()


# ================= RESUME PREVIEW =================
if not st.session_state.started:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("📌 How this app works")
    st.write("""
    1. Upload your resume.
    2. The app reads your skills and projects.
    3. It asks interview questions based on your resume.
    4. You answer using voice.
    5. Your voice is recorded and saved.
    6. Speech is converted into text.
    7. Final score is calculated using content quality and voice/tone.
    """)
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.resume_text:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("📄 Resume Preview")
        st.text_area(
            "Extracted Resume Text",
            st.session_state.resume_text[:3000],
            height=250
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()


# ================= FINAL RESULT =================
if st.session_state.current_index >= MAX_QUESTIONS:
    st.success("✅ Interview Completed")

    total_score = sum(item["final_score"] for item in st.session_state.answers)
    avg_score = total_score / len(st.session_state.answers)

    avg_content = sum(item["content_score"] for item in st.session_state.answers) / len(st.session_state.answers)
    avg_voice = sum(item["voice_score"] for item in st.session_state.answers) / len(st.session_state.answers)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.metric("Final Score", f"{round(total_score, 2)}/{MAX_QUESTIONS * 5}")
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.metric("Average Score", f"{round(avg_score, 2)}/5")
        st.markdown("</div>", unsafe_allow_html=True)

    with c3:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.metric("Voice Score", f"{round(avg_voice, 2)}/5")
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("📘 Average Content Score:", round(avg_content, 2), "/5")
    st.write("🎤 Average Voice/Tone Score:", round(avg_voice, 2), "/5")

    if avg_score >= 4:
        st.success("Excellent performance. You answered confidently and clearly.")
    elif avg_score >= 2.5:
        st.warning("Good performance. Improve explanation depth and speaking clarity.")
    else:
        st.error("Needs more practice. Try giving longer and more relevant answers.")

    report_path = save_report()

    st.download_button(
        "⬇️ Download Interview Report JSON",
        data=json.dumps(st.session_state.answers, indent=4),
        file_name="lockedai_interview_report.json",
        mime="application/json"
    )

    st.subheader("📊 Detailed Analysis")

    for i, item in enumerate(st.session_state.answers, 1):
        with st.expander(f"Question {i}: {item['question']}"):
            st.write("Type:", item["question_type"])
            st.write("Transcript:", item["transcript"])
            st.write("Matched Keywords:", ", ".join(item["matched_keywords"]) if item["matched_keywords"] else "No keywords matched")
            st.write("Content Status:", item["content_status"])
            st.write("Content Score:", f"{item['content_score']}/5")
            st.write("Voice Status:", item["voice_status"])
            st.write("Voice Score:", f"{item['voice_score']}/5")
            st.write("Final Score:", f"{item['final_score']}/5")
            st.write("Audio File:", item["audio_file"])
            st.json(item["voice_report"])

            if os.path.exists(item["audio_file"]):
                with open(item["audio_file"], "rb") as f:
                    st.audio(f.read(), format="audio/wav")

    if st.button("🔄 Start New Interview"):
        reset_all()
        st.rerun()

    st.stop()


# ================= QUESTION FLOW =================
current_index = st.session_state.current_index
question_obj = st.session_state.questions[current_index]

if st.session_state.start_time is None:
    st.session_state.start_time = time.time()

elapsed = int(time.time() - st.session_state.start_time)
remaining = max(0, TIME_LIMIT - elapsed)

mins = remaining // 60
secs = remaining % 60

st.markdown(
    f"<div class='timer'>⏳ Time Left: {mins:02d}:{secs:02d}</div>",
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class='question-card'>
    Question {current_index + 1}/{MAX_QUESTIONS}<br><br>
    ❓ {question_obj["question"]}
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("<div class='card'>", unsafe_allow_html=True)
st.subheader("🎤 Record Your Answer")

audio = mic_recorder(
    start_prompt="🎙 Start Recording",
    stop_prompt="⏹ Stop Recording",
    just_once=True,
    use_container_width=True,
    format="wav",
    key=f"recorder_{current_index}"
)

audio_file = st.session_state.audio_files.get(current_index)
transcript = st.session_state.transcripts.get(current_index, "")

if audio and "bytes" in audio:
    audio_bytes = audio["bytes"]

    if audio_bytes:
        audio_file = save_audio_file(audio_bytes, current_index + 1)
        transcript = transcribe_audio(audio_file)

        st.session_state.audio_files[current_index] = audio_file
        st.session_state.transcripts[current_index] = transcript

        st.rerun()

if audio_file:
    st.success("Voice recorded successfully.")
    st.write("Saved Audio:", audio_file)

    with open(audio_file, "rb") as f:
        st.audio(f.read(), format="audio/wav")

    if transcript:
        st.info("Transcript:")
        st.write(transcript)
    else:
        st.warning("Audio recorded, but speech was not recognized clearly.")

else:
    st.info("Click Start Recording, speak your answer, then click Stop Recording.")

st.markdown("</div>", unsafe_allow_html=True)


# ================= OPTIONAL TEXT FIX =================
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.subheader("✍️ Optional: Edit transcript before submitting")

edited_transcript = st.text_area(
    "Transcript / Answer Text",
    value=transcript,
    height=150,
    key=f"edited_text_{current_index}"
)

st.markdown("</div>", unsafe_allow_html=True)


# ================= SUBMIT ANSWER =================
submit_disabled = not audio_file and not edited_transcript.strip()

if st.button("✅ Submit Answer", disabled=submit_disabled):
    final_answer = edited_transcript.strip()

    keywords = question_obj.get("keywords", [])

    content_score, matched_keywords, content_status = evaluate_answer(
        final_answer,
        keywords
    )

    if audio_file:
        voice_score, voice_status, voice_report = analyze_voice(
            audio_file,
            final_answer
        )
    else:
        voice_score = 0
        voice_status = "No voice recorded"
        voice_report = {}

    final_score = round((content_score * 0.7) + (voice_score * 0.3), 2)

    st.session_state.answers.append({
        "question": question_obj["question"],
        "question_type": question_obj["type"],
        "transcript": final_answer if final_answer else "No transcript",
        "matched_keywords": matched_keywords,
        "content_status": content_status,
        "content_score": content_score,
        "voice_status": voice_status,
        "voice_score": voice_score,
        "voice_report": voice_report,
        "final_score": final_score,
        "audio_file": audio_file if audio_file else "No audio"
    })

    st.session_state.current_index += 1
    st.session_state.start_time = time.time()

    st.rerun()


# ================= AUTO SUBMIT WHEN TIME OVER =================
if remaining == 0:
    final_answer = edited_transcript.strip()

    keywords = question_obj.get("keywords", [])

    content_score, matched_keywords, content_status = evaluate_answer(
        final_answer,
        keywords
    )

    if audio_file:
        voice_score, voice_status, voice_report = analyze_voice(
            audio_file,
            final_answer
        )
    else:
        voice_score = 0
        voice_status = "Time over and no voice recorded"
        voice_report = {}

    final_score = round((content_score * 0.7) + (voice_score * 0.3), 2)

    st.session_state.answers.append({
        "question": question_obj["question"],
        "question_type": question_obj["type"],
        "transcript": final_answer if final_answer else "No answer",
        "matched_keywords": matched_keywords,
        "content_status": content_status,
        "content_score": content_score,
        "voice_status": voice_status,
        "voice_score": voice_score,
        "voice_report": voice_report,
        "final_score": final_score,
        "audio_file": audio_file if audio_file else "No audio"
    })

    st.session_state.current_index += 1
    st.session_state.start_time = time.time()

    st.rerun()
