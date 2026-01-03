"""
File browser for navigating the host filesystem from the web UI.
Provides API to list directories and navigate the filesystem.
"""

import os
import platform
from pathlib import Path
from typing import List, Dict, Optional


class FileBrowser:
    """Web-based file browser for selecting directories on the host."""

    def __init__(self, host_root: str = "/host"):
        """
        Initialize file browser.
        Args:
            host_root: Mount point for host filesystem in container
        """
        self.host_root = host_root
        self.system = platform.system()

    def get_start_paths(self) -> List[Dict[str, str]]:
        """
        Get common starting points based on the operating system.
        Returns list of dicts with 'name' and 'path' keys.
        """
        start_paths = []

        if self.system == "Darwin":  # macOS
            start_paths = [
                {"name": "Home", "path": os.path.join(self.host_root, "Users")},
                {"name": "Volumes", "path": os.path.join(self.host_root, "Volumes")},
                {"name": "Applications", "path": os.path.join(self.host_root, "Applications")},
            ]
        elif self.system == "Windows":
            # Windows paths in container
            start_paths = [
                {"name": "C:\\", "path": os.path.join(self.host_root, "c")},
                {"name": "Users", "path": os.path.join(self.host_root, "c", "Users")},
            ]
        else:  # Linux
            start_paths = [
                {"name": "Home", "path": os.path.join(self.host_root, "home")},
                {"name": "Root", "path": self.host_root},
                {"name": "Mnt", "path": os.path.join(self.host_root, "mnt")},
            ]

        # Filter to only existing paths
        return [p for p in start_paths if os.path.exists(p["path"])]

    def normalize_path(self, path: str) -> str:
        """
        Normalize a path to ensure it's within the host mount.
        Prevents directory traversal attacks.
        """
        # Convert to absolute path
        if not path.startswith(self.host_root):
            path = os.path.join(self.host_root, path.lstrip('/\\'))

        # Normalize and resolve
        path = os.path.normpath(path)
        path = os.path.abspath(path)

        # Ensure it's still within host_root
        if not path.startswith(self.host_root):
            return self.host_root

        return path

    def path_to_host_path(self, container_path: str) -> str:
        """
        Convert container path to host path (remove /host prefix).
        This is what gets stored in the configuration.
        """
        if container_path.startswith(self.host_root):
            host_path = container_path[len(self.host_root):]
            # Ensure we have a leading slash
            if not host_path.startswith('/') and not (len(host_path) > 1 and host_path[1] == ':'):
                host_path = '/' + host_path
            return host_path
        return container_path

    def host_path_to_path(self, host_path: str) -> str:
        """
        Convert host path to container path (add /host prefix).
        """
        if not host_path.startswith(self.host_root):
            return os.path.join(self.host_root, host_path.lstrip('/\\'))
        return host_path

    def list_directory(self, path: Optional[str] = None) -> Dict:
        """
        List contents of a directory.

        Args:
            path: Directory path to list. If None, returns start paths.

        Returns:
            Dict with keys:
                - current_path: Current directory path (container path)
                - current_path_host: Current directory path (host path, for display)
                - parent: Parent directory path (or None if at root)
                - directories: List of subdirectories (name, path pairs)
                - error: Error message if any
        """
        # If no path provided, return start paths
        if path is None:
            return {
                "current_path": self.host_root,
                "current_path_host": "/",
                "parent": None,
                "directories": self.get_start_paths(),
                "error": None
            }

        # Normalize and validate path
        normalized_path = self.normalize_path(path)

        # Check if path exists and is a directory
        if not os.path.exists(normalized_path):
            return {
                "current_path": self.host_root,
                "current_path_host": "/",
                "parent": None,
                "directories": self.get_start_paths(),
                "error": f"Path does not exist: {path}"
            }

        if not os.path.isdir(normalized_path):
            return {
                "current_path": os.path.dirname(normalized_path),
                "current_path_host": self.path_to_host_path(os.path.dirname(normalized_path)),
                "parent": None,
                "directories": [],
                "error": "Path is not a directory"
            }

        # Get parent directory
        parent = None
        if normalized_path != self.host_root:
            parent = os.path.dirname(normalized_path)

        # List subdirectories
        directories = []
        try:
            with os.scandir(normalized_path) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            directories.append({
                                "name": entry.name,
                                "path": entry.path
                            })
                    except PermissionError:
                        # Skip directories we can't access
                        continue
                    except Exception:
                        # Skip any other problematic entries
                        continue

            # Sort directories alphabetically
            directories.sort(key=lambda d: d["name"].lower())

        except PermissionError:
            return {
                "current_path": normalized_path,
                "current_path_host": self.path_to_host_path(normalized_path),
                "parent": parent,
                "directories": [],
                "error": "Permission denied"
            }
        except Exception as e:
            return {
                "current_path": normalized_path,
                "current_path_host": self.path_to_host_path(normalized_path),
                "parent": parent,
                "directories": [],
                "error": f"Error listing directory: {str(e)}"
            }

        return {
            "current_path": normalized_path,
            "current_path_host": self.path_to_host_path(normalized_path),
            "parent": parent,
            "directories": directories,
            "error": None
        }

    def validate_path(self, host_path: str) -> tuple[bool, str]:
        """
        Validate that a path exists and is accessible.

        Args:
            host_path: Path on host system (without /host prefix)

        Returns:
            (is_valid, error_message)
        """
        container_path = self.host_path_to_path(host_path)
        normalized_path = self.normalize_path(container_path)

        if not os.path.exists(normalized_path):
            return False, "Path does not exist"

        if not os.path.isdir(normalized_path):
            return False, "Path is not a directory"

        try:
            # Try to list directory to check permissions
            os.listdir(normalized_path)
            return True, ""
        except PermissionError:
            return False, "Permission denied"
        except Exception as e:
            return False, f"Error accessing path: {str(e)}"
