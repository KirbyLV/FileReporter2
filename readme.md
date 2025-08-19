# Media Repo Manager – Flask App (Docker-ready)

A complete, ready-to-run Flask application to scan a media repository, view metadata, bulk move assets (approve/quarantine), generate Hap/Hap Alpha proxies to /repo/_proxies, extract audio to a Hap (black video) + PCM MOV, and sync records to Google Sheets with _vNN version tracking.

## Features

Scan repo (recursive) for video & audio; collect: name, path, size, codec, fps, resolution, duration, has-audio, created/modified times.

Web UI with select-all/none, bulk actions: Approve → SHOW_MEDIA_DIR, Quarantine → QUARANTINE_DIR, Make Proxies, Extract Audio.

Proxies: Hap/Hap Alpha, scale factor 1/2 or 1/4, written to /repo/_proxies.

Audio extract: MOV with Hap black 16×16 @30fps + PCM16LE 48k (maps video from a generated color source, audio from file).

Docker: Dockerfile + docker-compose.yml with volumes and a writable /config for settings & service account JSON.

### Google Sheets: 
Service Account auth; upsert by filename stem (portion before _vNN), update when a higher version appears. 
Your custom columns stay as-is. For existing rows we rewrite the whole row—but using the existing values we just read for custom columns, so they’re preserved.

If you later add a new managed column (say, bitrate), the app adds that header to the right and starts filling it; your custom columns don’t move or get erased.

The unique key is still stem (the filename base before _vNN). If you change stems manually in the sheet, the app will treat them as different assets.

## Project Structure
media-repo-manager/
├─ app.py
├─ media_utils.py
├─ sheets_sync.py
├─ static/
│  ├─ app.js
│  └─ app.css
├─ templates/
│  ├─ index.html
│  └─ settings.html
├─ requirements.txt
├─ Dockerfile
└─ docker-compose.yml

## Project Setup, in docker
Ensure Docker Desktop has access to the media and folder locations:
-In Docker Desktop: Settings > Resources > File Sharing
-Add folder directories as virtual file shares

in docker-compose.yml:
-under volumes, ensure the structure reads as:
--/location/of/repo_folder:/repo:rw
--/location/of/quarantine_folder:/repo_quarantine:rw
--/location/of/show_media:/repo_show:rw

## Configuration (Env Vars)
REPO_DIR – repo to scan (default /repo)

QUARANTINE_DIR – destination for quarantined assets (default /repo_quarantine)

SHOW_MEDIA_DIR – destination for approved assets (default /repo_show)

CONFIG_DIR – writable config directory (default /config)

GOOGLE_SERVICE_ACCOUNT_JSON – service account JSON path (default /config/google-service-account.json)

GOOGLE_SHEET_NAME – default sheet name (editable in UI Settings)

## To obtain a Google service account JSON file for this application:

Go to the Google Cloud Console: https://console.cloud.google.com

Create or select a project: If you don't already have a project for this app, click New Project and give it a name.

### Enable Google Sheets API (and optionally Google Drive API):

Navigate to APIs & Services → Library.

Search for “Google Sheets API” and enable it.

Do the same for “Google Drive API” if you want the app to create spreadsheets automatically.

### Create a Service Account:

Go to APIs & Services → Credentials.

Click Create Credentials → Service account.

Name it, click Create and Continue, and grant it basic role (e.g., "Editor" if you need write access to Sheets).

Click Done.

### Generate a JSON key:

Find the service account you just created in the list.

Click it, then go to the Keys tab.

Click Add Key → Create new key, choose JSON, and download the file.

### Share the target Google Sheet with the service account email**:

Open your Google Sheet in Google Sheets.

Share it with the email address from the JSON (looks like your-service-account@your-project.iam.gserviceaccount.com) and give it edit access.

Upload the JSON in the app's Settings page, or place it in /config/google-service-account.json if running locally/Docker.

This JSON file will allow the app to authenticate and update your Google Sheet automatically.



## Running Locally (without Docker) - UNTESTED
NOTE:: We have only tested anythgin with Docker and we recomend using docker desktop.

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export REPO_DIR="/path/to/your/repo"
export QUARANTINE_DIR="/path/to/your/quarantine"
export SHOW_MEDIA_DIR="/path/to/your/show"
export CONFIG_DIR="/absolute/path/to/config"
export GOOGLE_SERVICE_ACCOUNT_JSON="$CONFIG_DIR/google-service-account.json"
export GOOGLE_SHEET_NAME="Media Repo Inventory"
python app.py

Open <http://localhost:8008>

## Notes
Security: service account JSON is uploaded to /config via Settings page and never exposed back to the client.

Version logic: keys on stem (before _vNN). We upsert the current state.

Jobs: in-process thread pool for now; for larger batches consider Celery + Redis.

Paths: moves are restricted under REPO_DIR by safe_relpath.

CONFIG_DIR is simply the writable directory where the app stores persistent settings and the Google service account JSON.
In Docker, it defaults to /config and is mounted as a volume so it survives container restarts.

Creation time: best-effort on Unix; reliable on Windows.