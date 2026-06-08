import streamlit as st
import json
import random
import time
import re
import html
import hashlib
import os
import wave
import statistics
from datetime import datetime

import numpy as np
import speech_recognition as sr
import streamlit.components.v1 as components
from streamlit_mic_recorder import mic_recorder

# ---------------- CONFIG ----------------
st.set_page_config(page_title="AI Interview Bot", layout="wide")

MAX = 5
TIME_LIMIT = 120

os.makedirs("recordings", exist_ok=True)

# ---------------- CSS ----------------
st.markdown("""
<style>
.stApp {
    background:#0f172a;
    color:white;
}
.title {
    text-align:center;
    font-size:40px;
    font-weight:bold;
    color:#00d9f5;
}
.ai {
    background:#1e293b;
    padding:18px;
    border-radius:12px;
    margin:10px;
    font-size:20px;
}
.timer {
    background:#facc15;
    color:black;
    padding:12px;
    border-radius:10px;
    font-weight:bold;
    text-align:center;
    font-size:20px;
}
.voice-box {
    background:#172554;
    padding:15px;
    border-radius:12px;
    margin-top:10px;
}
.score-card {
    background:#1e293b;
    padding:15px;
    border-radius:12px;
    margin:10px 0;
}
.stButton button {
    width:100%;
    border-radius:10px;
    background:#00d9f5;
    color:black;
    font-weight:bold;
}
textarea {
    color:black !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------- LOAD QUESTIONS ----------------
with open("questions.json", "r", encoding="utf-8") as f:
    TECH_QUESTIONS = json.load(f)

HR_QUESTIONS = [
    {"question": "Tell me about yourself", "answer": "", "keywords": []},
    {"question": "Why should we hire you", "answer": "", "keywords": []},
    {"question": "What are your strengths", "answer": "", "keywords": []},
    {"question": "What are your weaknesses", "answer": "", "keywords": []},
    {"question": "How do you handle pressure", "answer": "", "keywords": []}
]

RAPID_QUESTIONS = [
    {
        "question": "What is DBMS",
        "answer": "DBMS is software used to store manage and retrieve data",
        "keywords": ["software", "store", "manage", "retrieve", "data"]
    },
    {
        "question": "What is HTTP",
        "answer": "HTTP is a protocol used for communication between browser and server",
        "keywords": ["protocol", "communication", "browser", "server"]
    },
    {
        "question": "What is primary key",
        "answer": "Primary key uniquely identifies each record in a table",
        "keywords": ["uniquely", "identifies", "record", "table"]
    },
    {
        "question": "What is indexing",
        "answer": "Indexing improves speed of data retrieval",
        "keywords": ["speed", "data", "retrieval"]
    },
    {
        "question": "What is normalization",
        "answer": "Normalization reduces redundancy and improves data integrity",
        "keywords": ["redundancy", "data", "integrity"]
    }
]

# ---------------- SESSION DEFAULTS ----------------
defaults = {
    "start": False,
    "q": None,
    "q_obj": None,
    "count": 0,
    "used_q": [],
    "scores": [],
    "content_scores": [],
    "tone_scores": [],
    "answers": [],
    "start_time": None,
    "voice_answers": {},
    "voice_files": {},
    "tone_reports": {}
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------- TEXT FUNCTIONS ----------------
def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text


def get_question(mode):
    if mode == "Technical":
        source = TECH_QUESTIONS
    elif mode == "HR":
        source = HR_QUESTIONS
    else:
        source = RAPID_QUESTIONS

    remaining = [
        q for q in source
        if q["question"] not in st.session_state.used_q
    ]

    if not remaining:
        remaining = source

    q_obj = random.choice(remaining)
    st.session_state.used_q.append(q_obj["question"])
    return q_obj


def evaluate_content(user_answer, correct_answer, keywords):
    user_answer_clean = clean_text(user_answer)

    if not user_answer_clean:
        return 0, [], "No answer"

    if not keywords:
        word_count = len(user_answer_clean.split())

        if word_count >= 20:
            return 5, [], "Excellent HR answer"
        elif word_count >= 12:
            return 4, [], "Good HR answer"
        elif word_count >= 8:
            return 3, [], "Acceptable HR answer"
        elif word_count >= 4:
            return 2, [], "Short HR answer"
        else:
            return 1, [], "Too short"

    matched_keywords = []

    for keyword in keywords:
        if clean_text(keyword) in user_answer_clean:
            matched_keywords.append(keyword)

    ratio = len(matched_keywords) / len(keywords)

    if ratio >= 0.80:
        return 5, matched_keywords, "Excellent"
    elif ratio >= 0.60:
        return 4, matched_keywords, "Good"
    elif ratio >= 0.40:
        return 3, matched_keywords, "Partially Correct"
    elif ratio >= 0.20:
        return 2, matched_keywords, "Somewhat Correct"
    elif ratio > 0:
        return 1, matched_keywords, "Very Little Correct"
    else:
        return 0, matched_keywords, "Wrong"


# ---------------- BOT VOICE QUESTION ----------------
def speak_question_once(question, count):
    safe_question = html.escape(question)
    q_hash = hashlib.md5(question.encode()).hexdigest()
    speak_key = f"spoken_question_{count}_{q_hash}"

    components.html(
        f"""
        <script>
        const key = "{speak_key}";
        const text = "{safe_question}";

        if (!sessionStorage.getItem(key)) {{
            const msg = new SpeechSynthesisUtterance(text);
            msg.lang = "en-US";
            msg.rate = 0.9;
            msg.pitch = 1;

            window.speechSynthesis.cancel();
            window.speechSynthesis.speak(msg);

            sessionStorage.setItem(key, "true");
        }}
        </script>
        """,
        height=0
    )


def replay_question(question):
    safe_question = html.escape(question)

    components.html(
        f"""
        <script>
        const text = "{safe_question}";
        const msg = new SpeechSynthesisUtterance(text);
        msg.lang = "en-US";
        msg.rate = 0.9;
        msg.pitch = 1;

        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(msg);
        </script>
        """,
        height=0
    )


# ---------------- AUDIO FUNCTIONS ----------------
def save_audio_file(audio_bytes, question_no):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"recordings/question_{question_no}_{timestamp}.wav"

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
        audio_np = np.frombuffer(raw_audio, dtype=np.uint8)
        audio_np = audio_np.astype(np.float32)
        audio_np = (audio_np - 128) / 128.0

    elif sample_width == 2:
        audio_np = np.frombuffer(raw_audio, dtype=np.int16)
        audio_np = audio_np.astype(np.float32) / 32768.0

    elif sample_width == 4:
        audio_np = np.frombuffer(raw_audio, dtype=np.int32)
        audio_np = audio_np.astype(np.float32) / 2147483648.0

    else:
        audio_np = np.array([], dtype=np.float32)

    if channels > 1 and len(audio_np) > 0:
        audio_np = audio_np.reshape(-1, channels)
        audio_np = audio_np.mean(axis=1)

    duration = len(audio_np) / frame_rate if frame_rate > 0 else 0

    return audio_np, frame_rate, duration


def analyze_tone(audio_file, answer_text):
    try:
        audio_np, frame_rate, duration = read_wav_as_float(audio_file)

        if len(audio_np) == 0 or duration == 0:
            return 0, "No valid voice detected", {
                "duration": 0,
                "avg_volume": 0,
                "voice_stability": 0,
                "speech_ratio": 0,
                "pace": 0,
                "filler_count": 0
            }

        chunk_size = int(frame_rate * 0.5)
        rms_values = []

        for i in range(0, len(audio_np), chunk_size):
            chunk = audio_np[i:i + chunk_size]

            if len(chunk) > 0:
                rms = float(np.sqrt(np.mean(chunk ** 2)))
                rms_values.append(rms)

        if not rms_values:
            return 0, "No clear voice detected", {
                "duration": round(duration, 2),
                "avg_volume": 0,
                "voice_stability": 0,
                "speech_ratio": 0,
                "pace": 0,
                "filler_count": 0
            }

        avg_volume = statistics.mean(rms_values)

        if len(rms_values) > 1:
            volume_std = statistics.stdev(rms_values)
        else:
            volume_std = 0

        voice_stability = max(
            0,
            100 - ((volume_std / max(avg_volume, 0.0001)) * 100)
        )

        # speech ratio means how much part of the audio has audible voice
        voice_threshold = max(avg_volume * 0.35, 0.005)
        voiced_chunks = [v for v in rms_values if v > voice_threshold]
        speech_ratio = len(voiced_chunks) / len(rms_values)

        words = clean_text(answer_text).split()
        word_count = len(words)

        if duration > 0 and word_count > 0:
            pace = word_count / duration * 60
        else:
            pace = 0

        filler_words = [
            "um", "uh", "like", "actually", "basically",
            "you know", "i mean", "hmm", "aaa"
        ]

        answer_clean = clean_text(answer_text)
        filler_count = 0

        for filler in filler_words:
            filler_count += answer_clean.count(filler)

        tone_score = 0
        remarks = []

        # 1. Duration score
        if 8 <= duration <= 90:
            tone_score += 1
            remarks.append("Good answer duration")
        elif 4 <= duration < 8 or 90 < duration <= 120:
            tone_score += 0.5
            remarks.append("Average answer duration")
        else:
            remarks.append("Answer duration needs improvement")

        # 2. Volume score
        if avg_volume >= 0.025:
            tone_score += 1
            remarks.append("Voice is clear and audible")
        elif avg_volume >= 0.010:
            tone_score += 0.5
            remarks.append("Voice is slightly low")
        else:
            remarks.append("Voice is too low")

        # 3. Stability score
        if voice_stability >= 55:
            tone_score += 1
            remarks.append("Voice is stable")
        elif voice_stability >= 30:
            tone_score += 0.5
            remarks.append("Voice stability is average")
        else:
            remarks.append("Voice is not stable")

        # 4. Speech ratio score
        if speech_ratio >= 0.55:
            tone_score += 1
            remarks.append("Good continuous speaking")
        elif speech_ratio >= 0.30:
            tone_score += 0.5
            remarks.append("Some pauses detected")
        else:
            remarks.append("Too much silence or unclear speech")

        # 5. Pace and filler score
        if word_count == 0:
            if speech_ratio >= 0.55 and avg_volume >= 0.025:
                tone_score += 0.5
                remarks.append("Voice detected, but text was not recognized")
            else:
                remarks.append("Speech text not recognized")
        else:
            if 80 <= pace <= 180 and filler_count <= 2:
                tone_score += 1
                remarks.append("Good speaking pace and fewer filler words")
            elif 50 <= pace <= 230 and filler_count <= 4:
                tone_score += 0.5
                remarks.append("Average speaking pace")
            else:
                remarks.append("Speaking pace or filler words need improvement")

        tone_score = round(tone_score, 2)

        report = {
            "duration": round(duration, 2),
            "avg_volume": round(avg_volume, 4),
            "voice_stability": round(voice_stability, 2),
            "speech_ratio": round(speech_ratio * 100, 2),
            "pace": round(pace, 2),
            "filler_count": filler_count
        }

        return tone_score, ", ".join(remarks), report

    except Exception as e:
        return 0, f"Tone analysis failed: {str(e)}", {
            "duration": 0,
            "avg_volume": 0,
            "voice_stability": 0,
            "speech_ratio": 0,
            "pace": 0,
            "filler_count": 0
        }


# ---------------- RESET AND SAVE ----------------
def reset_interview():
    st.session_state.start = False
    st.session_state.q = None
    st.session_state.q_obj = None
    st.session_state.count = 0
    st.session_state.used_q = []
    st.session_state.scores = []
    st.session_state.content_scores = []
    st.session_state.tone_scores = []
    st.session_state.answers = []
    st.session_state.start_time = None
    st.session_state.voice_answers = {}
    st.session_state.voice_files = {}
    st.session_state.tone_reports = {}


def save_answer_and_next(final_answer, audio_file=None):
    correct = st.session_state.q_obj.get("answer", "")
    keywords = st.session_state.q_obj.get("keywords", [])

    content_score, matched_keywords, content_status = evaluate_content(
        final_answer,
        correct,
        keywords
    )

    if audio_file:
        tone_score, tone_status, tone_report = analyze_tone(audio_file, final_answer)
    else:
        tone_score = 0
        tone_status = "No voice answer recorded"
        tone_report = {
            "duration": 0,
            "avg_volume": 0,
            "voice_stability": 0,
            "speech_ratio": 0,
            "pace": 0,
            "filler_count": 0
        }

    # Final score out of 5
    # 70% answer/content + 30% voice/tone
    final_score = round((content_score * 0.7) + (tone_score * 0.3), 2)

    st.session_state.content_scores.append(content_score)
    st.session_state.tone_scores.append(tone_score)
    st.session_state.scores.append(final_score)

    st.session_state.answers.append({
        "question": st.session_state.q,
        "user_answer": final_answer if final_answer.strip() else "No answer",
        "correct_answer": correct,
        "matched_keywords": matched_keywords,
        "content_status": content_status,
        "content_score": content_score,
        "tone_status": tone_status,
        "tone_score": tone_score,
        "tone_report": tone_report,
        "final_score": final_score,
        "audio_file": audio_file if audio_file else "No audio recorded"
    })

    st.session_state.q = None
    st.session_state.q_obj = None
    st.session_state.count += 1
    st.session_state.start_time = None

    st.rerun()


# ---------------- UI ----------------
st.markdown("<div class='title'>🤖 AI Interview Bot</div>", unsafe_allow_html=True)

mode = st.selectbox("Select Mode", ["Technical", "HR", "Rapid Fire"])
voice_mode = st.checkbox("🔊 Enable Voice Question Mode", value=True)

col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 Start Interview"):
        reset_interview()
        st.session_state.start = True
        st.rerun()

with col2:
    if st.button("🔄 Restart"):
        reset_interview()
        st.rerun()


# ---------------- MAIN FLOW ----------------
if st.session_state.start:

    # ---------------- FINAL RESULT ----------------
    if st.session_state.count >= MAX:
        total_score = sum(st.session_state.scores)
        avg_score = total_score / len(st.session_state.scores)

        total_content = sum(st.session_state.content_scores)
        avg_content = total_content / len(st.session_state.content_scores)

        total_tone = sum(st.session_state.tone_scores)
        avg_tone = total_tone / len(st.session_state.tone_scores)

        st.success("✅ Interview Completed")

        st.markdown("<div class='score-card'>", unsafe_allow_html=True)
        st.subheader(f"🏆 Total Final Score: {round(total_score, 2)}/{MAX * 5}")
        st.subheader(f"⭐ Average Final Score: {round(avg_score, 2)}/5")
        st.write(f"📘 Average Content Score: {round(avg_content, 2)}/5")
        st.write(f"🎤 Average Voice/Tone Score: {round(avg_tone, 2)}/5")
        st.markdown("</div>", unsafe_allow_html=True)

        if avg_score >= 4:
            st.success("Excellent Performance 🎉")
        elif avg_score >= 2.5:
            st.warning("Good Performance, but needs improvement 👍")
        else:
            st.error("Needs More Practice 📚")

        st.divider()
        st.subheader("📊 Detailed Answer Analysis")

        for i, item in enumerate(st.session_state.answers, 1):
            st.markdown(f"### Question {i}")

            st.write("❓ Question:", item["question"])
            st.write("🗣 Your Answer:", item["user_answer"])

            if item["correct_answer"]:
                st.write("✅ Correct Answer:", item["correct_answer"])
            else:
                st.write("✅ Evaluation Type: HR answer evaluated generally")

            st.write(
                "🔑 Matched Keywords:",
                ", ".join(item["matched_keywords"])
                if item["matched_keywords"]
                else "No keywords matched"
            )

            st.write("📘 Content Status:", item["content_status"])
            st.write("📘 Content Score:", f"{item['content_score']}/5")

            st.write("🎤 Voice/Tone Status:", item["tone_status"])
            st.write("🎤 Voice/Tone Score:", f"{item['tone_score']}/5")

            st.write("📁 Audio File:", item["audio_file"])

            tone_report = item["tone_report"]
            st.write("⏱ Duration:", tone_report["duration"], "seconds")
            st.write("🔊 Average Volume:", tone_report["avg_volume"])
            st.write("📈 Voice Stability:", tone_report["voice_stability"])
            st.write("🗣 Speech Ratio:", tone_report["speech_ratio"], "%")
            st.write("⚡ Speaking Pace:", tone_report["pace"], "words/minute")
            st.write("💬 Filler Words:", tone_report["filler_count"])

            st.write("⭐ Final Score:", f"{item['final_score']}/5")

            if item["final_score"] >= 4:
                st.success("Excellent / Confident")
            elif item["final_score"] >= 2.5:
                st.warning("Average / Needs improvement")
            else:
                st.error("Needs more practice")

            st.divider()

        if st.button("🔄 Start Again"):
            reset_interview()
            st.rerun()

        st.stop()

    # ---------------- GET QUESTION ----------------
    if st.session_state.q is None:
        q_obj = get_question(mode)
        st.session_state.q_obj = q_obj
        st.session_state.q = q_obj["question"]
        st.session_state.start_time = time.time()

    # ---------------- TIMER ----------------
    elapsed = int(time.time() - st.session_state.start_time)
    remaining = max(0, TIME_LIMIT - elapsed)

    mins = remaining // 60
    secs = remaining % 60

    st.markdown(
        f"<div class='timer'>⏳ Time Left: {mins:02d}:{secs:02d}</div>",
        unsafe_allow_html=True
    )

    # ---------------- QUESTION ----------------
    st.markdown(
        f"<div class='ai'>❓ Q{st.session_state.count + 1}: {st.session_state.q}</div>",
        unsafe_allow_html=True
    )

    if voice_mode:
        speak_question_once(st.session_state.q, st.session_state.count)

    if st.button("🔁 Replay Question Voice"):
        replay_question(st.session_state.q)

    st.divider()

    # ---------------- TYPED ANSWER ----------------
    st.subheader("✍️ Answer by Typing")

    typed_answer = st.text_area(
        "Type your answer here",
        key=f"text_answer_{st.session_state.count}",
        height=140
    )

    # ---------------- VOICE ANSWER ----------------
    st.markdown("<div class='voice-box'>", unsafe_allow_html=True)
    st.subheader("🎤 Or Answer by Voice")

    audio = mic_recorder(
        start_prompt="🎙 Start Recording",
        stop_prompt="⏹ Stop Recording",
        just_once=True,
        use_container_width=True,
        format="wav",
        key=f"voice_recorder_{st.session_state.count}"
    )

    current_audio_file = st.session_state.voice_files.get(
        st.session_state.count,
        None
    )

    current_voice_text = st.session_state.voice_answers.get(
        st.session_state.count,
        ""
    )

    # Save audio after stop recording
    if audio and "bytes" in audio:
        audio_bytes = audio["bytes"]

        if audio_bytes:
            audio_file = save_audio_file(
                audio_bytes,
                st.session_state.count + 1
            )

            voice_text = transcribe_audio(audio_file)
            tone_score, tone_status, tone_report = analyze_tone(
                audio_file,
                voice_text
            )

            st.session_state.voice_files[st.session_state.count] = audio_file
            st.session_state.voice_answers[st.session_state.count] = voice_text
            st.session_state.tone_reports[st.session_state.count] = {
                "tone_score": tone_score,
                "tone_status": tone_status,
                "tone_report": tone_report
            }

            st.rerun()

    current_audio_file = st.session_state.voice_files.get(
        st.session_state.count,
        None
    )

    current_voice_text = st.session_state.voice_answers.get(
        st.session_state.count,
        ""
    )

    current_tone_data = st.session_state.tone_reports.get(
        st.session_state.count,
        None
    )

    if current_audio_file:
        st.success("✅ Voice answer recorded and stored")
        st.write("📁 Saved Audio File:", current_audio_file)

        try:
            with open(current_audio_file, "rb") as f:
                st.audio(f.read(), format="audio/wav")
        except Exception:
            pass

    if current_voice_text:
        st.write("📝 Converted Voice Text:")
        st.info(current_voice_text)
    elif current_audio_file:
        st.warning("Audio is stored, but speech text was not recognized clearly.")
    else:
        st.info("Click Start Recording, speak your answer, then click Stop Recording.")

    if current_tone_data:
        st.subheader("🎤 Current Voice/Tone Score")
        st.write("Score:", f"{current_tone_data['tone_score']}/5")
        st.write("Status:", current_tone_data["tone_status"])

        report = current_tone_data["tone_report"]
        st.write("Duration:", report["duration"], "seconds")
        st.write("Average Volume:", report["avg_volume"])
        st.write("Voice Stability:", report["voice_stability"])
        st.write("Speech Ratio:", report["speech_ratio"], "%")
        st.write("Speaking Pace:", report["pace"], "words/minute")
        st.write("Filler Words:", report["filler_count"])

    st.markdown("</div>", unsafe_allow_html=True)

    # ---------------- FINAL ANSWER ----------------
    typed = typed_answer.strip()
    voice = current_voice_text.strip()

    if typed and voice:
        final_answer = typed + " " + voice
    elif typed:
        final_answer = typed
    elif voice:
        final_answer = voice
    else:
        final_answer = ""

    # ---------------- SUBMIT ----------------
    if st.button("✅ Submit Answer"):
        save_answer_and_next(final_answer, current_audio_file)