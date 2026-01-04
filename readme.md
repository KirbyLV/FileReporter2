# File Reporter 2
A Docker-ready Flask App

A complete, ready-to-run Flask application to scan a media repository, view metadata, bulk move assets (approve/quarantine), generate Hap/Hap Alpha proxies to /repo/_proxies, extract audio to a Hap (black video) + PCM MOV, and sync records to Google Sheets with _vNN version tracking.

## To Use

### Quick Start: Desktop Configurator (Recommended)

The easiest way to get started is with the **CustomTkinter configurator**:

**Option 1: Download Pre-built Executable**
1. Download the latest release from the [Releases page](https://github.com/jspodick/FileReporter2/releases)
2. **Windows**:
   - Download `FileReporter2-Configurator-Windows.exe`
   - Double-click to run
3. **macOS**:
   - Download `FileReporter2-Configurator-macOS.zip`
   - Unzip to get `FileReporter2 Configurator.app`
   - Right-click → Open (first time only, to bypass Gatekeeper)
   - Or drag to Applications folder
4. The configurator has a modern dark UI with native file/directory pickers

**Option 2: Run from Python**
```bash
pip install customtkinter
python configurator.py
```

**Benefits:**
- ✅ Native file/directory pickers (just like any desktop app)
- ✅ Modern dark theme with red/yellow/gold accents
- ✅ Cross-platform (macOS, Windows, Linux)
- ✅ Standalone executable - no Python needed for end users
- ✅ All Docker management features built-in

### Alternative: Web Configurator (Advanced)

For server environments or remote management, there's also a web-based configurator:

```bash
docker run -d -p 8009:8009 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/config:/config \
  -v $(pwd):/workspace \
  jspodick/filereporter2-configurator:latest
```

Then open http://localhost:8009 - Note: Web browsers cannot provide native file pickers, so you'll need to type paths manually.

For detailed web configurator instructions, see [configurator-web/README.md](configurator-web/README.md)  

### Initial Configuration

#### Using the Web Configurator

1. Open http://localhost:8009 in your browser
2. Use the web-based directory browser to select:
   - **Repo Folder**: The location where all the raw content will arrive, while awaiting QC
   - **Show Folder**: The location of the approved media, to be sync'd to show servers
   - **Quarantine Folder**: A holding purgatory for items with issues or items that need to be reencoded
3. Upload your **Service Account JSON** file (optional, for Google Sheets sync)
4. Enter your **Google Sheet Name** (optional)
5. Choose deployment mode:
   - **Use Prebuilt Image**: Pulls from Docker Hub (recommended)
   - **Build Locally**: Builds from source in your repository
6. Click "Save Configuration" and "Generate docker-compose.yml"
7. Click "Start App" to launch FileReporter2

#### Using the Legacy Configurator (Desktop App)

Launch `configurator-legacy.py` and populate the values the app asks for:
<img width="913" height="625" alt="Screenshot-FileReporter2-Configurator" src="https://github.com/user-attachments/assets/a0e14a9b-bf23-45cc-9740-c402f289f9ad" />

Select the following by typing in the paths or using the browse button:
+ Repo Folder: The location where all the raw content will arrive, while awaiting QC.
+ Show Folder: The location of the approved media, to be sync'd to show servers.
+ Quarantine Folder: A holding purgatory for items with issues or items that need to be reencoded.

Ensure Docker has access to your folder locations. See below under Project Setup in Docker for more details.

Non mandatory:
+ Service Account JSON: The json file from google that enables google sheet synchronization. See below in "To obtain a Google service account JSON file for this application"
+ Google Sheet Name: The name of the sheet that the google API will publish to.  

Once fields are popualted, the buttons to build the docker file and launch the app will become available.

### Launching the App

#### With Web Configurator

Ensure Docker Desktop is running and has access to the file locations needed.

1. Configure all directories and settings in the web UI (http://localhost:8009)
2. Click "Save Configuration"
3. Click "Generate docker-compose.yml"
4. Click "Start App" - this will run `docker compose up -d`
5. Once started, click "Open Main App" to access FileReporter2 at http://localhost:8008

**Controls:**
- **View Logs**: Real-time log streaming in the browser
- **Stop Logs**: Stop the log stream
- **Stop App**: Shuts down the Docker containers (`docker compose down`)
- **Restart App**: Restarts the Docker containers
- **Refresh Status**: Check current container status

All Docker containers and their status are also visible in Docker Desktop.

#### With Legacy Configurator (Desktop App)

Ensure Docker Desktop is running and has access to the file locations needed.

1. If Google Sheets is being used, click "Copy SA JSON to /config"
2. Click on "Write docker-compose.yml"
3. Click on "Start App". This will run `docker compose up -d` and will start the application. You should see data process in the status frame.
4. Click on "Open Web Portal" to launch the front end web portal in your browser (http://localhost:8008)

**Other controls:**
- **View Log**: Shows the log in the status display, including any docker errors. This will continue to run until "Stop Log" is pressed.
- **Stop App**: Shuts down the docker containers (`docker compose down`)
- **Restart App**: Restarts the docker containers. If repos are changed, you should stop and then start to grab the new docker compose file.

All Docker containers and their status are also visible in Docker Desktop.

### If on Apple Silicon
You may need to edit the docker-compose.yaml file to direct docker to emulate the proper platform. 
```
services:
  media:
    image: jspodick/filereporter2:latest
    platform: linux/amd64
    ports:
      - "8008:8008"
```

### Using the app
<img width="1121" height="236" alt="Screenshot-FileReporter2-UI" src="https://github.com/user-attachments/assets/50ebd126-82d7-4eb8-8d16-c86eb67f4497" />

From the web portal, click on "Scan Repo" in the top to scan all files in the Repo Folder setup during configuration. 

You can use the "Sync google Sheet"  button to publish the data visible in the web portal to the chosen google sheet setup during configuration. Please do this AFTER quarantining and BEFORE approving in order to keep an up-to-date record of which assets have been pushed to the show folder.

#### Settings
<img width="848" height="325" alt="Screenshot-FileReporter2-Settings" src="https://github.com/user-attachments/assets/35a9fa58-8347-40ce-a60b-29d66d7853e9" />

+ There is a link for the settigns page in the top-right corner of the web portal.
+ Aside from checking the google sheet name and path that you loaded for the Google Service Account JSON file, you can decide to use Robocopy for file move actions.
+ By default, the app has built-in functions to move files between Docker mounts, that translate to the folders you assigned during setup.
+ On Windows, Robocopy may be slightly faster for file moves, but you do not see the move progress. It is user-preference on which method to use.

#### File move actions
+ Aprove Assets: will move all selected assets (with a checkbox) from the repo folder to the show folder
+ Quarantine Assets: will move all selected assets from the repo folder to the quarantine folder
+ Niether of these will have any effect on your google sheet

#### File processing
Proxy Maker:
+ Select which files need proxies by selecting the appropriate checkboxes
+ Select the scale (1/4 or 1/2) of the desired proxy
+ Select whether or not the file has alpha (will encode with HAP or HAPALPHA)
+ Click on "Make Proxies"
  You will see a line appear that shows the processing status of files. Proxied files will be loaded back into the repo folder ready for QC and will not be automatically pushed to the show folder.

Audio Extraction:
+ Select which files need audio extraction by selecting the appropriate checkboxes
+ Click on "Extract Audio"
  You will see a line appear that shows the processing status of files. Audio files will be encoded as 16x16 pixel black HAP files with the selected audio embedded. Files will be named as the original with an appeendage of `_hapaudio`. Audio files will be loaded back into the repo folder ready for QC and will not be automaticallty pushed to the show folder.

## Features

Scan repo (recursive) for video & audio; collect: name, path, size, codec, fps, resolution, duration, has-audio, created/modified times.

Web UI with select-all/none, bulk actions: Approve → SHOW_MEDIA_DIR, Quarantine → QUARANTINE_DIR, Make Proxies, Extract Audio.

Proxies: Hap/Hap Alpha, scale factor 1/2 or 1/4, written to /repo/_proxies.

Audio extract: MOV with Hap black 16×16 @30fps + PCM16LE 48k (maps video from a generated color source, audio from file).

Docker: Dockerfile + docker-compose.yml with volumes and a writable /config for settings & service account JSON.

#### Google Sheets: 
Service Account auth; upsert by filename stem (portion before _vNN), update when a higher version appears. 
Your custom columns stay as-is. For existing rows we rewrite the whole row—but using the existing values we just read for custom columns, so they’re preserved.

If you later add a new managed column (say, bitrate), the app adds that header to the right and starts filling it; your custom columns don’t move or get erased.

The unique key is still stem (the filename base before _vNN). If you change stems manually in the sheet, the app will treat them as different assets.

## Project Structure
```
FileReporter2/
├─ app.py                          # Main Flask application
├─ media_utils.py                  # Media scanning and processing
├─ sheets_sync.py                  # Google Sheets integration
├─ configurator-legacy.py          # Legacy Tkinter configurator (desktop)
├─ start-configurator.sh           # Quick start script for web configurator
├─ static/                         # Main app frontend assets
│  ├─ app.js
│  ├─ app.css
│  └─ assets/
│    └─ FR_Logo.png
├─ templates/                      # Main app HTML templates
│  ├─ index.html
│  └─ settings.html
├─ configurator-web/               # Web-based configurator (NEW)
│  ├─ configurator_app.py          # Flask backend
│  ├─ docker_manager.py            # Docker API wrapper
│  ├─ compose_generator.py         # Compose file generator
│  ├─ file_browser.py              # Directory browser API
│  ├─ static/                      # Configurator frontend
│  │  ├─ configurator.js
│  │  └─ configurator.css
│  ├─ templates/
│  │  └─ configurator.html
│  ├─ Dockerfile                   # Configurator container
│  ├─ docker-compose.yml           # Run configurator
│  └─ README.md                    # Configurator docs
├─ requirements.txt
├─ Dockerfile                      # Main app container
└─ docker-compose.yml              # Generated by configurator
```
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
- REPO_DIR – repo to scan (default /repo)

- QUARANTINE_DIR – destination for quarantined assets (default /repo_quarantine)

- SHOW_MEDIA_DIR – destination for approved assets (default /repo_show)

- CONFIG_DIR – writable config directory (default /config)

- GOOGLE_SERVICE_ACCOUNT_JSON – service account JSON path (default /config/google-service-account.json)

- GOOGLE_SHEET_NAME – default sheet name (editable in UI Settings)

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
