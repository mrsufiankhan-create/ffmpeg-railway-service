import os
import requests
import subprocess
import tempfile
from flask import Flask, request, jsonify

app = Flask(__name__)

def download_url(url, dest_path, headers=None):
    r = requests.get(url, headers=headers, stream=True)
    with open(dest_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/merge', methods=['POST'])
def merge():
    data = request.get_json(force=True)
    clip_urls = data.get('clipUrls', [])
    script = data.get('script')
    elevenlabs_key = data.get('elevenLabsKey')
    topic = data.get('topic', 'football')

    if not clip_urls or not script or not elevenlabs_key:
        return jsonify({"error": "Missing required fields"}), 400

    with tempfile.TemporaryDirectory() as tmpdir:
        clip_paths = []
        for i, url in enumerate(clip_urls):
            path = os.path.join(tmpdir, f"clip_{i}.mp4")
            download_url(url, path)
            clip_paths.append(path)

        voice_path = os.path.join(tmpdir, "voice.mp3")
        voice_id = "pNInz6obpgDQGcFmaJgB"
        tts_url = "https://api.elevenlabs.io/v1/text-to-speech/" + voice_id
        tts_response = requests.post(
            tts_url,
            headers={
                "xi-api-key": elevenlabs_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            },
            json={
                "text": script,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            }
        )

        if tts_response.status_code != 200:
            return jsonify({
                "error": "ElevenLabs failed",
                "status": tts_response.status_code,
                "detail": tts_response.text
            }), 500

        with open(voice_path, 'wb') as f:
            f.write(tts_response.content)

        concat_file = os.path.join(tmpdir, "concat.txt")
        with open(concat_file, 'w') as f:
            for cp in clip_paths:
                f.write(f"file '{cp}'\n")

        merged_path = os.path.join(tmpdir, "merged.mp4")
        subprocess.run([
            'ffmpeg', '-f', 'concat', '-safe', '0',
            '-i', concat_file, '-c', 'copy', merged_path
        ], check=True)

        output_name = topic.strip().replace(' ', '_') + '.mp4'
        final_path = os.path.join(tmpdir, output_name)
        subprocess.run([
            'ffmpeg',
            '-i', merged_path,
            '-i', voice_path,
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-shortest',
            final_path
        ], check=True)

        import base64
        with open(final_path, 'rb') as f:
            video_b64 = base64.b64encode(f.read()).decode('utf-8')

        return jsonify({
            "success": True,
            "fileName": output_name,
            "videoBase64": video_b64
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
