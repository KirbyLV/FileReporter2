import os
import re
import json
import subprocess, shutil, platform, shlex
from datetime import datetime
from pathlib import Path
from pymediainfo import MediaInfo
import ffmpeg
import errno

VIDEO_EXTS = {'.mp4', '.mov', '.mxf', '.mkv', '.avi', '.m4v', '.webm', '.wmv', '.png'}
AUDIO_EXTS = {'.wav', '.aiff', '.aif', '.mp3', '.m4a', '.flac', '.ogg'}
MEDIA_EXTS = VIDEO_EXTS | AUDIO_EXTS

VERSION_RE = re.compile(r"^(?P<stem>.*)_v(?P<ver>\d{1,3})$", re.IGNORECASE)

IGNORED_BASENAMES = {'.DS_Store', 'Thumbs.db'}
def is_hidden_path(path: str) -> bool:
    b = os.path.basename(path)
    # skip dotfiles (.foo) and AppleDouble (._foo)
    return b.startswith('.') or b.startswith('._') or b in IGNORED_BASENAMES


def is_media_file(path: str) -> bool:
    if is_hidden_path(path):
        return False
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


def analyze_media(path: str) -> dict | None:
    # Skip hidden/sidecar files early
    if is_hidden_path(path):
        return None
    try:
        size = os.path.getsize(path)
        abspath = os.path.abspath(path)
    except OSError:
        # unreadable or special file; skip
        return None

    info = {
        'path': abspath,
        'name': os.path.basename(path),
        'ext': os.path.splitext(path)[1].lower(),
        'size_bytes': size
    }
    try:
        info.update(file_times(path))
    except OSError:
        # if stat fails, still include minimal info
        info.update({'created_iso': None, 'modified_iso': None})

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
            if not is_media_file(p):
                continue
            rec = analyze_media(p)
            if rec is not None:
                records.append(rec)
    return records


def _same_device(path_a: str, path_b: str) -> bool:
    try:
        return os.stat(path_a).st_dev == os.stat(path_b).st_dev
    except FileNotFoundError:
        # if dest dir not yet created, compare against its parent
        parent = os.path.dirname(path_b.rstrip(os.sep)) or "/"
        try:
            return os.stat(path_a).st_dev == os.stat(parent).st_dev
        except Exception:
            return False

def _ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def _unique_dest(dst_dir: str, basename: str) -> str:
    root, ext = os.path.splitext(basename)
    candidate = os.path.join(dst_dir, basename)
    i = 1
    while os.path.exists(candidate):
        candidate = os.path.join(dst_dir, f"{root} ({i}){ext}")
        i += 1
    return candidate


def _rename_fast(src: str, dst_dir: str) -> str:
    _ensure_dir(dst_dir)
    dst = _unique_dest(dst_dir, os.path.basename(src))
    os.replace(src, dst)
    return dst

def _have(cmd: str) -> bool:
    from shutil import which
    return which(cmd) is not None

def _rsync_move(src: str, dst_dir: str, on_progress=None) -> str:
    """Use rsync for cross-device copy; remove source after."""
    _ensure_dir(dst_dir)
    # rsync prints overall progress to stderr with --info=progress2
    # We stream and parse percent/bytes to feed UI if on_progress is set.
    cmd = [
        "rsync", "-a", "--info=progress2", "--no-inc-recursive",
        "--remove-source-files", "--", src, dst_dir + os.sep
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    if on_progress:
        # Parse progress like: "  34,567,890  12%   12.34MB/s    0:12:34 (xfr#1, to-chk=0/1)"
        for line in proc.stderr:
            line = line.strip()
            if not line:
                continue
            # crude parse: look for "<bytes>  <pct>%"
            try:
                parts = line.replace(',', '').split()
                # parts[0] may be bytes copied so far, parts[1] may be "12%"
                if len(parts) >= 2 and parts[1].endswith('%'):
                    bytes_so_far = int(parts[0])
                    pct = int(parts[1][:-1])
                    on_progress(bytes_so_far, pct)
            except Exception:
                pass

    proc.wait()
    if proc.returncode != 0:
        # If rsync failed, raise with stderr for visibility
        err = (proc.stderr.read() if proc.stderr else "") or "rsync error"
        raise RuntimeError(err.strip())

    # rsync with --remove-source-files removes the file; if anything remains, clean up
    if os.path.exists(src):
        try: os.remove(src)
        except Exception: pass

    return os.path.join(dst_dir, os.path.basename(src))

def _mv_move(src: str, dst_dir: str):
    _ensure_dir(dst_dir)
    cmd = ["mv", "--", src, dst_dir + os.sep]
    subprocess.run(cmd, check=True)
    return os.path.join(dst_dir, os.path.basename(src))

def move_one_fast(src: str, dst_dir: str, on_progress=None) -> str:
    """
    Move a single file to dst_dir:
      1) try atomic rename (fastest)
      2) on EXDEV, fall back to rsync (with progress) or mv
    """
    _ensure_dir(dst_dir)

    # 1) Try atomic rename regardless of st_dev (Docker Desktop can misreport)
    try:
        return _rename_fast(src, dst_dir)
    except OSError as e:
        # Only fall back if it's a cross-device link error
        if getattr(e, "errno", None) != errno.EXDEV:
            # Some platforms report errno in args[0]
            if not (isinstance(e.args, tuple) and len(e.args) > 0 and e.args[0] == errno.EXDEV):
                raise

    # 2) Cross-device fallback
    if _have("rsync"):
        return _rsync_move(src, dst_dir, on_progress=on_progress)
    return _mv_move(src, dst_dir)


def move_files(paths, dest_dir, repo_dir=None, on_file_progress=None):
    """
    Move many files with fast path + robust EXDEV fallback.
    on_file_progress(file_path, bytes_so_far, pct) if provided.
    Returns list of new paths.
    """
    moved = []
    for p in paths:
        # Optional safety: ensure within repo
        if repo_dir and not os.path.abspath(p).startswith(os.path.abspath(repo_dir) + os.sep):
            raise ValueError(f"path outside repo: {p}")

        # First try the fast path
        try:
            newp = move_one_fast(
                p, dest_dir,
                on_progress=(lambda b, pct, fp=p: on_file_progress and on_file_progress(fp, b, pct))
            )
        except OSError as e:
            # Final safety: explicit EXDEV fallback here as well
            if getattr(e, "errno", None) == errno.EXDEV or (isinstance(e.args, tuple) and len(e.args) > 0 and e.args[0] == errno.EXDEV):
                if _have("rsync"):
                    newp = _rsync_move(p, dest_dir, on_progress=(lambda b, pct, fp=p: on_file_progress and on_file_progress(fp, b, pct)))
                else:
                    newp = _mv_move(p, dest_dir)
            else:
                raise
        moved.append(newp)
    return moved


def move_with_robocopy(src: str, dst_dir: str) -> str:
    """Use Robocopy on Windows to move a file (works across volumes)."""
    if platform.system() != "Windows":
        raise RuntimeError("Robocopy only available on Windows")

    os.makedirs(dst_dir, exist_ok=True)
    dst_file = os.path.join(dst_dir, os.path.basename(src))

    # Robocopy expects dirs, not files → copy then delete
    cmd = ["robocopy", os.path.dirname(src), dst_dir, os.path.basename(src), "/MOV", "/NFL", "/NDL", "/NJH", "/NJS", "/nc", "/ns", "/np"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode >= 8:  # robocopy returns 0–7 as success
        raise RuntimeError(f"Robocopy failed: {result.stderr or result.stdout}")
    return dst_file


def _within(base, path):
    base = os.path.abspath(base)
    path = os.path.abspath(path)
    try:
        return os.path.commonpath([base]) == os.path.commonpath([base, path])
    except Exception:
        return False

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


def _probe_fps(src: str) -> float | None:
    """Return avg frame rate (float) from the first video stream, or None."""
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=avg_frame_rate",
            "-of", "json", src
        ], stderr=subprocess.STDOUT)
        data = json.loads(out.decode("utf-8"))
        streams = data.get("streams") or []
        if not streams:
            return None
        afr = streams[0].get("avg_frame_rate")
        if afr and afr != "0/0":
            num, den = afr.split("/")
            if float(den) != 0:
                return float(num) / float(den)
    except Exception:
        pass
    return None

def _probe_audio_duration(src: str) -> float | None:
    """
    Return duration (seconds) from the first audio stream; fallback to
    container duration if audio-only probing fails.
    """
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=duration",
            "-of", "json", src
        ], stderr=subprocess.STDOUT)
        data = json.loads(out.decode("utf-8"))
        streams = data.get("streams") or []
        dur = streams[0].get("duration") if streams else None
        if dur is not None:
            return float(dur)
    except Exception:
        pass

    # Fallback to container duration
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", src
        ], stderr=subprocess.STDOUT)
        data = json.loads(out.decode("utf-8"))
        dur = (data.get("format") or {}).get("duration")
        if dur is not None:
            return float(dur)
    except Exception:
        pass

    return None

def ffmpeg_extract_audio(src: str, out_dir: str | None = None) -> str:
    """
    Create MOV with Hap black filler video + PCM16LE audio.
    - If the source has video, match its FPS.
    - Filler video duration is set to the source audio duration.
    - Falls back to 30 fps and 'shortest' if probing fails.
    """
    p = Path(src)
    target_dir = Path(out_dir) if out_dir else p.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(target_dir / f"{p.stem}_hapaudio.mov")

    fps = _probe_fps(src) or 30
    dur = _probe_audio_duration(src)  # seconds (float) or None

    try:
        # Build the black filler as a lavfi input with desired r (fps) and d (duration)
        # Example: color=c=black:s=16x16:r=23.976:d=12.345
        color_args = f"color=c=black:s=16x16:r={fps}"
        if dur and dur > 0:
            # Format to reasonable precision to avoid super long decimals
            color_args += f":d={dur:.6f}"

        color = ffmpeg.input(color_args, f='lavfi')
        audio = ffmpeg.input(src)

        # If duration could not be probed, keep 'shortest' to trim to audio
        common_output_args = dict(
            vcodec='hap',
            acodec='pcm_s16le',
            format='mov',
            ar=48000,
            tune='stillimage'
        )
        out = ffmpeg.output(color, audio, out_path, **common_output_args)

        if not dur:
            # Ensure we never out-run the audio if duration wasn't set
            out = out.global_args('-shortest')

        (
            out
            .global_args('-map', '0:v', '-map', '1:a')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

    except ffmpeg.Error as e:
        err = e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)
        raise RuntimeError(f"ffmpeg hapaudio failed for {src}: {err}")

    return out_path
