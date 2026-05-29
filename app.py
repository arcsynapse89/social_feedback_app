# ==========================================================
# SOCIAL FEEDBACK TRAINER
# ==========================================================
#
# Purpose:
# Record webcam + microphone practice sessions entirely
# inside the browser and save them into a local library.
#
# Architecture:
#
# Browser Camera + Microphone
#          ↓
#      MediaRecorder
#          ↓
#     Flask Upload API
#          ↓
#      recordings/
#          ↓
#   Streamlit Video Tiles
#
# ==========================================================

import streamlit as st
import os
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from streamlit.components.v1 import html

SAVE_DIR = os.path.abspath("recordings")
os.makedirs(SAVE_DIR, exist_ok=True)

UPLOAD_PORT = 8765

api = Flask(__name__)
CORS(api)


def clean_prompt_for_js(text):
    return (
        text.replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("$", "\\$")
    )


# ==========================================================
# FLASK UPLOAD ENDPOINT
#
# Receives the completed video recording from the browser.
#
# Browser:
#     MediaRecorder Blob
#          ↓
#      POST /upload
#          ↓
#       Save Video
#
# Also creates:
# - Metadata file
# - Notes file
# - Self-review score file
#
# ==========================================================


@api.route("/upload", methods=["POST"])
def upload_recording():
    video = request.files.get("video")
    prompt = request.form.get("prompt", "No prompt")

    if video is None:
        return jsonify({"error": "No video received"}), 400

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    base_name = f"practice_{timestamp}"

    video_filename = f"{base_name}.webm"
    metadata_filename = f"{base_name}.txt"
    notes_filename = f"{base_name}_notes.txt"
    scores_filename = f"{base_name}_scores.txt"

    video_path = os.path.join(SAVE_DIR, video_filename)
    metadata_path = os.path.join(SAVE_DIR, metadata_filename)
    notes_path = os.path.join(SAVE_DIR, notes_filename)
    scores_path = os.path.join(SAVE_DIR, scores_filename)

    video.save(video_path)

    with open(metadata_path, "w", encoding="utf-8") as f:
        f.write(f"Prompt: {prompt}\n")
        f.write(f"Date: {timestamp}\n")
        f.write(f"File: {video_filename}\n")
        f.write("Format: webm browser recording with prompt overlay\n")
        f.write("Render loop: requestAnimationFrame\n")
        f.write("Canvas capture: 30 FPS\n")

    with open(notes_path, "w", encoding="utf-8") as f:
        f.write("")

    with open(scores_path, "w", encoding="utf-8") as f:
        f.write("Eye contact: \n")
        f.write("Facial expression: \n")
        f.write("Voice energy: \n")
        f.write("Posture: \n")

    return jsonify({"status": "saved", "file": video_filename})


def run_api():
    api.run(host="127.0.0.1", port=UPLOAD_PORT, debug=False, use_reloader=False)


if "api_started" not in st.session_state:
    threading.Thread(target=run_api, daemon=True).start()
    st.session_state.api_started = True


st.set_page_config(page_title="Social Feedback Trainer", layout="wide")

st.title("🎤 Social Feedback Trainer")
st.caption(f"Saving recordings to: {SAVE_DIR}")

prompt = st.selectbox(
    "Choose your practice prompt",
    [
        "Introduce yourself for 30 seconds",
        "Explain what you did today",
        "Answer: What are your strengths?",
        "Practise a calm smile and neutral face",
        "Explain a project you are working on",
        "Practise a job interview answer",
        "Tell a short story with more expression",
    ],
)

st.info(prompt)
safe_prompt = clean_prompt_for_js(prompt)

left, right = st.columns([1, 1])

with left:
    st.subheader("📹 Internal Camera + Microphone Recorder")

    recorder_html = f"""
    <div style="font-family: Arial, sans-serif;">
     <h3 style="color:red;">
    Prompt: {safe_prompt}
    </h3>

      <canvas id="recordCanvas" width="640" height="360"
              style="border:2px solid #00FF00; border-radius:10px;"></canvas>

      <video id="hiddenVideo" autoplay muted playsinline style="display:none;"></video>

      <br><br>

      <button onclick="startRecording()">▶ Start Recording</button>
      <button onclick="stopRecording()">■ Stop Recording</button>
      <button onclick="saveRecording()">💾 Save Recording to Tiles</button>

      <p id="status" style="color:red;">
        Ready.
      </p>

      <video id="playback" width="640" height="360" controls
             style="border:2px solid #00FF00; border-radius:10px;"></video>
    </div>

    <script>
    let mediaRecorder;
    let recordedChunks = [];
    let cameraStream;
    let canvasStream;
    let combinedStream;
    let finalBlob = null;
    let drawTimer = null;

    const promptText = `{safe_prompt}`;

    function wrapText(ctx, text, x, y, maxWidth, lineHeight) {{
        const words = text.split(" ");
        let line = "";

        for (let n = 0; n < words.length; n++) {{
            const testLine = line + words[n] + " ";
            const testWidth = ctx.measureText(testLine).width;

            if (testWidth > maxWidth && n > 0) {{
                ctx.fillText(line, x, y);
                line = words[n] + " ";
                y += lineHeight;
            }} else {{
                line = testLine;
            }}
        }}

        ctx.strokeText(line, x, y);
        ctx.fillText(line, x, y);
    }}

    async function startRecording() {{
        recordedChunks = [];
        finalBlob = null;

        const canvas = document.getElementById("recordCanvas");
        const ctx = canvas.getContext("2d");
        const hiddenVideo = document.getElementById("hiddenVideo");

        document.getElementById("status").innerText = "Requesting camera and microphone...";

        // ==========================================================
        // CAMERA + MICROPHONE ACQUISITION
        //
        // Requests webcam and microphone access from the browser.
        //
        // Why browser-side?
        //
        // Browser recording is dramatically more reliable than
        // trying to capture video/audio in Python.
        //
        // =========================================================
        
        
        cameraStream = await navigator.mediaDevices.getUserMedia({{
            video: {{
                width: 640,
                height: 360
            }},
            audio: {{
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: false,
                channelCount: 1,
                sampleRate: 48000
            }}
        }});

        hiddenVideo.srcObject = cameraStream;
        await hiddenVideo.play();

        // ==========================================================
        // PROMPT OVERLAY
        //
        // Draws:
        //
        // Camera Feed
        // +
        // Prompt Text
        // +
        // Recording Indicator
        //
        // onto a canvas.
        //
        // The canvas is what gets recorded,
        // meaning the prompt becomes permanently embedded
        // into the final video.
        //
        // ==========================================================





        function drawFrame() {{
            ctx.drawImage(
                hiddenVideo,
                0,
                0,
                canvas.width,
                canvas.height
            );

            ctx.fillStyle = "rgba(0,0,0,0.75)";
            ctx.fillRect(0, 0, canvas.width, 70);

            ctx.font = "bold 20px Arial";

            ctx.strokeStyle = "black";
            ctx.lineWidth = 4;

            ctx.fillStyle = "#00FF00";

            wrapText(
                ctx,
                promptText,
                15,
                30,
                610,
                24
            );

            ctx.fillStyle = "red";
            ctx.beginPath();
            ctx.arc(
                610,
                35,
                8,
                0,
                2 * Math.PI
            );
            ctx.fill();

            drawTimer = requestAnimationFrame(drawFrame);
        }}

        drawFrame();

        canvasStream = canvas.captureStream(30);

        const audioTracks = cameraStream.getAudioTracks();
        const videoTracks = canvasStream.getVideoTracks();

        combinedStream = new MediaStream([
            ...videoTracks,
            ...audioTracks
        ]);

        let recorderOptions = {{
            mimeType: "video/webm",
            audioBitsPerSecond: 128000,
            videoBitsPerSecond: 2500000
        }};

        if (!MediaRecorder.isTypeSupported(recorderOptions.mimeType)) {{
            recorderOptions = {{}};
        }}
        
        // ==========================================================
        // MEDIARECORDER
        //
        // Combines:
        //
        // Canvas Video Track
        // +
        // Microphone Audio Track
        //
        // into a single WEBM recording.
        //
        // Similar concept to Zoom / Teams / Google Meet.
        //
        // ==========================================================




        mediaRecorder = new MediaRecorder(
            combinedStream,
            recorderOptions
        );

        mediaRecorder.ondataavailable = function(event) {{
            if (event.data.size > 0) {{
                recordedChunks.push(event.data);
            }}
        }};

        mediaRecorder.onstop = function() {{
            finalBlob = new Blob(recordedChunks, {{
                type: "video/webm"
            }});

            const url = URL.createObjectURL(finalBlob);
            document.getElementById("playback").src = url;


        const status = document.getElementById("status");

        status.innerText =
            "Recording stopped. Preview ready. Click Save Recording to Tiles.";
                
        status.style.color = "red";
        status.style.fontWeight = "bold";
        }};





        mediaRecorder.start();
        document.getElementById("status").innerText = "Recording...";
    }}

    function stopRecording() {{
        if (mediaRecorder && mediaRecorder.state !== "inactive") {{
            mediaRecorder.stop();
        }}

        if (drawTimer) {{
            cancelAnimationFrame(drawTimer);
            drawTimer = null;
        }}

        if (cameraStream) {{
            cameraStream.getTracks().forEach(track => track.stop());
        }}

        if (canvasStream) {{
            canvasStream.getTracks().forEach(track => track.stop());
        }}

        if (combinedStream) {{
            combinedStream.getTracks().forEach(track => track.stop());
        }}
    }}

    async function saveRecording() {{
        if (!finalBlob) {{
            document.getElementById("status").innerText =
                "No recording to save yet.";
            return;
        }}

        const formData = new FormData();
        formData.append("video", finalBlob, "recording.webm");
        formData.append("prompt", promptText);

        document.getElementById("status").innerText = "Saving...";

        try {{
            const response = await fetch("http://127.0.0.1:{UPLOAD_PORT}/upload", {{
                method: "POST",
                body: formData
            }});

            const result = await response.json();

            if (response.ok) {{
                document.getElementById("status").innerText =
                    "Saved: " + result.file + ". Updating library...";

                setTimeout(() => {{
                    window.parent.location.reload();
                }}, 1000);
            }} else {{
                document.getElementById("status").innerText =
                    "Save failed: " + result.error;
            }}
        }} catch (error) {{
            document.getElementById("status").innerText =
                "Save failed: " + error;
        }}
    }}
    </script>
    """

    html(recorder_html, height=900)

with right:
    st.subheader("🎬 Latest Saved Video")

    videos = sorted(
        [
            f for f in os.listdir(SAVE_DIR)
            if f.lower().endswith((".webm", ".mp4", ".mov"))
        ],
        reverse=True,
    )

    if videos:
        st.video(os.path.join(SAVE_DIR, videos[0]))
    else:
        st.write("No saved videos yet.")

    if st.button("🔄 Refresh Library"):
        st.rerun()
       
       
       
st.divider()
st.header("📁 Saved Recording Tiles")



videos = sorted(
    [
        f for f in os.listdir(SAVE_DIR)
        if f.lower().endswith((".webm", ".mp4", ".mov"))
    ],
    reverse=True,
)

if not videos:
    st.write("No recordings saved yet.")

else:
    cols = st.columns(3)

    for i, video in enumerate(videos):
        video_path = os.path.join(SAVE_DIR, video)
        base_name = os.path.splitext(video)[0]

        metadata_path = os.path.join(SAVE_DIR, f"{base_name}.txt")
        notes_path = os.path.join(SAVE_DIR, f"{base_name}_notes.txt")
        scores_path = os.path.join(SAVE_DIR, f"{base_name}_scores.txt")

        with cols[i % 3]:
            with st.container(border=True):
                st.subheader(video)

                if os.path.exists(metadata_path):
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        st.caption(f.read())

                st.video(video_path)

                with open(video_path, "rb") as video_file:
                    st.download_button(
                        label="⬇ Download Video",
                        data=video_file,
                        file_name=video,
                        mime="video/webm",
                        key=f"download_{video}",
                    )

                st.markdown("### 📝 Notes")

                existing_notes = ""
                if os.path.exists(notes_path):
                    with open(notes_path, "r", encoding="utf-8") as f:
                        existing_notes = f.read()

                new_notes = st.text_area(
                    "Notes for this recording",
                    value=existing_notes,
                    key=f"notes_{video}",
                    height=100,
                )

                if st.button("Save Notes", key=f"save_notes_{video}"):
                    with open(notes_path, "w", encoding="utf-8") as f:
                        f.write(new_notes)
                    st.success("Notes saved.")

                st.markdown("### ✅ Self Review")

                eye_contact = st.slider("Eye contact", 1, 10, 5, key=f"eye_{video}")
                facial_expression = st.slider("Facial expression", 1, 10, 5, key=f"face_{video}")
                voice_energy = st.slider("Voice energy", 1, 10, 5, key=f"voice_{video}")
                posture = st.slider("Posture", 1, 10, 5, key=f"posture_{video}")

                if st.button("Save Scores", key=f"save_scores_{video}"):
                    with open(scores_path, "w", encoding="utf-8") as f:
                        f.write(f"Eye contact: {eye_contact}/10\n")
                        f.write(f"Facial expression: {facial_expression}/10\n")
                        f.write(f"Voice energy: {voice_energy}/10\n")
                        f.write(f"Posture: {posture}/10\n")
                    st.success("Scores saved.")

                if os.path.exists(scores_path):
                    with open(scores_path, "r", encoding="utf-8") as f:
                        st.caption(f.read())

                if st.button("🗑 Delete Recording", key=f"delete_{video}"):
                    for path in [
                        video_path,
                        metadata_path,
                        notes_path,
                        scores_path,
                    ]:
                        if os.path.exists(path):
                            os.remove(path)

                    st.warning("Recording deleted.")
                    st.rerun()
                    
                    
                    # ==========================================================
# PERSONAL NOTES
#
# User observations after reviewing recording.
#
# Example:
#
# - Need more eye contact
# - Too many filler words
# - Smile looked forced
# - Better vocal energy
#
# ==========================================================

# ==========================================================
# SELF REVIEW SCORECARD
#
# User rates performance from 1-10.
#
# Future AI version:
#
# Automatically estimate:
# - Eye contact
# - Facial expression
# - Voice energy
# - Posture
#
# ==========================================================





# ==========================================================
# SAVED RECORDING TILE LIBRARY
#
# Each tile contains:
#
# - Video Preview
# - Download Button
# - Notes
# - Self Review Scores
# - Delete Button
#
# Future upgrades:
#
# - Whisper transcription
# - AI analysis
# - Smile detection
# - Eye contact scoring
# - Speaking pace analysis
#
# ==========================================================




