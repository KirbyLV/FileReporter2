"""
FileReporter2 Web Configurator
Flask application for configuring and managing the FileReporter2 Docker container.
"""

import os
import json
from flask import Flask, render_template, request, jsonify, Response
from werkzeug.utils import secure_filename
from compose_generator import ComposeGenerator
from docker_manager import DockerManager
from file_browser import FileBrowser

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Configuration
WORKSPACE_PATH = os.environ.get('WORKSPACE_PATH', '/workspace')
CONFIG_PATH = os.environ.get('CONFIG_PATH', '/config')
SETTINGS_FILE = os.path.join(CONFIG_PATH, 'configurator-settings.json')
HOST_MOUNT = os.environ.get('HOST_MOUNT', '/host')

# Initialize components
compose_gen = ComposeGenerator(workspace_path=WORKSPACE_PATH)
docker_mgr = DockerManager(compose_file=os.path.join(WORKSPACE_PATH, 'docker-compose.yml'))
file_browser = FileBrowser(host_root=HOST_MOUNT)


# --- Configuration Management ---

def load_config():
    """Load configuration from settings file."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return get_default_config()
    return get_default_config()


def save_config(config):
    """Save configuration to settings file."""
    try:
        os.makedirs(CONFIG_PATH, exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True, ""
    except Exception as e:
        return False, f"Error saving config: {str(e)}"


def get_default_config():
    """Get default configuration."""
    return {
        "repo_dir": "",
        "show_dir": "",
        "quarantine_dir": "",
        "config_dir": "./config",
        "sheet_name": "Media Repo Inventory",
        "deploy_mode": "image",
        "image_ref": "jspodick/filereporter2:latest",
        "service_account_uploaded": False
    }


# --- Routes ---

@app.route('/')
def index():
    """Main configurator page."""
    return render_template('configurator.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration."""
    config = load_config()
    return jsonify(config)


@app.route('/api/config', methods=['POST'])
def update_config():
    """Save configuration."""
    try:
        config = request.get_json()
        success, error = save_config(config)
        if success:
            return jsonify({"success": True, "message": "Configuration saved"})
        else:
            return jsonify({"success": False, "error": error}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/config/generate', methods=['POST'])
def generate_compose():
    """Generate docker-compose.yml file."""
    try:
        config = request.get_json()

        # Save config first
        save_config(config)

        # Generate compose file
        success, error = compose_gen.write_compose_file(config)

        if success:
            return jsonify({
                "success": True,
                "message": "docker-compose.yml generated successfully"
            })
        else:
            return jsonify({"success": False, "error": error}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/config/upload-sa', methods=['POST'])
def upload_service_account():
    """Upload service account JSON file."""
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No file provided"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "No file selected"}), 400

        if not file.filename.endswith('.json'):
            return jsonify({"success": False, "error": "File must be a JSON file"}), 400

        # Validate JSON content
        try:
            content = file.read()
            json.loads(content)  # Validate JSON
            file.seek(0)  # Reset file pointer
        except json.JSONDecodeError:
            return jsonify({"success": False, "error": "Invalid JSON file"}), 400

        # Save file
        os.makedirs(CONFIG_PATH, exist_ok=True)
        dest_path = os.path.join(CONFIG_PATH, 'google-service-account.json')

        with open(dest_path, 'wb') as f:
            f.write(content)

        # Update config
        config = load_config()
        config['service_account_uploaded'] = True
        save_config(config)

        return jsonify({
            "success": True,
            "message": f"Service account file saved to {dest_path}"
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --- Docker Management ---

@app.route('/api/docker/status', methods=['GET'])
def docker_status():
    """Get Docker and container status."""
    # Check Docker availability
    docker_available, docker_msg = docker_mgr.check_available()
    compose_available, compose_type = docker_mgr.check_docker_compose()

    # Get container status
    container_status = docker_mgr.get_status()

    return jsonify({
        "docker_available": docker_available,
        "docker_message": docker_msg,
        "compose_available": compose_available,
        "compose_type": compose_type,
        "container": container_status
    })


@app.route('/api/docker/pull', methods=['POST'])
def docker_pull():
    """Pull Docker image."""
    try:
        data = request.get_json()
        image_ref = data.get('image_ref')

        if not image_ref:
            return jsonify({"success": False, "error": "No image reference provided"}), 400

        success, message = docker_mgr.pull_image(image_ref)

        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/docker/up', methods=['POST'])
def docker_up():
    """Start the main application container."""
    try:
        data = request.get_json()
        build = data.get('build', False)

        success, message = docker_mgr.compose_up(build=build)

        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/docker/down', methods=['POST'])
def docker_down():
    """Stop the main application container."""
    try:
        success, message = docker_mgr.compose_down()

        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/docker/restart', methods=['POST'])
def docker_restart():
    """Restart the main application container."""
    try:
        success, message = docker_mgr.compose_restart()

        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/docker/logs/stream', methods=['GET'])
def docker_logs_stream():
    """Stream Docker logs using Server-Sent Events."""
    def generate():
        try:
            for line in docker_mgr.stream_logs(tail=200):
                yield f"data: {line}\n\n"
        except Exception as e:
            yield f"data: Error streaming logs: {str(e)}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/docker/logs', methods=['GET'])
def docker_logs():
    """Get recent Docker logs (non-streaming)."""
    try:
        tail = request.args.get('tail', 200, type=int)
        logs = docker_mgr.get_logs(tail=tail)
        return jsonify({"success": True, "logs": logs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --- File Browser ---

@app.route('/api/browse', methods=['GET'])
def browse_directory():
    """Browse directories on host filesystem."""
    try:
        path = request.args.get('path')
        result = file_browser.list_directory(path)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/validate-path', methods=['POST'])
def validate_path():
    """Validate that a path exists and is accessible."""
    try:
        data = request.get_json()
        path = data.get('path')

        if not path:
            return jsonify({"valid": False, "error": "No path provided"}), 400

        is_valid, error_msg = file_browser.validate_path(path)

        return jsonify({
            "valid": is_valid,
            "error": error_msg if not is_valid else None
        })

    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 500


# --- Health Check ---

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    # Ensure config directory exists
    os.makedirs(CONFIG_PATH, exist_ok=True)

    # Run Flask app
    app.run(host='0.0.0.0', port=8009, debug=True)
