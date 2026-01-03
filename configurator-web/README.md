# FileReporter2 Web Configurator

A modern, web-based configurator for FileReporter2 that runs in Docker. This replaces the legacy Tkinter-based configurator with a cross-platform web interface.

## Features

- **Cross-platform**: Works on macOS, Windows, and Linux
- **Web-based directory browser**: Navigate and select directories through your browser
- **Docker integration**: Start, stop, and manage the main FileReporter2 app
- **Real-time logs**: Stream container logs directly in the browser
- **Easy sharing**: Distribute as a single Docker image - no platform-specific executables needed

## Quick Start

### Option 1: Using Docker Compose (Recommended for Development)

```bash
cd configurator-web
docker-compose up -d
```

Then open http://localhost:8009 in your browser.

### Option 2: Using Pre-built Image (Recommended for End Users)

From the main FileReporter2 directory:

```bash
./start-configurator.sh
```

Or manually:

```bash
docker run -d \
  -p 8009:8009 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/config:/config \
  -v $(pwd):/workspace \
  -v /:/host:ro \
  --name filereporter2-config \
  jspodick/filereporter2-configurator:latest
```

Then open http://localhost:8009 in your browser.

## How It Works

1. **Configure Directories**: Use the web-based directory browser to select:
   - Repo directory (source media files)
   - Show directory (approved/processed files)
   - Quarantine directory (rejected files)

2. **Google Sheets Integration**: Upload your service account JSON and enter your sheet name

3. **Select Deployment Mode**:
   - **Prebuilt Image**: Uses `jspodick/filereporter2:latest` from Docker Hub (faster)
   - **Build Locally**: Builds from source in your repository (for development)

4. **Generate Configuration**: Click "Generate docker-compose.yml" to create the main app configuration

5. **Start the App**: Click "Start App" to launch FileReporter2

6. **Monitor**: View real-time logs and container status

## Directory Structure

```
configurator-web/
├── Dockerfile                  # Container image definition
├── docker-compose.yml         # For running configurator itself
├── requirements.txt           # Python dependencies
├── configurator_app.py        # Main Flask application
├── docker_manager.py          # Docker API wrapper
├── compose_generator.py       # docker-compose.yml generator
├── file_browser.py           # Host filesystem browser
├── static/
│   ├── configurator.css      # Styling
│   └── configurator.js       # Frontend logic
└── templates/
    └── configurator.html     # Main UI template
```

## API Endpoints

### Configuration
- `GET /api/config` - Get current configuration
- `POST /api/config` - Save configuration
- `POST /api/config/generate` - Generate docker-compose.yml
- `POST /api/config/upload-sa` - Upload service account JSON

### Docker Management
- `GET /api/docker/status` - Get container status
- `POST /api/docker/pull` - Pull Docker image
- `POST /api/docker/up` - Start main app
- `POST /api/docker/down` - Stop main app
- `POST /api/docker/restart` - Restart main app
- `GET /api/docker/logs/stream` - Stream logs (SSE)

### File Browser
- `GET /api/browse?path=/some/path` - List directories
- `POST /api/validate-path` - Validate path exists

## Building and Publishing

### Build Image

```bash
cd configurator-web
docker build -t jspodick/filereporter2-configurator:latest .
```

### Push to Docker Hub

```bash
docker push jspodick/filereporter2-configurator:latest
```

### Tag with Version

```bash
docker tag jspodick/filereporter2-configurator:latest jspodick/filereporter2-configurator:v1.0.0
docker push jspodick/filereporter2-configurator:v1.0.0
```

## Security Considerations

### Docker Socket Access

The configurator mounts the Docker socket (`/var/run/docker.sock`) to control Docker containers. This gives the configurator **root-equivalent access** to the host system.

**Security implications:**
- The configurator can start/stop any container
- It can access the Docker daemon with full privileges
- Only run this on trusted systems
- Do not expose port 8009 to untrusted networks

**Mitigation options:**
- Run on local machine only (localhost:8009)
- Use Docker socket proxy (e.g., tecnativa/docker-socket-proxy) for production
- Consider rootless Docker for additional isolation

### Host Filesystem Access

The configurator mounts the host root filesystem at `/host:ro` (read-only) for the directory browser. This allows it to:
- List directories on the host
- Validate paths exist
- **Cannot modify files** (read-only mount)

## Troubleshooting

### Docker Socket Permission Denied

If you see "permission denied" errors accessing Docker:
- **Linux**: Add your user to the `docker` group: `sudo usermod -aG docker $USER`
- **macOS/Windows**: Ensure Docker Desktop is running

### Port Already in Use

If port 8009 is already in use:
```bash
# Stop existing container
docker stop filereporter2-config
docker rm filereporter2-config
```

Or change the port in docker-compose.yml:
```yaml
ports:
  - "9009:8009"  # Use 9009 instead
```

### Container Won't Start

Check logs:
```bash
docker logs configurator-web-configurator-1
```

Common issues:
- Docker socket not accessible
- Port 8009 already in use
- Volume mount permissions

## Development

### Run Locally (Outside Docker)

```bash
cd configurator-web
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
export WORKSPACE_PATH=$(pwd)/..
export CONFIG_PATH=$(pwd)/../config
export HOST_MOUNT=/
python configurator_app.py
```

Open http://localhost:8009

### Debug Mode

The Flask app runs in debug mode by default when using docker-compose. This enables:
- Auto-reload on code changes
- Detailed error messages
- Interactive debugger

For production, set `debug=False` in `configurator_app.py`.

## Comparison with Legacy Configurator

| Feature | Legacy (Tkinter) | Web Configurator |
|---------|------------------|------------------|
| Platform | Platform-specific exe | Universal Docker |
| Distribution | Separate builds per OS | Single Docker image |
| Directory Selection | Native file dialogs | Web-based browser |
| Updates | Re-download exe | Pull Docker image |
| Dependencies | Bundled (large) | Docker only |
| Remote Access | No | Yes (via browser) |

## License

Same as FileReporter2 main application.
