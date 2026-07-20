import json
import subprocess

import pytest

from backend.app.services import formal_de_preflight
from backend.app.services.formal_de_preflight import CommandResult


FORBIDDEN_PUBLIC_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "traceback",
    "token",
    "password",
    "secret",
)


def _assert_no_forbidden_public_fragments(body: object) -> None:
    text = json.dumps(body, sort_keys=True).lower()
    assert all(fragment not in text for fragment in FORBIDDEN_PUBLIC_FRAGMENTS)


def _version_result(command: list[str]) -> CommandResult:
    if command[0] == "R":
        return CommandResult(
            args=command,
            returncode=0,
            stdout='R version 4.4.1 (2024-06-14) -- "Race for Your Life"\n',
        )
    return CommandResult(
        args=command,
        returncode=0,
        stderr="Rscript (R) version 4.4.1 (2024-06-14)\n",
    )


def _patch_preflight_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    r_available: bool = True,
    rscript_available: bool = True,
    biocmanager_available: bool = True,
    deseq2_available: bool = True,
) -> None:
    monkeypatch.setattr(
        formal_de_preflight,
        "check_executable_available",
        lambda name: r_available if name == "R" else rscript_available,
    )
    monkeypatch.setattr(formal_de_preflight, "run_command_safely", _version_result)
    monkeypatch.setattr(
        formal_de_preflight,
        "check_r_package_available",
        lambda package_name: (
            biocmanager_available
            if package_name == "BiocManager"
            else deseq2_available
        ),
    )
    monkeypatch.setattr(
        formal_de_preflight,
        "check_controlled_runtime_script",
        lambda: (
            deseq2_available,
            {
                "Bioconductor": "3.16",
                "BiocManager": "1.30.20",
                "BiocVersion": "3.16.0",
                "DESeq2": "1.38.3",
                "SummarizedExperiment": "1.28.0",
                "S4Vectors": "0.36.1",
                "IRanges": "2.32.0",
                "BiocGenerics": "0.44.0",
            },
        ),
    )
    monkeypatch.setattr(
        formal_de_preflight, "check_runtime_directories_writable", lambda: True
    )


def test_missing_r_returns_ready_false(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_preflight_environment(monkeypatch, r_available=False)

    result = formal_de_preflight.run_deseq2_preflight()

    assert result["r_available"] is False
    assert result["rscript_available"] is True
    assert result["ready"] is False
    assert "R executable is not available." in result["errors"]
    assert "R --version" not in result["commands_checked"]
    _assert_no_forbidden_public_fragments(result)


def test_missing_rscript_returns_ready_false(monkeypatch: pytest.MonkeyPatch) -> None:
    called_packages: list[str] = []
    _patch_preflight_environment(monkeypatch, rscript_available=False)
    monkeypatch.setattr(
        formal_de_preflight,
        "check_r_package_available",
        lambda package_name: called_packages.append(package_name) or True,
    )

    result = formal_de_preflight.run_deseq2_preflight()

    assert result["r_available"] is True
    assert result["rscript_available"] is False
    assert result["biocmanager_available"] is False
    assert result["deseq2_available"] is False
    assert result["ready"] is False
    assert called_packages == []
    assert "Rscript executable is not available." in result["errors"]
    _assert_no_forbidden_public_fragments(result)


def test_available_r_and_rscript_versions_are_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_preflight_environment(
        monkeypatch,
        biocmanager_available=False,
        deseq2_available=False,
    )

    result = formal_de_preflight.run_deseq2_preflight()

    assert result["r_available"] is True
    assert result["rscript_available"] is True
    assert result["r_version"] == "4.4.1"
    assert result["rscript_version"] == "4.4.1"
    assert result["ready"] is False


def test_biocmanager_availability_is_detected_with_monkeypatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_preflight_environment(
        monkeypatch,
        biocmanager_available=True,
        deseq2_available=False,
    )

    result = formal_de_preflight.run_deseq2_preflight()

    assert result["biocmanager_available"] is True
    assert result["deseq2_available"] is False
    assert result["ready"] is False


def test_deseq2_availability_is_detected_with_monkeypatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_preflight_environment(monkeypatch)

    result = formal_de_preflight.run_deseq2_preflight()

    assert result["biocmanager_available"] is True
    assert result["deseq2_available"] is True
    assert result["ready"] is True


@pytest.mark.parametrize(
    (
        "r_available",
        "rscript_available",
        "biocmanager_available",
        "deseq2_available",
        "expected_ready",
    ),
    [
        (True, True, True, True, True),
        (False, True, True, True, False),
        (True, False, True, True, False),
        (True, True, False, True, False),
        (True, True, True, False, False),
    ],
)
def test_ready_is_true_only_when_required_components_are_available(
    monkeypatch: pytest.MonkeyPatch,
    r_available: bool,
    rscript_available: bool,
    biocmanager_available: bool,
    deseq2_available: bool,
    expected_ready: bool,
) -> None:
    _patch_preflight_environment(
        monkeypatch,
        r_available=r_available,
        rscript_available=rscript_available,
        biocmanager_available=biocmanager_available,
        deseq2_available=deseq2_available,
    )

    result = formal_de_preflight.run_deseq2_preflight()

    assert result["ready"] is expected_ready


def test_run_command_safely_uses_list_args_and_disables_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    class Completed:
        returncode = 0
        stdout = "R version 4.4.1\n"
        stderr = ""

    def fake_run(args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return Completed()

    monkeypatch.setattr(formal_de_preflight.subprocess, "run", fake_run)

    result = formal_de_preflight.run_command_safely(["R", "--version"])

    assert result.returncode == 0
    assert calls[0]["args"] == ["R", "--version"]
    assert isinstance(calls[0]["args"], list)
    assert calls[0]["kwargs"]["shell"] is False
    assert calls[0]["kwargs"]["timeout"] == 20


def test_timeout_errors_are_handled_safely(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args, timeout=kwargs["timeout"])

    monkeypatch.setattr(formal_de_preflight.subprocess, "run", fake_run)

    result = formal_de_preflight.run_command_safely(["Rscript", "--version"])

    assert result.returncode is None
    assert result.timed_out is True
    assert result.error == "Command timed out."
    _assert_no_forbidden_public_fragments(result.as_dict())


def test_command_output_is_sanitized_before_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Completed:
        returncode = 1
        stdout = r"D:\private\token.txt /home/user/password traceback"
        stderr = r"C:\private\secret.txt /mnt/data/token"

    monkeypatch.setattr(
        formal_de_preflight.subprocess,
        "run",
        lambda args, **kwargs: Completed(),
    )

    result = formal_de_preflight.run_command_safely(["Rscript", "--version"])

    _assert_no_forbidden_public_fragments(result.as_dict())


def test_check_r_package_available_uses_safe_rscript_expression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run_command(args: list[str], timeout_seconds: int = 10) -> CommandResult:
        calls.append(args)
        return CommandResult(args=args, returncode=0)

    monkeypatch.setattr(formal_de_preflight, "run_command_safely", fake_run_command)

    assert formal_de_preflight.check_r_package_available("DESeq2") is True
    assert calls == [
        [
            "Rscript",
            "--vanilla",
            "-e",
            'if (requireNamespace("DESeq2", quietly = TRUE)) quit(status = 0) else quit(status = 1)',
        ]
    ]


def test_public_preflight_payload_does_not_expose_sensitive_fragments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_preflight_environment(
        monkeypatch,
        biocmanager_available=False,
        deseq2_available=False,
    )

    result = formal_de_preflight.run_deseq2_preflight()

    _assert_no_forbidden_public_fragments(result)
