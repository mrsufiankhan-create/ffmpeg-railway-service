import os
import requests
import subprocess
import tempfile
from flask import Flask, request, jsonify

app = Flask(__name__)

GDRIVE_API = "https://www.googleapis.com/drive/v3"

def download_file(file_id, dest_path, access_token):
    url = f"{GDRIVE_API}/files/{file_id}?alt=media"
    headers = {"Authorization": f"Bearer {access_token}"}
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
    clip_ids = data.get('clipFileIds', [])
    voice_id = data.get('voiceFileId')
    folder_id = data.get('folderId')
    access_token = data.get('accessToken')
    output_name = data.get('outputName', 'final_reel.mp4')

    if not clip_ids or not voice_id or not access_token:
        return jsonify({"error": "Missing required fields"}), 400

    with tempfile.TemporaryDirectory() as tmpdir:
        clip_paths = []
        for i, cid in enumerate(clip_ids):
            path = os.path.join(tmpdir, f"clip_{i}.mp4")
            download_file(cid, path, access_token)
            clip_paths.append(path)

        voice_path = os.path.join(tmpdir, "voice.mp3")
        download_file(voice_id, voice_path, access_token)

        concat_file = os.path.join(tmpdir, "concat.txt")
        with open(concat_file, 'w') as f:
            for cp in clip_paths:
                f.write(f"file '{cp}'\n")

        merged_path = os.path.join(tmpdir, "merged.mp4")
        subprocess.run([
            'ffmpeg', '-f', 'concat', '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            merged_path
        ], check=True)

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

        result = upload_to_drive(final_path, output_name, folder_id, access_token)

        return jsonify({
            "success": True,
            "fileId": result.get('id'),
            "fileName": output_name
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
