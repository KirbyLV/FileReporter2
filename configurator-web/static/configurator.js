// FileReporter2 Web Configurator - Frontend Logic

let currentTargetInput = null;
let currentBrowserPath = null;
let logStreamSource = null;
let statusPollInterval = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadConfig();
    refreshStatus();
    startStatusPolling();
    setupDeployModeToggle();
});

// --- Configuration Management ---

async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();

        document.getElementById('repoDir').value = config.repo_dir || '';
        document.getElementById('showDir').value = config.show_dir || '';
        document.getElementById('quarantineDir').value = config.quarantine_dir || '';
        document.getElementById('sheetName').value = config.sheet_name || 'Media Repo Inventory';
        document.getElementById('imageRef').value = config.image_ref || 'jspodick/filereporter2:latest';

        // Set deploy mode
        const deployMode = config.deploy_mode || 'image';
        document.querySelector(`input[name="deployMode"][value="${deployMode}"]`).checked = true;
        updateImageRefVisibility();

        if (config.service_account_uploaded) {
            document.getElementById('uploadStatus').textContent = 'Service account uploaded';
            document.getElementById('uploadStatus').className = 'upload-status success';
        }
    } catch (error) {
        showMessage('Error loading configuration: ' + error.message, 'error');
    }
}

async function saveConfig() {
    const config = getConfigFromForm();

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });

        const result = await response.json();
        if (result.success) {
            showMessage('Configuration saved successfully', 'success');
        } else {
            showMessage('Error: ' + result.error, 'error');
        }
    } catch (error) {
        showMessage('Error saving configuration: ' + error.message, 'error');
    }
}

async function generateCompose() {
    const config = getConfigFromForm();

    // Validate required fields
    if (!config.repo_dir || !config.show_dir || !config.quarantine_dir || !config.sheet_name) {
        showMessage('Please fill in all required fields', 'error');
        return;
    }

    try {
        const response = await fetch('/api/config/generate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });

        const result = await response.json();
        if (result.success) {
            showMessage('docker-compose.yml generated successfully', 'success');
            log('docker-compose.yml file created in workspace');
        } else {
            showMessage('Error: ' + result.error, 'error');
        }
    } catch (error) {
        showMessage('Error generating compose file: ' + error.message, 'error');
    }
}

function getConfigFromForm() {
    return {
        repo_dir: document.getElementById('repoDir').value.trim(),
        show_dir: document.getElementById('showDir').value.trim(),
        quarantine_dir: document.getElementById('quarantineDir').value.trim(),
        config_dir: './config',
        sheet_name: document.getElementById('sheetName').value.trim(),
        deploy_mode: document.querySelector('input[name="deployMode"]:checked').value,
        image_ref: document.getElementById('imageRef').value.trim(),
        service_account_uploaded: document.getElementById('uploadStatus').textContent.includes('uploaded')
    };
}

// --- File Upload ---

async function handleFileUpload(input) {
    const file = input.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/config/upload-sa', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        if (result.success) {
            showMessage('Service account file uploaded successfully', 'success');
            document.getElementById('uploadStatus').textContent = 'Uploaded: ' + file.name;
            document.getElementById('uploadStatus').className = 'upload-status success';
        } else {
            showMessage('Error: ' + result.error, 'error');
            document.getElementById('uploadStatus').textContent = 'Upload failed';
            document.getElementById('uploadStatus').className = 'upload-status error';
        }
    } catch (error) {
        showMessage('Error uploading file: ' + error.message, 'error');
    }
}

// --- Docker Actions ---

async function startApp() {
    const config = getConfigFromForm();
    const build = config.deploy_mode === 'build';

    log(`Starting app (${build ? 'build mode' : 'image mode'})...`);

    // Pull image first if using prebuilt
    if (!build && config.image_ref) {
        log(`Pulling image ${config.image_ref}...`);
        try {
            const pullResponse = await fetch('/api/docker/pull', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({image_ref: config.image_ref})
            });
            const pullResult = await pullResponse.json();
            if (pullResult.success) {
                log('Image pulled successfully');
            } else {
                log('Pull warning: ' + pullResult.error);
            }
        } catch (error) {
            log('Pull error: ' + error.message);
        }
    }

    try {
        const response = await fetch('/api/docker/up', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({build: build})
        });

        const result = await response.json();
        if (result.success) {
            showMessage('App started successfully', 'success');
            log('App started. Open http://localhost:8008');
            refreshStatus();
        } else {
            showMessage('Error: ' + result.error, 'error');
            log('Error starting app: ' + result.error);
        }
    } catch (error) {
        showMessage('Error starting app: ' + error.message, 'error');
        log('Error: ' + error.message);
    }
}

async function stopApp() {
    log('Stopping app...');

    try {
        const response = await fetch('/api/docker/down', {
            method: 'POST'
        });

        const result = await response.json();
        if (result.success) {
            showMessage('App stopped successfully', 'success');
            log('App stopped');
            refreshStatus();
        } else {
            showMessage('Error: ' + result.error, 'error');
            log('Error stopping app: ' + result.error);
        }
    } catch (error) {
        showMessage('Error stopping app: ' + error.message, 'error');
        log('Error: ' + error.message);
    }
}

async function restartApp() {
    log('Restarting app...');

    try {
        const response = await fetch('/api/docker/restart', {
            method: 'POST'
        });

        const result = await response.json();
        if (result.success) {
            showMessage('App restarted successfully', 'success');
            log('App restarted');
            refreshStatus();
        } else {
            showMessage('Error: ' + result.error, 'error');
            log('Error restarting app: ' + result.error);
        }
    } catch (error) {
        showMessage('Error restarting app: ' + error.message, 'error');
        log('Error: ' + error.message);
    }
}

function openMainApp() {
    window.open('http://localhost:8008', '_blank');
}

// --- Status Management ---

async function refreshStatus() {
    try {
        const response = await fetch('/api/docker/status');
        const status = await response.json();

        let statusText = '';
        let statusClass = '';

        if (!status.docker_available) {
            statusText = 'Docker Not Available';
            statusClass = 'status-error';
        } else if (!status.compose_available) {
            statusText = 'Docker Compose Not Available';
            statusClass = 'status-error';
        } else if (status.container.running) {
            statusText = 'Running';
            statusClass = 'status-running';
        } else {
            statusText = 'Stopped';
            statusClass = 'status-stopped';
        }

        const statusBadge = document.getElementById('containerStatus');
        statusBadge.textContent = statusText;
        statusBadge.className = 'status-badge ' + statusClass;

        const statusTextElem = document.getElementById('statusText');
        if (status.docker_available && status.compose_available) {
            statusTextElem.textContent = status.container.status_text;
        } else {
            statusTextElem.textContent = status.docker_message;
        }

        // Enable/disable buttons based on status
        document.getElementById('btnStart').disabled = !status.compose_available;
        document.getElementById('btnStop').disabled = !status.compose_available;
        document.getElementById('btnRestart').disabled = !status.compose_available;
        document.getElementById('btnOpenApp').disabled = !status.container.running;

    } catch (error) {
        console.error('Error refreshing status:', error);
    }
}

function startStatusPolling() {
    // Poll every 5 seconds
    statusPollInterval = setInterval(refreshStatus, 5000);
}

// --- Log Streaming ---

function startLogStream() {
    if (logStreamSource) {
        return; // Already streaming
    }

    log('Starting log stream...');

    logStreamSource = new EventSource('/api/docker/logs/stream');

    logStreamSource.onmessage = function(event) {
        log(event.data);
    };

    logStreamSource.onerror = function(error) {
        log('Log stream connection error');
        stopLogStream();
    };

    document.getElementById('btnStartLogs').disabled = true;
    document.getElementById('btnStopLogs').disabled = false;
}

function stopLogStream() {
    if (logStreamSource) {
        logStreamSource.close();
        logStreamSource = null;
        log('Log stream stopped');
    }

    document.getElementById('btnStartLogs').disabled = false;
    document.getElementById('btnStopLogs').disabled = true;
}

function log(message) {
    const console = document.getElementById('console');
    const line = document.createElement('div');
    line.textContent = message;
    console.appendChild(line);
    console.scrollTop = console.scrollHeight;
}

function clearLogs() {
    document.getElementById('console').innerHTML = '';
}

// --- Path Validation ---

async function validatePaths() {
    const paths = [
        { id: 'repoDir', label: 'Repo Directory' },
        { id: 'showDir', label: 'Show Directory' },
        { id: 'quarantineDir', label: 'Quarantine Directory' }
    ];

    let allValid = true;
    let messages = [];

    for (const pathInfo of paths) {
        const input = document.getElementById(pathInfo.id);
        const path = input.value.trim();

        if (!path) {
            messages.push(`❌ ${pathInfo.label}: No path entered`);
            input.style.borderColor = 'var(--accent-red)';
            allValid = false;
            continue;
        }

        try {
            const response = await fetch('/api/validate-path', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: path })
            });

            const result = await response.json();

            if (result.valid) {
                messages.push(`✓ ${pathInfo.label}: Valid`);
                input.style.borderColor = 'var(--success-text)';
            } else {
                messages.push(`❌ ${pathInfo.label}: ${result.error}`);
                input.style.borderColor = 'var(--accent-red)';
                allValid = false;
            }
        } catch (error) {
            messages.push(`❌ ${pathInfo.label}: Error validating`);
            input.style.borderColor = 'var(--accent-red)';
            allValid = false;
        }
    }

    // Display results in console
    log('--- Path Validation Results ---');
    messages.forEach(msg => log(msg));
    log('---');

    if (allValid) {
        showMessage('All paths are valid!', 'success');
    } else {
        showMessage('Some paths are invalid. Check the console for details.', 'error');
    }
}

// --- UI Helpers ---

function showMessage(message, type) {
    const toast = document.getElementById('messageToast');
    toast.textContent = message;
    toast.className = 'toast show toast-' + type;

    setTimeout(() => {
        toast.className = 'toast';
    }, 5000);
}

function setupDeployModeToggle() {
    const radios = document.querySelectorAll('input[name="deployMode"]');
    radios.forEach(radio => {
        radio.addEventListener('change', updateImageRefVisibility);
    });
}

function updateImageRefVisibility() {
    const deployMode = document.querySelector('input[name="deployMode"]:checked').value;
    const imageRefGroup = document.getElementById('imageRefGroup');

    if (deployMode === 'image') {
        imageRefGroup.style.display = 'block';
    } else {
        imageRefGroup.style.display = 'none';
    }
}
