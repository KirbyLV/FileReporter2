"""
Docker manager for controlling the main FileReporter2 application.
Uses docker-py SDK for better control than subprocess calls.
"""

import docker
import subprocess
import os
from typing import Generator, Optional
import time


class DockerManager:
    """Manages Docker operations for the FileReporter2 main application."""

    def __init__(self, compose_file: str = "/workspace/docker-compose.yml", service_name: str = "media"):
        self.compose_file = compose_file
        self.service_name = service_name
        self.compose_dir = os.path.dirname(compose_file)

        try:
            self.client = docker.from_env()
        except Exception as e:
            self.client = None
            print(f"Warning: Could not connect to Docker: {e}")

    def check_available(self) -> tuple[bool, str]:
        """
        Check if Docker daemon is available.
        Returns (is_available, message).
        """
        if self.client is None:
            return False, "Docker client not initialized"

        try:
            self.client.ping()
            return True, "Docker is available"
        except Exception as e:
            return False, f"Docker daemon not available: {str(e)}"

    def check_docker_compose(self) -> tuple[bool, str]:
        """
        Check if docker compose command is available.
        Returns (is_available, command_type).
        """
        # Try docker compose plugin first
        try:
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return True, "docker compose"
        except Exception:
            pass

        # Try standalone docker-compose
        try:
            result = subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return True, "docker-compose"
        except Exception:
            pass

        return False, "not found"

    def get_compose_cmd(self) -> Optional[list]:
        """Get the docker compose command (either 'docker compose' or 'docker-compose')."""
        is_available, cmd_type = self.check_docker_compose()
        if not is_available:
            return None

        if cmd_type == "docker compose":
            return ["docker", "compose"]
        else:
            return ["docker-compose"]

    def get_status(self) -> dict:
        """
        Get status of the main app container.
        Returns dict with keys: running (bool), container_id, status_text.
        """
        if self.client is None:
            return {
                "running": False,
                "container_id": None,
                "status_text": "Docker not available"
            }

        try:
            # Look for container with the service name label
            containers = self.client.containers.list(
                filters={"label": f"com.docker.compose.service={self.service_name}"}
            )

            if containers:
                container = containers[0]
                return {
                    "running": container.status == "running",
                    "container_id": container.short_id,
                    "status_text": f"Container {container.short_id}: {container.status}"
                }
            else:
                return {
                    "running": False,
                    "container_id": None,
                    "status_text": "Container not found"
                }
        except Exception as e:
            return {
                "running": False,
                "container_id": None,
                "status_text": f"Error checking status: {str(e)}"
            }

    def pull_image(self, image_ref: str) -> tuple[bool, str]:
        """
        Pull a Docker image.
        Returns (success, message).
        """
        if self.client is None:
            return False, "Docker not available"

        try:
            print(f"Pulling image: {image_ref}")
            self.client.images.pull(image_ref)
            return True, f"Successfully pulled {image_ref}"
        except Exception as e:
            return False, f"Error pulling image: {str(e)}"

    def compose_up(self, build: bool = False) -> tuple[bool, str]:
        """
        Start containers using docker compose up -d.
        Args:
            build: If True, build images before starting (for build mode)
        Returns (success, message).
        """
        compose_cmd = self.get_compose_cmd()
        if not compose_cmd:
            return False, "docker compose not available"

        if not os.path.exists(self.compose_file):
            return False, f"Compose file not found: {self.compose_file}"

        cmd = compose_cmd + ["up", "-d"]
        if build:
            cmd.append("--build")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.compose_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout for building
            )

            if result.returncode == 0:
                return True, "Container started successfully"
            else:
                error_output = result.stderr or result.stdout
                return False, f"Failed to start container: {error_output}"
        except subprocess.TimeoutExpired:
            return False, "Operation timed out (5 minute limit)"
        except Exception as e:
            return False, f"Error starting container: {str(e)}"

    def compose_down(self) -> tuple[bool, str]:
        """
        Stop and remove containers using docker compose down.
        Returns (success, message).
        """
        compose_cmd = self.get_compose_cmd()
        if not compose_cmd:
            return False, "docker compose not available"

        cmd = compose_cmd + ["down"]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.compose_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                return True, "Container stopped successfully"
            else:
                error_output = result.stderr or result.stdout
                return False, f"Failed to stop container: {error_output}"
        except Exception as e:
            return False, f"Error stopping container: {str(e)}"

    def compose_restart(self) -> tuple[bool, str]:
        """
        Restart containers using docker compose restart.
        Returns (success, message).
        """
        compose_cmd = self.get_compose_cmd()
        if not compose_cmd:
            return False, "docker compose not available"

        cmd = compose_cmd + ["restart"]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.compose_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                return True, "Container restarted successfully"
            else:
                error_output = result.stderr or result.stdout
                return False, f"Failed to restart container: {error_output}"
        except Exception as e:
            return False, f"Error restarting container: {str(e)}"

    def stream_logs(self, tail: int = 200) -> Generator[str, None, None]:
        """
        Stream container logs.
        Args:
            tail: Number of lines to show from the end
        Yields log lines as strings.
        """
        if self.client is None:
            yield "Error: Docker not available"
            return

        try:
            containers = self.client.containers.list(
                filters={"label": f"com.docker.compose.service={self.service_name}"}
            )

            if not containers:
                yield "No container found to stream logs from"
                return

            container = containers[0]

            # Stream logs
            for line in container.logs(stream=True, follow=True, tail=tail):
                try:
                    decoded_line = line.decode('utf-8').rstrip('\n')
                    yield decoded_line
                except Exception as e:
                    yield f"Error decoding log line: {str(e)}"

        except Exception as e:
            yield f"Error streaming logs: {str(e)}"

    def get_logs(self, tail: int = 200) -> str:
        """
        Get recent container logs (non-streaming).
        Args:
            tail: Number of lines to retrieve from the end
        Returns logs as a single string.
        """
        if self.client is None:
            return "Error: Docker not available"

        try:
            containers = self.client.containers.list(
                filters={"label": f"com.docker.compose.service={self.service_name}"}
            )

            if not containers:
                return "No container found"

            container = containers[0]
            logs = container.logs(tail=tail).decode('utf-8')
            return logs
        except Exception as e:
            return f"Error retrieving logs: {str(e)}"
