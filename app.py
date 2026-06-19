import os
import subprocess
import tempfile
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/merge', methods=['POST'])
def merge():
    files = request.files
    
    if 'voice' not in files:
        return jsonify({"error": "voice file required"}), 400
    
    clip_files = []
    i = 0
    while f'clip_{i}' in files:
        clip_files.append(files[f'clip_{i}'])
        i += 1
    
    if not clip_files:
        return jsonify({"error": "at least one clip required"}), 400

    with tempfile.TemporaryDirectory() as tmpdir:
        # Save clips
        clip_paths = []
        for idx, clip in enumerate(clip_files):
            path = os.path.join(tmpdir, f"clip_{idx}.mp4")
            clip.save(path)
            clip_paths.append(path)

        # Save voice
        voice_path = os.path.join(tmpdir, "voice.mp3")
        files['voice'].save(voice_path)

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

        return send_file(
            final_path,
            mimetype='video/mp4',
            as_attachment=True,
            download_name='final_reel.mp4'
        )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
