"""
Docker Compose file generator for FileReporter2.
Ported from the legacy Tkinter configurator.
"""

import os

DEFAULT_SHEET_NAME = "Media Repo Inventory"

COMPOSE_IMAGE_TEMPLATE = """services:
  media:
    image: {image_ref}
    ports:
      - "8008:8008"
    environment:
      REPO_DIR: /repo
      SHOW_MEDIA_DIR: /repo_show
      QUARANTINE_DIR: /repo_quarantine
      CONFIG_DIR: /config
      GOOGLE_SERVICE_ACCOUNT_JSON: /config/google-service-account.json
      GOOGLE_SHEET_NAME: {sheet_name}
    volumes:
      - "{repo_host}:/repo:rw"
      - "{show_host}:/repo_show:rw"
      - "{quarantine_host}:/repo_quarantine:rw"
      - "./config:/config:rw"
"""

COMPOSE_BUILD_TEMPLATE = """services:
  media:
    build: .
    ports:
      - "8008:8008"
    environment:
      REPO_DIR: /repo
      SHOW_MEDIA_DIR: /repo_show
      QUARANTINE_DIR: /repo_quarantine
      CONFIG_DIR: /config
      GOOGLE_SERVICE_ACCOUNT_JSON: /config/google-service-account.json
      GOOGLE_SHEET_NAME: {sheet_name}
    volumes:
      - "{repo_host}:/repo:rw"
      - "{show_host}:/repo_show:rw"
      - "{quarantine_host}:/repo_quarantine:rw"
      - "./config:/config:rw"
"""


class ComposeGenerator:
    """Generates docker-compose.yml files for the main FileReporter2 application."""

    def __init__(self, workspace_path: str = "/workspace"):
        self.workspace_path = workspace_path

    def validate_config(self, config: dict) -> tuple[bool, str]:
        """
        Validate configuration before generating compose file.
        Returns (is_valid, error_message).
        """
        required_fields = ['repo_dir', 'show_dir', 'quarantine_dir', 'sheet_name']

        for field in required_fields:
            if not config.get(field, '').strip():
                return False, f"Missing required field: {field}"

        # If using prebuilt image mode, validate image reference
        if config.get('deploy_mode') == 'image':
            if not config.get('image_ref', '').strip():
                return False, "Image reference required when using prebuilt image mode"

        return True, ""

    def generate(self, config: dict) -> tuple[bool, str, str]:
        """
        Generate docker-compose.yml content from configuration.

        Args:
            config: Configuration dictionary with keys:
                - repo_dir: Host path for repo directory
                - show_dir: Host path for show directory
                - quarantine_dir: Host path for quarantine directory
                - sheet_name: Google Sheet name
                - deploy_mode: "image" or "build"
                - image_ref: Docker image reference (if deploy_mode is "image")

        Returns:
            (success, compose_content, error_message)
        """
        # Validate configuration
        is_valid, error_msg = self.validate_config(config)
        if not is_valid:
            return False, "", error_msg

        # Select template based on deploy mode
        deploy_mode = config.get('deploy_mode', 'image')
        if deploy_mode == 'image':
            template = COMPOSE_IMAGE_TEMPLATE
        else:
            template = COMPOSE_BUILD_TEMPLATE

        # Escape sheet name for YAML
        sheet_name = config.get('sheet_name', DEFAULT_SHEET_NAME).replace('"', '\\"')

        # Generate compose content
        try:
            compose_content = template.format(
                image_ref=config.get('image_ref', 'jspodick/filereporter2:latest'),
                repo_host=config.get('repo_dir'),
                show_host=config.get('show_dir'),
                quarantine_host=config.get('quarantine_dir'),
                sheet_name=sheet_name
            )
            return True, compose_content, ""
        except Exception as e:
            return False, "", f"Error generating compose file: {str(e)}"

    def write_compose_file(self, config: dict, output_path: str = None) -> tuple[bool, str]:
        """
        Generate and write docker-compose.yml file.

        Args:
            config: Configuration dictionary
            output_path: Optional custom output path. Defaults to workspace_path/docker-compose.yml

        Returns:
            (success, error_message)
        """
        success, content, error_msg = self.generate(config)
        if not success:
            return False, error_msg

        if output_path is None:
            output_path = os.path.join(self.workspace_path, "docker-compose.yml")

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, ""
        except Exception as e:
            return False, f"Error writing compose file: {str(e)}"
