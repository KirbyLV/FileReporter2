"""
Path validator for host filesystem access.
Validates that paths exist and are accessible on the host.
"""

import os


class FileBrowser:
    """Path validator for host filesystem."""

    def __init__(self, host_root: str = "/host"):
        """
        Initialize file browser.
        Args:
            host_root: Mount point for host filesystem in container
        """
        self.host_root = host_root

    def validate_path(self, host_path: str) -> tuple[bool, str]:
        """
        Validate that a path exists and is accessible.

        Args:
            host_path: Path on host system (e.g., /Users/name/Documents)

        Returns:
            (is_valid, error_message)
        """
        # Convert host path to container path
        # Host path: /Users/name/Documents -> Container path: /host/Users/name/Documents
        container_path = os.path.join(self.host_root, host_path.lstrip('/\\'))

        if not os.path.exists(container_path):
            return False, f"Path does not exist"

        if not os.path.isdir(container_path):
            return False, "Path is not a directory"

        try:
            # Try to list directory to check permissions
            os.listdir(container_path)
            return True, ""
        except PermissionError:
            return False, "Permission denied"
        except Exception as e:
            return False, f"Error accessing path: {str(e)}"
