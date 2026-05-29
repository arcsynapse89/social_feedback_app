import streamlit as st
from streamlit.components.v1 import html
from pathlib import Path
from datetime import datetime
import os

# ==========================================================
# SOCIAL FEEDBACK TRAINER - STREAMLIT CLOUD VERSION
#
# No Flask.
# No local upload server.
# Uses:
# - Browser MediaRecorder for camera + mic
# - Streamlit file_uploader to save recordings into tiles
# ==========================================================

BASE_DIR = Path(__file__).parent
SAVE_DIR = BASE_DIR / "recordings"
SAVE_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Social Feedback Trainer", layout="wide")

st.title("🎤 Social Feedback Trainer")
st.caption(f"Temporary save folder: {SAVE_DIR}")

st.warning(
    "Streamlit Cloud storage is temporary. Saved recordings may disappear when the app restarts."
)

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

safe_prompt = (
    prompt.replace("\\", "\\\\")
    .replace("`", "\\`")
    .replace("$", "\\$")
)

left, right = st.columns([1, 1])

with left:
    st.subheader("📹 Internal Camera + Microphone Recorder")

    recorder_html = f"""
    <div style="font-family: Arial, sans-serif;">
        <h3 style="color:red;">Prompt: {safe_prompt}</h3>

        <canvas id="recordCanvas" width="640" height="360"
            style="border:2px solid #00FF00; border-radius:10px;"></canvas>

        <video id="hiddenVideo" autoplay muted playsinline style="display:none;"></video>

        <br><br>

        <button onclick="startRecording()">▶ Start Recording</button>
        <button onclick="stopRecording()">■ Stop Recording</button>

        <p id="status" style="color:red; font-weight:bold;">Ready.</p>

        <video id="playback" width="640" height="360" controls
            style="border:2px solid #00FF00; border-radius:10px;"></video>

        <br><br>

        <a id="downloadLink"
           style="display:none; font-size:18px; color:#00FF00; font-weight:bold;">
           ⬇ Download Recording
        </a>
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
                ctx.strokeText(line, x, y);
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
        const status = document.getElementById("status");
        const downloadLink = document.getElementById("downloadLink");

        downloadLink.style.display = "none";
        status.innerText = "Requesting camera and microphone...";
        status.style.color = "orange";

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

        function drawFrame() {{
            ctx.drawImage(hiddenVideo, 0, 0, canvas.width, canvas.height);

            ctx.fillStyle = "rgba(0,0,0,0.75)";
            ctx.fillRect(0, 0, canvas.width, 70);

            ctx.font = "bold 20px Arial";
            ctx.strokeStyle = "black";
            ctx.lineWidth = 4;
            ctx.fillStyle = "#00FF00";

            wrapText(ctx, promptText, 15, 30, 610, 24);

            ctx.fillStyle = "red";
            ctx.beginPath();
            ctx.arc(610, 35, 8, 0, 2 * Math.PI);
            ctx.fill();

            drawTimer = requestAnimationFrame(drawFrame);
        }}

        drawFrame();

        canvasStream = canvas.captureStream(30);

        combinedStream = new MediaStream([
            ...canvasStream.getVideoTracks(),
            ...cameraStream.getAudioTracks()
        ]);

        let recorderOptions = {{
            mimeType: "video/webm",
            audioBitsPerSecond: 128000,
            videoBitsPerSecond: 2500000
        }};

        if (!MediaRecorder.isTypeSupported(recorderOptions.mimeType)) {{
            recorderOptions = {{}};
        }}

        mediaRecorder = new MediaRecorder(combinedStream, recorderOptions);

        mediaRecorder.ondataavailable = function(event) {{
            if (event.data.size > 0) {{
                recordedChunks.push(event.data);
            }}
        }};

        mediaRecorder.onstop = function() {{
            finalBlob = new Blob(recordedChunks, {{ type: "video/webm" }});
            const url = URL.createObjectURL(finalBlob);

            document.getElementById("playback").src = url;

            downloadLink.href = url;
            downloadLink.download = "practice_recording.webm";
            downloadLink.style.display = "inline-block";

            status.innerText =
                "Recording stopped. Download it, then upload it below to save as a tile.";
            status.style.color = "red";
            status.style.fontWeight = "bold";
        }};

        mediaRecorder.start();

        status.innerText = "Recording...";
        status.style.color = "lime";
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
    </script>
    """

    html(recorder_html, height=950)

with right:
    st.subheader("💾 Save Recording to Tile Library")

    uploaded_video = st.file_uploader(
        "Upload the downloaded recording",
        type=["webm", "mp4", "mov"],
    )

    if uploaded_video is not None:
        st.video(uploaded_video)

        if st.button("Save Uploaded Recording"):
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            ext = uploaded_video.name.split(".")[-1].lower()

            base_name = f"practice_{timestamp}"
            video_filename = f"{base_name}.{ext}"

            video_path = SAVE_DIR / video_filename
            metadata_path = SAVE_DIR / f"{base_name}.txt"
            notes_path = SAVE_DIR / f"{base_name}_notes.txt"
            scores_path = SAVE_DIR / f"{base_name}_scores.txt"

            with open(video_path, "wb") as f:
                f.write(uploaded_video.getbuffer())

            with open(metadata_path, "w", encoding="utf-8") as f:
                f.write(f"Prompt: {prompt}\n")
                f.write(f"Date: {timestamp}\n")
                f.write(f"File: {video_filename}\n")
                f.write("Saved using Streamlit file_uploader\n")

            notes_path.write_text("", encoding="utf-8")

            scores_path.write_text(
                "Eye contact: \n"
                "Facial expression: \n"
                "Voice energy: \n"
                "Posture: \n",
                encoding="utf-8",
            )

            st.success("Recording saved to tile library.")
            st.rerun()

    st.subheader("🎬 Latest Saved Video")

    videos = sorted(
        [
            f.name for f in SAVE_DIR.iterdir()
            if f.suffix.lower() in [".webm", ".mp4", ".mov"]
        ],
        reverse=True,
    )

    if videos:
        st.video(str(SAVE_DIR / videos[0]))
    else:
        st.write("No saved videos yet.")

st.divider()
st.header("📁 Saved Recording Tiles")

videos = sorted(
    [
        f.name for f in SAVE_DIR.iterdir()
        if f.suffix.lower() in [".webm", ".mp4", ".mov"]
    ],
    reverse=True,
)

if not videos:
    st.write("No recordings saved yet.")
else:
    cols = st.columns(3)

    for i, video in enumerate(videos):
        video_path = SAVE_DIR / video
        base_name = video_path.stem

        metadata_path = SAVE_DIR / f"{base_name}.txt"
        notes_path = SAVE_DIR / f"{base_name}_notes.txt"
        scores_path = SAVE_DIR / f"{base_name}_scores.txt"

        with cols[i % 3]:
            with st.container(border=True):
                st.subheader(video)

                if metadata_path.exists():
                    st.caption(metadata_path.read_text(encoding="utf-8"))

                st.video(str(video_path))

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
                if notes_path.exists():
                    existing_notes = notes_path.read_text(encoding="utf-8")

                new_notes = st.text_area(
                    "Notes for this recording",
                    value=existing_notes,
                    key=f"notes_{video}",
                    height=100,
                )

                if st.button("Save Notes", key=f"save_notes_{video}"):
                    notes_path.write_text(new_notes, encoding="utf-8")
                    st.success("Notes saved.")

                st.markdown("### ✅ Self Review")

                eye_contact = st.slider("Eye contact", 1, 10, 5, key=f"eye_{video}")
                facial_expression = st.slider("Facial expression", 1, 10, 5, key=f"face_{video}")
                voice_energy = st.slider("Voice energy", 1, 10, 5, key=f"voice_{video}")
                posture = st.slider("Posture", 1, 10, 5, key=f"posture_{video}")

                if st.button("Save Scores", key=f"save_scores_{video}"):
                    scores_path.write_text(
                        f"Eye contact: {eye_contact}/10\n"
                        f"Facial expression: {facial_expression}/10\n"
                        f"Voice energy: {voice_energy}/10\n"
                        f"Posture: {posture}/10\n",
                        encoding="utf-8",
                    )
                    st.success("Scores saved.")

                if scores_path.exists():
                    st.caption(scores_path.read_text(encoding="utf-8"))

                if st.button("🗑 Delete Recording", key=f"delete_{video}"):
                    for path in [
                        video_path,
                        metadata_path,
                        notes_path,
                        scores_path,
                    ]:
                        if path.exists():
                            path.unlink()

                    st.warning("Recording deleted.")
                    st.rerun()
