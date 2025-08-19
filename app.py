import os
import json
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template, request, jsonify # type: ignore
from dotenv import load_dotenv # type: ignore

from media_utils import scan_repo, move_files, ffmpeg_proxy, ffmpeg_extract_audio
from sheets_sync import open_sheet, sync_records

load_dotenv()

# Defaults from env; can be overridden by settings.json via the Settings UI
ENV_REPO_DIR = os.environ.get('REPO_DIR', '/repo')
ENV_QUARANTINE_DIR = os.environ.get('QUARANTINE_DIR', '/repo_quarantine')
ENV_SHOW_MEDIA_DIR = os.environ.get('SHOW_MEDIA_DIR', '/repo_show')

CONFIG_DIR = os.environ.get('CONFIG_DIR', '/config')
SETTINGS_PATH = os.path.join(CONFIG_DIR, 'settings.json')
DEFAULT_SA_JSON = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON', os.path.join(CONFIG_DIR, 'google-service-account.json'))
DEFAULT_SHEET_NAME = os.environ.get('GOOGLE_SHEET_NAME', 'Media Repo Inventory')

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=4)
JOBS = {}


def load_settings():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            # Backup the bad file and continue with defaults
            try:
                import time, shutil
                ts = time.strftime('%Y%m%d-%H%M%S')
                backup = f"{SETTINGS_PATH}.bad-{ts}"
                shutil.copy2(SETTINGS_PATH, backup)
            except Exception:
                pass
            # You could also log the error here
    return {
        'sheet_name': DEFAULT_SHEET_NAME,
        'service_account_json': DEFAULT_SA_JSON,
        'repo_dir': ENV_REPO_DIR,
        'quarantine_dir': ENV_QUARANTINE_DIR,
        'show_media_dir': ENV_SHOW_MEDIA_DIR,
    }



def save_settings(data: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def cfg_paths():
    cfg = load_settings()
    return cfg['repo_dir'], cfg['quarantine_dir'], cfg['show_media_dir']


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/settings')
def settings_page():
    return render_template('settings.html')


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    if request.method == 'GET':
        return jsonify(load_settings())

    # Accept multipart form for file upload and text fields
    cfg = load_settings()

    # Text fields
    for key in ['sheet_name', 'repo_dir', 'quarantine_dir', 'show_media_dir']:
        if key in request.form and request.form[key].strip():
            cfg[key] = request.form[key].strip()

    # Upload of service account JSON
    if 'sa_json' in request.files and request.files['sa_json']:
        f = request.files['sa_json']
        path = os.path.join(CONFIG_DIR, 'google-service-account.json')
        f.save(path)
        cfg['service_account_json'] = path

    save_settings(cfg)
    return jsonify({'status': 'ok', 'settings': cfg})


@app.route('/api/scan')
def api_scan():
    try:
        repo_dir, _, _ = cfg_paths()
    except Exception as e:
        return jsonify({'error': f'Failed to load settings: {e}', 'records': []}), 500
    if not os.path.isdir(repo_dir):
        return jsonify({'error': f'Repo folder does not exist or is not a directory: {repo_dir}', 'records': []}), 400
    data = scan_repo(repo_dir)
    return jsonify({'records': data})


@app.route('/api/move', methods=['POST'])
def api_move():
    repo_dir, quarantine_dir, show_media_dir = cfg_paths()
    payload = request.get_json(force=True)
    paths = payload.get('paths', [])
    action = payload.get('action')  # 'quarantine' or 'approve'
    dest = quarantine_dir if action == 'quarantine' else show_media_dir
    try:
        moved = move_files(paths, dest, repo_dir)
        return jsonify({'moved': moved})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/proxy', methods=['POST'])
def api_proxy():
    payload = request.get_json(force=True)
    paths = payload.get('paths', [])
    res_factor = int(payload.get('res_factor', 2))
    alpha = bool(payload.get('alpha', False))

    job_id = f"proxy:{len(JOBS)+1}"
    JOBS[job_id] = {'status': 'queued', 'outputs': []}

    def run():
        outs = []
        for p in paths:
            try:
                o = ffmpeg_proxy(p, res_factor=res_factor, alpha=alpha)
                outs.append(o)
            except Exception as e:
                outs.append(f"ERROR:{p}:{e}")
        JOBS[job_id] = {'status': 'done', 'outputs': outs}

    executor.submit(run)
    return jsonify({'job_id': job_id})


@app.route('/api/extract-audio', methods=['POST'])
def api_extract_audio():
    payload = request.get_json(force=True)
    paths = payload.get('paths', [])
    out_dir = payload.get('out_dir')

    job_id = f"audio:{len(JOBS)+1}"
    JOBS[job_id] = {'status': 'queued', 'outputs': []}

    def run():
        outs = []
        for p in paths:
            try:
                o = ffmpeg_extract_audio(p, out_dir)
                outs.append(o)
            except Exception as e:
                outs.append(f"ERROR:{p}:{e}")
        JOBS[job_id] = {'status': 'done', 'outputs': outs}

    executor.submit(run)
    return jsonify({'job_id': job_id})


@app.route('/api/jobs/<job_id>')
def api_job(job_id):
    return jsonify(JOBS.get(job_id, {'status': 'unknown'}))


@app.route('/api/sync-sheets', methods=['POST'])
def api_sync_sheets():
    repo_dir, _, _ = cfg_paths()
    records = scan_repo(repo_dir)
    try:
        cfg = load_settings()
        ws = open_sheet(cfg['service_account_json'], cfg['sheet_name'])
        sync_records(ws, records)
        return jsonify({'status': 'ok', 'count': len(records)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8008, debug=True)