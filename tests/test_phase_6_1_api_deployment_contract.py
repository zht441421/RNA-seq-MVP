from pathlib import Path


DEPLOYMENT_DOC = Path("docs/phase-6-1-api-deployment-contract.md")
COZE_CONTRACT_DOC = Path("docs/phase-6-1-coze-api-contract.md")


def _read_docs() -> str:
    return "\n".join(
        [
            DEPLOYMENT_DOC.read_text(encoding="utf-8"),
            COZE_CONTRACT_DOC.read_text(encoding="utf-8"),
        ]
    )


def test_phase_6_1_contract_docs_exist() -> None:
    assert DEPLOYMENT_DOC.is_file()
    assert COZE_CONTRACT_DOC.is_file()


def test_phase_6_1_docs_mention_required_deployment_settings() -> None:
    text = _read_docs()
    lowered = text.lower()

    for env_var in (
        "BIOINFO_INPUT_ROOT",
        "BIOINFO_OUTPUT_ROOT",
        "BIOINFO_TASK_STORE_PATH",
    ):
        assert env_var in text

    assert "uvicorn backend.app.main:app" in lowered
    assert "--host 127.0.0.1" in lowered
    assert "--port 8000" in lowered


def test_phase_6_1_docs_mention_runtime_requirements() -> None:
    text = _read_docs()
    lowered = text.lower()

    for required_text in (
        "minimal workflow runtime requirements",
        "minimal_cpm_log2fc",
        "exploratory cpm/log2fc",
        "preflight",
        "R",
        "Rscript",
        "BiocManager",
        "DESeq2",
    ):
        assert required_text in text or required_text.lower() in lowered


def test_phase_6_1_docs_mention_safety_boundaries_and_no_real_coze_call() -> None:
    lowered = _read_docs().lower()

    for required_text in (
        "no absolute paths",
        "no arbitrary filesystem reads",
        "no traceback/token/password/secret leakage",
        "relative api paths only",
        "no real coze api call in this phase",
    ):
        assert required_text in lowered
