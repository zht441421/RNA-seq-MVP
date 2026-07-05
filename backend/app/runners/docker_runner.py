from typing import Dict, List


class DockerRunner:
    """Placeholder for future isolated command execution."""

    def run(self, image: str, command: List[str], mounts: Dict[str, str] = None) -> Dict[str, object]:
        return {
            "mode": "mock",
            "image": image,
            "command": command,
            "mounts": mounts or {},
            "status": "not_executed",
            "note": "Docker execution is not enabled in Phase 1.",
        }

