# File Reporter 2
A Docker-ready Flask App 

A complete, ready-to-run Flask application to scan a media repository, view metadata, bulk move assets (approve/quarantine), generate Hap/Hap Alpha proxies to /repo/_proxies, extract audio to a Hap (black video) + PCM MOV, and sync records to Google Sheets with _vNN version tracking.

## To Use
### Download
+ If on PC: Download the exe file under releases and launch. You may need to disable anti-virus, I just dont have the app signed.  
+ If on Mac: Downlaod configurator.py and run using a python launcher.  
The configurator app will pull everything else needed from Docker hub. web connection is needed.  

If desired, you can clone the entire git repo and run from configurator using "build locally" instead of pulling the prebuilt image form docker hub.  

### Initial Configuration:
Launch `Configurator.py` and populate the values the app asks for
<img width="913" height="625" alt="Screenshot 2025-08-22 at 1 00 44 PM" src="https://github.com/user-attachments/assets/a0e14a9b-bf23-45cc-9740-c402f289f9ad" />

Select the following by either typing in the paths or using the browse button:
+ Repo Folder: The location where all the raw content will arrive, while awaiting QC.
+ Show Folder: The location of the approved media, to be sync'd to show servers.
+ Quarantine Folder: A holding purgatory for items with issues or items that need to be reencoded.

Ensure Docker has access to your folder locations. See below under Project Setup in Docker for more details.

Non mandatory:
+ Service Account JSON: The json file from google that enables google sheet synchronization. See below in "To obtain a Google service account JSON file for this application"
+ Google Sheet Name: The name of the sheet that the google API will publish to.  

Once fields are popualted, the buttons to build the docker file and launch the app will become available.

### Launching the app
Ensure docker desktop is running and has access to the file locations needed.

1. If google sheets is being used, click "Copy SA JSON to /config"
2. Click on "Write docker-compose.yml"
3. Click on "Start App". This will run `docker copose up-d` and will start the application. Yopu should see data process in the status frame.
4. Click on "Open Web Portal" to launch the front end web portal in your browser. 

Other controls:
+ View Log: shows the log in the status display, including any docker errors. This will continue to run until "Stop Log" is pressed.
+ Stop App: Shutsdown the docker containers, basically jsut runs `docker compose down `.
+ Restart App: restarts the docker containers. If repos are changed, you should stop and then start to grab the new docker compose file.

All docker containers and their status should also be visible in docker desktop.

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
<img width="1121" height="236" alt="Screenshot 2025-08-19 at 9 26 12 AM" src="https://github.com/user-attachments/assets/50ebd126-82d7-4eb8-8d16-c86eb67f4497" />

From the web portal, click on "Scan Repo" in the top to scan all files in the Repo Folder setup during configuration. 

You can use the "Sync google Sheet"  button to publish the data visible in the web portal to the chosen google sheet setup during configuration. Please do this AFTER quarantining and BEFORE approving in order to keep an up-to-date record of which assets have been pushed to the show folder.

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
media-repo-manager/
├─ app.py
├─ media_utils.py
├─ sheets_sync.py
├─ configurator.py
├─ static/
│  ├─ app.js
│  └─ app.css
|  └─ assets/
│    └─ FR_Logo.png
├─ templates/
│  ├─ index.html
│  └─ settings.html
├─ requirements.txt
├─ Dockerfile
└─ docker-compose.yml
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
