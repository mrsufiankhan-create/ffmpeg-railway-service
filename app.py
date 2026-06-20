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

def upload_to_drive(file_path, filename, folder_id, access_token):
    import json
    metadata = {"name": filename, "parents": [folder_id]}
    headers = {"Authorization": f"Bearer {access_token}"}
    with open(file_path, 'rb') as f:
        r = requests.post(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
            headers=headers,
            files={
                'metadata': ('metadata', json.dumps(metadata), 'application/json'),
                'file': (filename, f, 'video/mp4')
            }
        )
    return r.json()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/merge', methods=['POST'])
def merge():
    data = request.json
    clip_urls = data.get('clipUrls', [])
    voice_url = data.get('voiceUrl')
    elevenlabs_key = data.get('elevenLabsKey')
    pexels_key = data.get('pexelsKey')
    folder_id = data.get('folderId')
    access_token = data.get('accessToken')
    topic = data.get('topic', 'reel')

    if not clip_urls or not voice_url:
        return jsonify({"error": "Missing clipUrls or voiceUrl"}), 400

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download clips
        clip_paths = []
        for i, url in enumerate(clip_urls):
            path = os.path.join(tmpdir, f"clip_{i}.mp4")
            download_url(url, path)
            clip_paths.append(path)

        # Download voice from ElevenLabs
        voice_path = os.path.join(tmpdir, "voice.mp3")
        voice_headers = {"xi-api-key": elevenlabs_key} if elevenlabs_key else None
        download_url(voice_url, voice_path, headers=voice_headers)

        # Concat file
        concat_file = os.path.join(tmpdir, "concat.txt")
        with open(concat_file, 'w') as f:
            for cp in clip_paths:
                f.write(f"file '{cp}'\n")

        # Merge clips
        merged_path = os.path.join(tmpdir, "merged.mp4")
        subprocess.run([
            'ffmpeg', '-f', 'concat', '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            merged_path
        ], check=True)

        # Mix video + audio
        final_path = os.path.join(tmpdir, "final.mp4")
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

        # Upload to Drive if credentials provided
        if access_token and folder_id:
            output_name = topic.strip().replace(' ', '_') + '_reel.mp4'
            result = upload_to_drive(final_path, output_name, folder_id, access_token)
            return jsonify({
                "success": True,
                "fileId": result.get('id'),
                "fileName": output_name
            })
        else:
            return jsonify({"error": "No access token provided"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
