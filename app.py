import os
import json, tempfile, shutil
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

    cfg = load_settings()
    content_type = request.headers.get('Content-Type', '')
    payload = {}

    try:
        if content_type.startswith('application/json'):
            payload = request.get_json(force=True, silent=False) or {}
        else:
            for key in ['sheet_name','repo_dir','quarantine_dir','show_media_dir','service_account_json']:
                if key in request.form and request.form[key].strip():
                    payload[key] = request.form[key].strip()
            if 'sa_json' in request.files and request.files['sa_json']:
                f = request.files['sa_json']
                os.makedirs(CONFIG_DIR, exist_ok=True)
                path = os.path.join(CONFIG_DIR, 'google-service-account.json')
                f.save(path)
                payload['service_account_json'] = path
    except Exception as e:
        return jsonify({'error': f'Invalid settings payload: {e}'}), 400

    for key in ['sheet_name','repo_dir','quarantine_dir','show_media_dir','service_account_json']:
        if payload.get(key):
            cfg[key] = payload[key]

    missing = [k for k in ['sheet_name','repo_dir','quarantine_dir','show_media_dir','service_account_json'] if not cfg.get(k)]
    if missing:
        return jsonify({'error': f"Missing fields: {', '.join(missing)}"}), 400

    # atomic write
    fd, tmp = tempfile.mkstemp(dir=CONFIG_DIR, prefix='settings.', suffix='.json')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)
    shutil.move(tmp, SETTINGS_PATH)

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
    try:
        repo_dir, _, _ = cfg_paths()
        cfg = load_settings()
        sa = cfg.get('service_account_json')
        sheet = cfg.get('sheet_name')

        if not sheet:
            return jsonify({'error': 'Missing sheet_name in settings.'}), 400
        if not sa or not os.path.isfile(sa):
            return jsonify({'error': f'Service account JSON not found at {sa}'}), 400

        records = scan_repo(repo_dir)

        # Try open by ID/URL or by name (see open_sheet patch below)
        ws = open_sheet(sa, sheet)

        sync_records(ws, records)
        return jsonify({'status': 'ok', 'count': len(records)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/move-async', methods=['POST'])
def api_move_async():
    repo_dir, quarantine_dir, show_media_dir = cfg_paths()
    payload = request.get_json(force=True) or {}
    paths = payload.get('paths') or []
    action = payload.get('action')

    if not paths:
        return jsonify({'error': 'No paths provided'}), 400
    if action not in ('quarantine', 'approve'):
        return jsonify({'error': 'Invalid action'}), 400

    dest = quarantine_dir if action == 'quarantine' else show_media_dir

    # compute total bytes (missing files count as 0)
    def fsize(p):
        try: return os.path.getsize(p)
        except Exception: return 0
    total_bytes = sum(fsize(p) for p in paths)

    job_id = f"move:{len(JOBS)+1}"
    JOBS[job_id] = {
        'status': 'queued',
        'moved': 0,              # files moved
        'total': len(paths),     # total files
        'bytes': 0,              # bytes moved so far
        'total_bytes': total_bytes,
        'errors': [],
        'action': action,
        'dest': dest,
        'current': None,         # currently moving file
        'current_pct': 0
    }

    def run():
        moved_count = 0
        bytes_moved = 0
        errors = []
        from media_utils import move_one_fast

        for p in paths:
            # progress callback for a single file
            def on_progress(bytes_so_far, pct):
                # bytes_so_far is per-file; convert to global-ish gauge:
                # We can't know previously moved bytes for this file, so we only
                # use pct for UI, and set 'current_pct'
                JOBS[job_id].update({
                    'status': 'running',
                    'current': p,
                    'current_pct': pct,
                    'moved': moved_count,
                    'bytes': bytes_moved
                })

            try:
                # update current file start
                JOBS[job_id].update({
                    'status': 'running',
                    'current': p,
                    'current_pct': 0,
                    'moved': moved_count,
                    'bytes': bytes_moved
                })

                # record size before move for global bytes tally
                size_before = fsize(p)
                move_one_fast(p, dest, on_progress=on_progress)

                moved_count += 1
                bytes_moved += size_before

                JOBS[job_id].update({
                    'status': 'running',
                    'current': None,
                    'current_pct': 100,
                    'moved': moved_count,
                    'bytes': bytes_moved
                })

            except Exception as e:
                errors.append(f"{p}: {e}")
                JOBS[job_id].update({
                    'status': 'running',
                    'current': None,
                    'current_pct': 0,
                    'moved': moved_count,
                    'bytes': bytes_moved,
                    'errors': errors
                })

        final_status = 'done_with_errors' if errors else 'done'
        JOBS[job_id].update({
            'status': final_status,
            'moved': moved_count,
            'bytes': bytes_moved,
            'errors': errors,
            'current': None,
            'current_pct': 0
        })

    executor.submit(run)
    return jsonify({'job_id': job_id}), 202


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8008, debug=True)