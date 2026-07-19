from __future__ import annotations

import argparse
from pathlib import Path
import secrets
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SECRET_ROOT = ROOT / ".staging-secrets"
OPENSSL_CONFIG = ROOT / "deploy/staging/openssl-local.cnf"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare ignored local-only Phase 8.5 API key and TLS files."
    )
    parser.add_argument(
        "--rotate", action="store_true", help="Replace existing local-only materials."
    )
    args = parser.parse_args()
    try:
        prepare_local_materials(rotate=args.rotate)
    except RuntimeError as exc:
        print(f"Phase 8.5 local staging preparation failed: {exc}")
        return 1
    print("Phase 8.5 local-only staging materials are ready")
    print("No credential value was printed")
    return 0


def prepare_local_materials(*, rotate: bool = False) -> None:
    SECRET_ROOT.mkdir(parents=True, exist_ok=True)
    api_key = SECRET_ROOT / "api_key.txt"
    certificate = SECRET_ROOT / "staging.crt"
    private_key = SECRET_ROOT / "staging.key"
    if rotate or not api_key.is_file():
        api_key.write_text(secrets.token_urlsafe(32) + "\n", encoding="utf-8")
    if rotate or not (certificate.is_file() and private_key.is_file()):
        command = [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-sha256",
            "-nodes",
            "-days",
            "2",
            "-config",
            str(OPENSSL_CONFIG),
            "-keyout",
            str(private_key),
            "-out",
            str(certificate),
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError("OpenSSL could not create the local-only certificate")
    _restrict_permissions(api_key, certificate, private_key)


def _restrict_permissions(*paths: Path) -> None:
    if sys.platform == "win32":
        return
    for path in paths:
        path.chmod(0o600)


if __name__ == "__main__":
    raise SystemExit(main())
