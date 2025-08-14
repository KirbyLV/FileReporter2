import os
import re
import json
import subprocess
from datetime import datetime
from pathlib import Path
from pymediainfo import MediaInfo
import ffmpeg

VIDEO_EXTS = {'.mp4', '.mov', '.mxf', '.mkv', '.avi', '.m4v', '.webm', '.wmv'}
AUDIO_EXTS = {'.wav', '.aiff', '.aif', '.mp3', '.m4a', '.flac', '.ogg'}
MEDIA_EXTS = VIDEO_EXTS | AUDIO_EXTS

VERSION_RE = re.compile(r"^(?P<stem>.*)_v(?P<ver>\d{1,3})$", re.IGNORECASE)


def is_media_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in MEDIA_EXTS


def safe_relpath(path: str, base: str) -> str:
    rp = os.path.relpath(path, base)
    if rp.startswith('..'):
        raise ValueError(f"Path {path} is outside base {base}")
    return rp


def file_times(path: str) -> dict:
    st = os.stat(path)
    created = datetime.fromtimestamp(getattr(st, 'st_birthtime', st.st_ctime))
    modified = datetime.fromtimestamp(st.st_mtime)
    return {'created_iso': created.isoformat(timespec='seconds'), 'modified_iso': modified.isoformat(timespec='seconds')}


def parse_version(filename: str) -> dict:
    name, _ext = os.path.splitext(filename)
    m = VERSION_RE.match(name)
    if m:
        return {'stem': m.group('stem'), 'version': int(m.group('ver'))}
    return {'stem': name, 'version': None}


def ffprobe_streams(path: str) -> dict:
    try:
        cmd = ['ffprobe', '-v', 'error', '-print_format', 'json', '-show_streams', '-show_format', path]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return json.loads(out.decode('utf-8'))
    except Exception:
        return {}


def analyze_media(path: str) -> dict:
    info = {'path': os.path.abspath(path), 'name': os.path.basename(path), 'ext': os.path.splitext(path)[1].lower(), 'size_bytes': os.path.getsize(path)}
    info.update(file_times(path))

    codec = width = height = fps = duration_ms = None
    has_audio = False

    try:
        mi = MediaInfo.parse(path)
    except Exception:
        mi = None

    if mi and mi.tracks:
        for t in mi.tracks:
            if t.track_type == 'Video' and not width:
                width = getattr(t, 'width', None)
                height = getattr(t, 'height', None)
                fps = getattr(t, 'frame_rate', None)
                codec = getattr(t, 'format', None) or getattr(t, 'codec_id', None)
                duration_ms = duration_ms or getattr(t, 'duration', None)
            if t.track_type == 'Audio':
                has_audio = True
                duration_ms = duration_ms or getattr(t, 'duration', None)

    if any(v is None for v in (codec, width, height, fps, duration_ms)):
        data = ffprobe_streams(path)
        streams = data.get('streams', [])
        fmt = data.get('format', {})
        for s in streams:
            if s.get('codec_type') == 'video':
                width = width or s.get('width')
                height = height or s.get('height')
                afr = s.get('avg_frame_rate') or s.get('r_frame_rate')
                if afr and afr != '0/0':
                    try:
                        num, den = afr.split('/')
                        if float(den) != 0:
                            fps = float(num) / float(den)
                    except Exception:
                        pass
                codec = codec or s.get('codec_name')
            if s.get('codec_type') == 'audio':
                has_audio = True
        if not duration_ms:
            try:
                duration_ms = float(fmt.get('duration')) * 1000 if fmt.get('duration') else None
            except Exception:
                duration_ms = None

    info.update({'codec': codec, 'width': width, 'height': height, 'fps': fps, 'duration_sec': (float(duration_ms) / 1000.0) if duration_ms else None, 'has_audio': has_audio})
    return info


def scan_repo(repo_dir: str):
    records = []
    for root, _dirs, files in os.walk(repo_dir):
        for f in files:
            p = os.path.join(root, f)
            if is_media_file(p):
                records.append(analyze_media(p))
    return records


def move_files(paths, dest_dir, base_dir):
    import shutil
    os.makedirs(dest_dir, exist_ok=True)
    moved = []
    for p in paths:
        abs_p = os.path.abspath(p)
        safe_relpath(abs_p, base_dir)
        target = os.path.join(dest_dir, os.path.basename(abs_p))
        shutil.move(abs_p, target)
        moved.append(target)
    return moved


def ffmpeg_proxy(src: str, res_factor: int = 2, alpha: bool = False) -> str:
    """Create a Hap (or Hap Alpha) proxy MOV scaled by 1/res_factor.
    Output: /repo/_proxies/<stem>_proxy{res_factor}.mov
    """
    base_repo = os.environ.get('REPO_DIR', '/repo')
    out_dir_path = Path(base_repo) / '_proxies'
    out_dir_path.mkdir(parents=True, exist_ok=True)

    name = Path(src).stem
    out_path = out_dir_path / f"{name}_proxy{res_factor}.mov"

    scale_expr = f"scale=iw/{res_factor}:ih/{res_factor}"
    cmd = ['ffmpeg', '-y', '-i', src, '-vf', scale_expr, '-c:v', 'hap']
    if alpha:
        cmd += ['-format', 'hap_alpha']
    cmd += ['-acodec', 'pcm_s16le', str(out_path)]

    subprocess.run(cmd, check=True, stderr=subprocess.PIPE)
    return str(out_path)


def ffmpeg_extract_audio(src: str, out_dir: str | None = None) -> str:
    """Create MOV with Hap black 16x16 @30fps + PCM16LE audio from file.
    Output: <stem>_hapaudio.mov (next to source unless out_dir specified).
    """
    p = Path(src)
    target_dir = Path(out_dir) if out_dir else p.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(target_dir / f"{p.stem}_hapaudio.mov")

    try:
        color = ffmpeg.input('color=c=black:s=16x16', f='lavfi')
        audio = ffmpeg.input(src)
        (ffmpeg
            .output(color, audio, out_path,
                    vcodec='hap', acodec='pcm_s16le', format='mov', vf='fps=30', ar=48000,
                    tune='stillimage', shortest=None)
            .global_args('-map', '0:v', '-map', '1:a')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        err = e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)
        raise RuntimeError(f"ffmpeg hapaudio failed for {src}: {err}")

    return out_path