import requests
import os
import subprocess
from flask import Flask, request, jsonify, send_file, render_template
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

API_URL = "https://router.huggingface.co/hf-inference/models/openai/whisper-large-v3"
API_KEY = os.getenv("HF_API_KEY")


def extract_audio(video_path, audio_path):
    subprocess.run([
        "ffmpeg", "-i", video_path,
        "-q:a", "0", "-map", "a",
        audio_path, "-y"
    ])


def transcribe(audio_path):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "audio/mpeg"
    }
    params = {"return_timestamps": "word"}
    with open(audio_path, "rb") as f:
        audio_data = f.read()
    response = requests.post(API_URL, headers=headers, params=params, data=audio_data)
    return response.json()["chunks"]


def make_srt(words, group_size=5, position="bottom"):
    alignment = {
        "bottom": "\\an2",
        "center": "\\an5",
        "top": "\\an8"
    }

    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    srt = ""
    index = 1
    for i in range(0, len(words), group_size):
        group = words[i:i+group_size]
        text = "".join(w["text"] for w in group).strip()
        start = group[0]["timestamp"][0]
        end = group[-1]["timestamp"][1]
        if end is None:
            end = start + 2.0
        pos_tag = alignment.get(position, "\\an2")
        srt += f"{index}\n{format_time(start)} --> {format_time(end)}\n{{{pos_tag}}}{text}\n\n"
        index += 1

    return srt


def burn_captions(video_path, srt_path, output_path):
    subprocess.run([
        "ffmpeg", "-i", video_path,
        "-vf", f"subtitles={srt_path}:force_style='FontName=Arial,FontSize=14,Bold=1,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Shadow=1'",
        output_path, "-y"
    ])


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    video = request.files["video"]
    group_size = int(request.form.get("group_size", 5))
    position = request.form.get("position", "bottom")

    video.save("input_video.mp4")

    print("Extracting audio...")
    extract_audio("input_video.mp4", "audio.mp3")

    print("Transcribing...")
    words = transcribe("audio.mp3")

    print("Generating .srt...")
    srt = make_srt(words, group_size=group_size, position=position)
    with open("captions.srt", "w", encoding="utf-8") as f:
        f.write(srt)

    print("Burning captions...")
    burn_captions("input_video.mp4", "captions.srt", "output.mp4")

    print("Done!")
    return jsonify({"status": "done"})


@app.route("/get-srt")
def get_srt():
    return send_file("captions.srt", as_attachment=False)


@app.route("/get-video")
def get_video():
    return send_file("output.mp4", as_attachment=True, download_name="captioned_video.mp4")


if __name__ == "__main__":
    app.run(debug=True)