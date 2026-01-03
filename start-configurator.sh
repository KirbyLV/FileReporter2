#!/bin/bash

# Start the FileReporter2 Web Configurator
# This script runs the configurator in a Docker container

echo "Starting FileReporter2 Web Configurator..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

# Check if configurator container is already running
if docker ps --format '{{.Names}}' | grep -q "filereporter2-config"; then
    echo "Configurator is already running."
    echo "Open http://localhost:8009 in your browser"
    exit 0
fi

# Remove old container if it exists but is stopped
docker rm filereporter2-config > /dev/null 2>&1

# Run the configurator container
docker run -d \
    -p 8009:8009 \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$(pwd)/config:/config" \
    -v "$(pwd):/workspace" \
    -v /:/host:ro \
    --name filereporter2-config \
    --restart unless-stopped \
    jspodick/filereporter2-configurator:latest

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Configurator started successfully!"
    echo ""
    echo "Open http://localhost:8009 in your browser to configure FileReporter2"
    echo ""
    echo "To stop the configurator:"
    echo "  docker stop filereporter2-config"
    echo ""
    echo "To view logs:"
    echo "  docker logs -f filereporter2-config"
else
    echo ""
    echo "❌ Failed to start configurator"
    echo "Trying to build locally..."
    echo ""

    # Try building locally as fallback
    cd configurator-web
    docker-compose up -d

    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Configurator started successfully (built locally)!"
        echo ""
        echo "Open http://localhost:8009 in your browser"
    else
        echo "❌ Failed to start configurator. Check Docker Desktop is running."
        exit 1
    fi
fi
