import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run or execute a Docker replay from an evidence artifact package."
    )
    parser.add_argument("artifact", help="Artifact project id or artifact directory path.")
    parser.add_argument("--execute", action="store_true", help="Actually run Docker. Default is dry-run only.")
    parser.add_argument("--docker-executable", default=os.environ.get("DOCKER_EXECUTABLE", "docker"))
    parser.add_argument("--docker-workdir", default=os.environ.get("DOCKER_WORKDIR", "/workspace"))
    parser.add_argument("--docker-image", default=os.environ.get("DOCKER_R_IMAGE"))
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    artifact_root = resolve_artifact_root(repo_root, args.artifact)
    reproducible_config_path = artifact_root / "08_reproducible_code" / "analysis_config.json"
    if not reproducible_config_path.exists():
        print(f"Missing reproducible analysis config: {reproducible_config_path}", file=sys.stderr)
        return 2

    analysis_config = json.loads(reproducible_config_path.read_text(encoding="utf-8"))
    software_versions = read_json(artifact_root / "08_reproducible_code" / "software_versions.json")
    image = args.docker_image or software_versions.get("docker_image") or "bioinformatics-agent-r-bulk-rnaseq:0.1"

    replay_id = replay_project_id(artifact_root.name)
    replay_root = repo_root / "artifacts" / replay_id
    replay_config = dict(analysis_config)
    replay_config["project_id"] = replay_id
    replay_config["output_dir"] = f"{args.docker_workdir.rstrip('/')}/artifacts/{replay_id}"
    replay_config_path = replay_root / "09_environment" / "analysis_config.json"
    container_config_path = f"{args.docker_workdir.rstrip('/')}/artifacts/{replay_id}/09_environment/analysis_config.json"
    command = docker_command(
        docker_executable=args.docker_executable,
        repo_root=repo_root,
        docker_workdir=args.docker_workdir,
        image=image,
        container_config_path=container_config_path,
    )

    print("Replay source artifact:")
    print(f"  {artifact_root}")
    print("Replay output artifact:")
    print(f"  {replay_root}")
    print("Docker command:")
    print(format_command(command))

    if not args.execute:
        print("Dry run only. No files were written and Docker was not executed.")
        print("Pass --execute to write the replay config and run the command.")
        return 0

    replay_config_path.parent.mkdir(parents=True, exist_ok=True)
    replay_config_path.write_text(json.dumps(replay_config, indent=2), encoding="utf-8")
    print(f"Wrote replay analysis config: {replay_config_path}")
    completed = subprocess.run(command, check=False)
    return completed.returncode


def resolve_artifact_root(repo_root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.exists():
        return candidate.resolve()
    return (repo_root / "artifacts" / value).resolve()


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def replay_project_id(project_id: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{project_id}_replay_{timestamp}"


def docker_command(
    docker_executable: str,
    repo_root: Path,
    docker_workdir: str,
    image: str,
    container_config_path: str,
) -> List[str]:
    return [
        docker_executable,
        "run",
        "--rm",
        "-v",
        f"{repo_root}:{docker_workdir}",
        "-w",
        docker_workdir,
        image,
        "Rscript",
        "backend/app/scripts/r/bulk_rnaseq_de.R",
        container_config_path,
    ]


def format_command(command: List[str]) -> str:
    return " ".join(quote_part(part) for part in command)


def quote_part(part: str) -> str:
    if any(character.isspace() for character in part):
        return f'"{part}"'
    return part


if __name__ == "__main__":
    sys.exit(main())
