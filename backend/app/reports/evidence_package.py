import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.config import get_settings
from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.models.project import Project
from backend.app.models.qc_report import QCReport, QCSeverity, QCStatus
from backend.app.models.reliability import ReliabilityAssessment
from backend.app.models.schemas import BulkRNASeqAnalysisConfig
from backend.app.services.file_inspector import inspect_file
from backend.app.services.result_interpretation import (
    build_result_interpretation,
    write_interpretation_summary_md,
)
from backend.app.utils.file_utils import resolve_input_path
from backend.app.utils.hashing import sha256_file


STANDARD_DIRECTORIES = [
    "04_main_results",
    "05_validation_results",
    "06_figures",
    "07_tables",
    "08_reproducible_code",
    "09_environment",
]

STANDARD_FILES = [
    ("01_summary.md", "report", "Human-readable summary"),
    ("02_qc_report.md", "report", "QC report"),
    ("03_method_selection.md", "report", "Method selection and user-confirmed plan"),
    ("10_audit_log.json", "audit_log", "Structured audit log"),
    ("11_reliability_report.md", "report", "Reliability report"),
    ("12_interpretation_summary.md", "report", "Guarded result interpretation summary"),
    ("manifest.json", "manifest", "Evidence package manifest"),
]

EXPECTED_ANALYSIS_FILES = [
    ("04_main_results/deseq2_results.csv", "main_result", "DESeq2 main result table"),
    ("05_validation_results/edger_results.csv", "validation_result", "edgeR validation result table"),
    ("05_validation_results/limma_voom_results.csv", "validation_result", "limma-voom validation result table"),
    ("05_validation_results/validation_comparison.csv", "validation_result", "Validation consistency comparison"),
    ("06_figures/pca_plot.png", "figure", "PCA plot"),
    ("06_figures/sample_distance_heatmap.png", "figure", "Sample distance heatmap"),
    ("06_figures/volcano_deseq2.png", "figure", "DESeq2 volcano plot"),
    ("06_figures/ma_plot_deseq2.png", "figure", "DESeq2 MA plot"),
    ("07_tables/normalized_counts.csv", "table", "Normalized counts"),
    ("07_tables/significant_genes_deseq2.csv", "table", "Significant DESeq2 genes"),
    ("09_environment/analysis_config.json", "environment", "Real R analysis config"),
    ("09_environment/r_session_info.txt", "environment", "R session info"),
    ("09_environment/run_status.json", "environment", "Real R run status"),
    ("09_environment/r_stdout.log", "environment", "R stdout log"),
    ("09_environment/r_stderr.log", "environment", "R stderr log"),
    ("09_environment/audit_log.json", "environment", "Runner-level audit log"),
]

REPRODUCIBILITY_FILES = [
    ("08_reproducible_code/README_REPRODUCE.md", "reproducibility", "Reproduction instructions"),
    ("08_reproducible_code/analysis_config.json", "reproducibility", "Analysis configuration used for replay"),
    ("08_reproducible_code/run_command.txt", "reproducibility", "Best-effort rerun command"),
    ("08_reproducible_code/docker_command.txt", "reproducibility", "Docker rerun command when available"),
    ("08_reproducible_code/input_hashes.json", "reproducibility", "Input and analysis config hashes"),
    ("08_reproducible_code/software_versions.json", "reproducibility", "Runtime software versions"),
]


def create_evidence_package(project_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
    artifact_root = ensure_artifact_dirs(project_id)
    config: BulkRNASeqAnalysisConfig = context["config"]
    plan: AnalysisPlan = context["plan"]
    qc_report: QCReport = context["qc_report"]
    reliability: ReliabilityAssessment = context["reliability"]
    run_result: Dict[str, Any] = context["run_result"]
    project: Optional[Project] = context.get("project")

    write_summary_md(artifact_root, config, plan, reliability, run_result)
    write_qc_report_md(artifact_root, qc_report)
    write_method_selection_md(artifact_root, plan, config)
    write_reliability_report_md(artifact_root, reliability, run_result)
    write_reproducibility_bundle(artifact_root, config, plan, reliability, run_result)
    interpretation = build_result_interpretation(
        project_id=project_id,
        reliability=reliability,
        result_summary={"status": run_result.get("status"), "run_status": run_result.get("run_status")},
        artifact_root=artifact_root,
    )
    write_interpretation_summary_md(artifact_root, interpretation)

    audit_payload = build_audit_log(
        artifact_root=artifact_root,
        project=project,
        config=config,
        plan=plan,
        qc_report=qc_report,
        reliability=reliability,
        run_result=run_result,
    )
    write_audit_log_json(artifact_root, audit_payload)
    manifest = build_manifest_json(project_id, artifact_root, config, plan, run_result)
    write_manifest_json(artifact_root, manifest)
    return manifest


def ensure_artifact_dirs(project_id: str) -> Path:
    artifact_root = get_settings().project_root / "artifacts" / project_id
    artifact_root.mkdir(parents=True, exist_ok=True)
    for directory in STANDARD_DIRECTORIES:
        (artifact_root / directory).mkdir(parents=True, exist_ok=True)
    return artifact_root


def write_summary_md(
    artifact_root: Path,
    config: BulkRNASeqAnalysisConfig,
    plan: AnalysisPlan,
    reliability: ReliabilityAssessment,
    run_result: Dict[str, Any],
) -> Path:
    run_mode = run_result.get("mode", "mock")
    grade = reliability.grade.value
    allowed_level = allowed_conclusion_level(grade)
    lines = [
        f"# Analysis Summary: {config.project_id}",
        "",
        f"- Project ID: {config.project_id}",
        f"- Omics type: {config.omics_type.value}",
        f"- Input level: {config.input_level.value}",
        f"- Analysis mode: {run_mode}",
        f"- Primary method: {plan.primary_method}",
        f"- Validation methods: {', '.join(plan.validation_methods)}",
        f"- Run status: {run_result.get('status', 'unknown')}",
        f"- Reliability grade: {grade}",
        f"- Allowed conclusion level: {allowed_level}",
        "",
        "## Conclusion Boundary",
        "",
        conclusion_boundary(grade),
    ]
    if grade in {"C", "D", "E"}:
        lines.extend(
            [
                "",
                "Current evidence is not sufficient for a strong scientific conclusion.",
            ]
        )
    path = artifact_root / "01_summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_qc_report_md(artifact_root: Path, qc_report: QCReport) -> Path:
    stop_conditions = _stop_conditions(qc_report)
    warnings = _warnings(qc_report)
    sample_alignment = qc_report.sample_alignment
    library_summary = qc_report.library_size_summary
    low_count_summary = qc_report.low_count_gene_summary
    batch_assessment = qc_report.batch_group_assessment
    count_validity = _check_status(qc_report, ["count_values_numeric", "count_values_non_negative", "count_values_integer_like"])
    lines = [
        f"# QC Report: {qc_report.project_id}",
        "",
        f"- File readability: {_check_status(qc_report, ['count_matrix_readable', 'metadata_readable'])}",
        f"- Metadata alignment: {_check_status(qc_report, ['sample_ids_aligned'])}",
        f"- Number of genes: {low_count_summary.total_genes if low_count_summary else 'unknown'}",
        f"- Number of samples: {sample_alignment.matrix_sample_count if sample_alignment else 'unknown'}",
        f"- Group sizes: {qc_report.group_counts}",
        f"- Count validity: {count_validity}",
        f"- QC gate status: {'pass' if qc_report.passed else 'fail'}",
        "",
        "## Library Size Summary",
        "",
        _library_size_text(library_summary),
        "",
        "## Low-Count Gene Summary",
        "",
        _low_count_text(low_count_summary),
        "",
        "## Batch / Group Confounding",
        "",
        batch_assessment.message if batch_assessment else "No batch column assessment was requested or available.",
        "",
        "## Stop Conditions",
        "",
    ]
    lines.extend(_bullet_list(stop_conditions, "None"))
    lines.extend(["", "## Warnings", ""])
    lines.extend(_bullet_list(warnings, "None"))
    lines.extend(["", "## Validation Issues", ""])
    if qc_report.validation_issues:
        for issue in qc_report.validation_issues:
            lines.extend(
                [
                    f"- `{issue.code}` ({issue.severity.value}): {issue.message}",
                    f"  Suggestion: {issue.suggestion}",
                    f"  Details: {json.dumps(issue.details, default=str)}",
                ]
            )
    else:
        lines.append("- None")
    path = artifact_root / "02_qc_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_method_selection_md(
    artifact_root: Path,
    plan: AnalysisPlan,
    config: BulkRNASeqAnalysisConfig,
) -> Path:
    lines = [
        f"# Method Selection: {plan.project_id}",
        "",
        f"- User-confirmed plan exists: {plan.confirmed}",
        f"- Primary method: {plan.primary_method}",
        f"- Validation methods: {', '.join(plan.validation_methods)}",
        f"- Normalization: {plan.normalization}",
        f"- Low-count filtering rule: total count >= {plan.low_count_filtering.min_total_count}; min samples = {plan.low_count_filtering.min_samples}",
        f"- FDR threshold: {plan.fdr_threshold}",
        f"- log2FC threshold: {plan.log2fc_threshold}",
        f"- Batch column: {config.batch_column}",
        f"- Covariates: {config.covariates}",
        f"- Design formula: `{plan.design_formula}`",
        "",
        "## Why User Confirmation Is Required",
        "",
        "The selected contrast, batch terms, covariates, and thresholds change the statistical model and must be explicitly confirmed before execution.",
        "",
        "## Risks and Assumptions",
        "",
        "- Count matrix inputs are assumed to be gene-level non-negative count-like values.",
        "- Metadata sample IDs are assumed to represent biological samples.",
        "- The backend does not infer biological causality.",
        "- Strong conclusions are allowed only when reliability grade permits them.",
    ]
    path = artifact_root / "03_method_selection.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_audit_log_json(artifact_root: Path, payload: Dict[str, Any]) -> Path:
    path = artifact_root / "10_audit_log.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def write_reliability_report_md(
    artifact_root: Path,
    reliability: ReliabilityAssessment,
    run_result: Dict[str, Any],
) -> Path:
    grade = reliability.grade.value
    lines = [
        f"# Reliability Report: {reliability.project_id}",
        "",
        f"- Final reliability grade: {grade}",
        f"- Strong conclusions allowed: {reliability.strong_conclusion_allowed}",
        f"- Allowed conclusion level: {allowed_conclusion_level(grade)}",
        "",
        "## Why This Grade Was Assigned",
        "",
    ]
    lines.extend(_bullet_list(reliability.rationale, "No rationale was recorded."))
    lines.extend(["", "## Conditions Satisfied", ""])
    lines.extend(_bullet_list(_conditions_satisfied(reliability, run_result), "No positive reliability conditions were recorded."))
    lines.extend(["", "## Conditions Failed", ""])
    lines.extend(_bullet_list(_conditions_failed(reliability, run_result), "No failed reliability conditions were recorded."))
    lines.extend(["", "## Stop Conditions", ""])
    lines.extend(_bullet_list(reliability.stop_conditions, "None"))
    lines.extend(["", "## Downgrade Conditions", ""])
    lines.extend(_bullet_list(reliability.downgrade_conditions, "None"))
    lines.extend(["", "## Required Improvements", ""])
    lines.extend(_bullet_list(_required_improvements(reliability, run_result), "No specific improvements are required by the current rule set."))
    if grade == "C" and _validation_missing(run_result):
        lines.extend(
            [
                "",
                "DESeq2 may have completed, but independent validation was not available; therefore conclusions remain exploratory.",
            ]
        )
    if grade == "E":
        lines.extend(
            [
                "",
                "No scientific conclusion should be generated from this run.",
            ]
        )
    path = artifact_root / "11_reliability_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_manifest_json(artifact_root: Path, manifest: Dict[str, Any]) -> Path:
    path = artifact_root / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return path


def write_reproducibility_bundle(
    artifact_root: Path,
    config: BulkRNASeqAnalysisConfig,
    plan: AnalysisPlan,
    reliability: ReliabilityAssessment,
    run_result: Dict[str, Any],
) -> None:
    reproducible_dir = artifact_root / "08_reproducible_code"
    reproducible_dir.mkdir(parents=True, exist_ok=True)
    analysis_config = _analysis_config_for_replay(config, run_result)
    analysis_config_path = reproducible_dir / "analysis_config.json"
    analysis_config_path.write_text(json.dumps(analysis_config, indent=2, default=str), encoding="utf-8")

    input_hashes = _input_hashes_payload(config, analysis_config_path)
    (reproducible_dir / "input_hashes.json").write_text(
        json.dumps(input_hashes, indent=2, default=str),
        encoding="utf-8",
    )

    software_versions = _software_versions_payload(artifact_root, run_result)
    (reproducible_dir / "software_versions.json").write_text(
        json.dumps(software_versions, indent=2, default=str),
        encoding="utf-8",
    )

    run_command = _run_command_text(artifact_root, run_result)
    docker_command = _docker_command_text(artifact_root, run_result)
    (reproducible_dir / "run_command.txt").write_text(run_command + "\n", encoding="utf-8")
    (reproducible_dir / "docker_command.txt").write_text(docker_command + "\n", encoding="utf-8")

    readme = _readme_reproduce_text(
        artifact_root=artifact_root,
        config=config,
        plan=plan,
        reliability=reliability,
        run_result=run_result,
        input_hashes=input_hashes,
        software_versions=software_versions,
        run_command=run_command,
        docker_command=docker_command,
    )
    (reproducible_dir / "README_REPRODUCE.md").write_text(readme, encoding="utf-8")


def _analysis_config_for_replay(config: BulkRNASeqAnalysisConfig, run_result: Dict[str, Any]) -> Dict[str, Any]:
    analysis_config = run_result.get("analysis_config")
    if isinstance(analysis_config, dict) and analysis_config:
        return analysis_config
    return _model_to_dict(config)


def _input_hashes_payload(config: BulkRNASeqAnalysisConfig, analysis_config_path: Path) -> Dict[str, Any]:
    payload = {
        "count_matrix_path": config.count_matrix_file,
        "count_matrix_sha256": _safe_sha256(config.count_matrix_file),
        "metadata_path": config.metadata_file,
        "metadata_sha256": _safe_sha256(config.metadata_file),
        "analysis_config_sha256": _safe_sha256(analysis_config_path),
    }
    warnings = []
    if payload["count_matrix_sha256"] is None:
        warnings.append("Count matrix file could not be hashed.")
    if payload["metadata_sha256"] is None:
        warnings.append("Metadata file could not be hashed.")
    if payload["analysis_config_sha256"] is None:
        warnings.append("Analysis config file could not be hashed.")
    if warnings:
        payload["warnings"] = warnings
    return payload


def _safe_sha256(path_value: Any) -> Optional[str]:
    try:
        path = path_value if isinstance(path_value, Path) else resolve_input_path(str(path_value))
        if not path.exists() or not path.is_file():
            return None
        return sha256_file(path)
    except Exception:
        return None


def _software_versions_payload(artifact_root: Path, run_result: Dict[str, Any]) -> Dict[str, Any]:
    run_status = run_result.get("run_status") or {}
    package_status = run_status.get("package_status") or {}
    packages = {}
    for package_name, package_info in package_status.items():
        if isinstance(package_info, dict):
            packages[package_name] = package_info.get("version")
        else:
            packages[package_name] = package_info
    return {
        "run_mode": run_result.get("mode", "mock"),
        "docker_image": run_result.get("docker_image") or run_status.get("docker_image"),
        "r_version": _r_version_from_session_info(artifact_root),
        "packages": packages,
    }


def _r_version_from_session_info(artifact_root: Path) -> Optional[str]:
    session_path = artifact_root / "09_environment" / "r_session_info.txt"
    if not session_path.exists():
        return None
    for line in session_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("R version "):
            parts = line.split()
            return parts[2] if len(parts) >= 3 else line.replace("R version ", "", 1)
    return None


def _run_command_text(artifact_root: Path, run_result: Dict[str, Any]) -> str:
    run_mode = run_result.get("mode", "mock")
    if run_mode == "docker_r":
        return _docker_command_text(artifact_root, run_result)
    if run_mode == "real_r":
        settings = get_settings()
        config_path = run_result.get("analysis_config_path") or str(artifact_root / "09_environment" / "analysis_config.json")
        return " ".join(
            [
                settings.rscript_executable,
                str(settings.project_root / "backend" / "app" / "scripts" / "r" / "bulk_rnaseq_de.R"),
                str(config_path),
            ]
        )
    return "Mock run: re-run the API workflow with RUN_MODE=mock; no R command is required."


def _docker_command_text(artifact_root: Path, run_result: Dict[str, Any]) -> str:
    if run_result.get("mode") != "docker_r":
        return "Not applicable: run mode is not docker_r."
    settings = get_settings()
    image = run_result.get("docker_image") or (run_result.get("run_status") or {}).get("docker_image") or settings.docker_r_image
    docker_executable = settings.docker_executable
    docker_workdir = settings.docker_workdir
    analysis_config_path = run_result.get("analysis_config_path") or str(artifact_root / "09_environment" / "analysis_config.json")
    try:
        relative_config = Path(analysis_config_path).resolve().relative_to(settings.project_root.resolve()).as_posix()
        container_config_path = f"{docker_workdir.rstrip('/')}/{relative_config}"
    except Exception:
        container_config_path = f"{docker_workdir.rstrip('/')}/artifacts/{artifact_root.name}/09_environment/analysis_config.json"
    return "\n".join(
        [
            f'{docker_executable} run --rm \\',
            f'  -v "{settings.project_root}:{docker_workdir}" \\',
            f"  -w {docker_workdir} \\",
            f"  {image} \\",
            f"  Rscript backend/app/scripts/r/bulk_rnaseq_de.R \\",
            f"  {container_config_path}",
        ]
    )


def _readme_reproduce_text(
    artifact_root: Path,
    config: BulkRNASeqAnalysisConfig,
    plan: AnalysisPlan,
    reliability: ReliabilityAssessment,
    run_result: Dict[str, Any],
    input_hashes: Dict[str, Any],
    software_versions: Dict[str, Any],
    run_command: str,
    docker_command: str,
) -> str:
    run_status = run_result.get("run_status") or {}
    warnings = run_status.get("warnings") or []
    errors = run_status.get("errors") or []
    lines = [
        f"# Reproduce Run: {config.project_id}",
        "",
        f"- Project ID: {config.project_id}",
        f"- Run mode: {run_result.get('mode', 'mock')}",
        f"- Primary method: {plan.primary_method}",
        f"- Validation methods: {', '.join(plan.validation_methods)}",
        f"- Count matrix path: {config.count_matrix_file}",
        f"- Metadata path: {config.metadata_file}",
        f"- Count matrix SHA256: {input_hashes.get('count_matrix_sha256')}",
        f"- Metadata SHA256: {input_hashes.get('metadata_sha256')}",
        f"- Analysis config SHA256: {input_hashes.get('analysis_config_sha256')}",
        f"- Docker image: {software_versions.get('docker_image')}",
        f"- R version: {software_versions.get('r_version')}",
        f"- Reliability grade: {reliability.grade.value}",
        "",
        "## R Package Versions",
        "",
    ]
    packages = software_versions.get("packages") or {}
    if packages:
        for package_name, version in packages.items():
            lines.append(f"- {package_name}: {version}")
    else:
        lines.append("- No R package versions were recorded for this run mode.")
    lines.extend(
        [
            "",
            "## Analysis Config Summary",
            "",
            f"- gene_id_column: {config.gene_id_column}",
            f"- sample_id_column: {config.sample_id_column}",
            f"- group_column: {config.group_column}",
            f"- reference_group: {config.reference_group}",
            f"- test_group: {config.test_group}",
            f"- batch_column: {config.batch_column}",
            f"- covariates: {config.covariates}",
            f"- fdr_threshold: {plan.fdr_threshold}",
            f"- log2fc_threshold: {plan.log2fc_threshold}",
            "",
            "## Rerun Command",
            "",
            "```bash",
            run_command,
            "```",
            "",
            "## Docker Command",
            "",
            "```bash",
            docker_command,
            "```",
            "",
            "## Output Directory",
            "",
            f"Original outputs are under `{artifact_root}`.",
            "For replay, write to a new output directory rather than overwriting the original artifact package.",
            "",
            "## Warnings",
            "",
        ]
    )
    lines.extend(_bullet_list([str(item) for item in warnings], "None"))
    lines.extend(["", "## Errors", ""])
    lines.extend(_bullet_list([str(item) for item in errors], "None"))
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "Replay is intended to reproduce the computational workflow and artifacts. It does not automatically create or upgrade scientific conclusions.",
            "Any interpretation must still follow the reliability grade, QC findings, validation consistency, and documented limitations.",
            "",
        ]
    )
    return "\n".join(lines)


def collect_existing_artifacts(artifact_root: Path) -> List[Dict[str, Any]]:
    if not artifact_root.exists():
        return []
    artifacts: List[Dict[str, Any]] = []
    for path in sorted(artifact_root.rglob("*")):
        if not path.is_file():
            continue
        artifacts.append(
            {
                "relative_path": _relative(path, artifact_root),
                "path": str(path),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return artifacts


def build_manifest_json(
    project_id: str,
    artifact_root: Path,
    config: BulkRNASeqAnalysisConfig,
    plan: AnalysisPlan,
    run_result: Dict[str, Any],
) -> Dict[str, Any]:
    files: List[Dict[str, Any]] = []
    for directory in STANDARD_DIRECTORIES:
        path = artifact_root / directory
        files.append(
            {
                "relative_path": directory + "/",
                "type": "directory",
                "status": "present" if path.exists() else "missing",
                "description": f"Evidence package directory: {directory}",
            }
        )
    for relative_path, artifact_type, description in STANDARD_FILES:
        path = artifact_root / relative_path
        status = "present" if path.exists() or relative_path == "manifest.json" else "missing"
        files.append(_manifest_entry(artifact_root, relative_path, artifact_type, status, description))
    for relative_path, artifact_type, description in REPRODUCIBILITY_FILES:
        status = _expected_artifact_status(artifact_root / relative_path, relative_path, run_result)
        files.append(_manifest_entry(artifact_root, relative_path, artifact_type, status, description))
    for relative_path, artifact_type, description in EXPECTED_ANALYSIS_FILES:
        status = _expected_artifact_status(artifact_root / relative_path, relative_path, run_result)
        files.append(_manifest_entry(artifact_root, relative_path, artifact_type, status, description))

    known_paths = {entry["relative_path"].rstrip("/") for entry in files}
    for artifact in collect_existing_artifacts(artifact_root):
        if artifact["relative_path"] in known_paths:
            continue
        files.append(
            {
                "relative_path": artifact["relative_path"],
                "type": "additional_artifact",
                "status": "present",
                "description": "Additional generated artifact",
                "sha256": artifact["sha256"],
                "size_bytes": artifact["size_bytes"],
            }
        )

    return {
        "project_id": project_id,
        "generated_at": _now_iso(),
        "artifact_root": str(artifact_root),
        "run_mode": run_result.get("mode", "mock"),
        "primary_method": plan.primary_method,
        "validation_methods": plan.validation_methods,
        "files": files,
    }


def build_audit_log(
    artifact_root: Path,
    project: Optional[Project],
    config: BulkRNASeqAnalysisConfig,
    plan: AnalysisPlan,
    qc_report: QCReport,
    reliability: ReliabilityAssessment,
    run_result: Dict[str, Any],
) -> Dict[str, Any]:
    count_info = _input_file_info(config.count_matrix_file)
    metadata_info = _input_file_info(config.metadata_file)
    run_status = _run_status_payload(run_result)
    return {
        "project_id": config.project_id,
        "created_at": project.created_at.isoformat() if project else _now_iso(),
        "omics_type": config.omics_type.value,
        "input_level": config.input_level.value,
        "run_mode": run_result.get("mode", "mock"),
        "input_files": {
            "count_matrix": count_info,
            "metadata": metadata_info,
        },
        "schema_mapping": {
            "gene_id_column": config.gene_id_column,
            "sample_id_column": config.sample_id_column,
            "group_column": config.group_column,
            "reference_group": config.reference_group,
            "test_group": config.test_group,
            "batch_column": config.batch_column,
            "covariates": config.covariates,
        },
        "methods": {
            "primary_method": plan.primary_method,
            "validation_methods": plan.validation_methods,
            "normalization": plan.normalization,
            "fdr_threshold": plan.fdr_threshold,
            "log2fc_threshold": plan.log2fc_threshold,
        },
        "qc": {
            "status": "pass" if qc_report.passed else "fail",
            "warnings": _warnings(qc_report),
            "stop_conditions": _stop_conditions(qc_report),
            "validation_issues": [_model_to_dict(issue) for issue in qc_report.validation_issues],
        },
        "run_status": run_status,
        "reliability": {
            "grade": reliability.grade.value,
            "reason": "; ".join(reliability.rationale),
            "allowed_conclusion_level": allowed_conclusion_level(reliability.grade.value),
        },
        "artifacts": collect_existing_artifacts(artifact_root),
        "environment": {
            "r_session_info": _r_session_info_path(run_result),
            "run_mode": run_result.get("mode", "mock"),
            "docker_image": run_result.get("docker_image") or (run_result.get("run_status") or {}).get("docker_image"),
            "docker_available": run_result.get("docker_available") or (run_result.get("run_status") or {}).get("docker_available"),
            "package_versions": _package_versions(run_result),
        },
    }


def build_evidence_manifest(
    config: BulkRNASeqAnalysisConfig,
    plan: AnalysisPlan,
    qc_report: QCReport,
    reliability: ReliabilityAssessment,
    run_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Backward-compatible structured manifest for older call sites."""
    return {
        "project_id": config.project_id,
        "inputs": _model_to_dict(config),
        "analysis_plan": _model_to_dict(plan),
        "qc_report": _model_to_dict(qc_report),
        "reliability": _model_to_dict(reliability),
        "run_result": run_result,
        "audit": {
            "execution_mode": run_result.get("mode", "mock"),
            "strong_conclusion_allowed": reliability.strong_conclusion_allowed,
            "note": "Conclusion strength is gated by reliability grade.",
        },
    }


def allowed_conclusion_level(grade: str) -> str:
    return {
        "A": "Statistical conclusions may be stated with limitations; causal language is prohibited.",
        "B": "Only cautious supportive conclusions are allowed.",
        "C": "Exploratory findings only.",
        "D": "Not recommended for formal conclusions.",
        "E": "No scientific conclusion.",
    }.get(grade, "No scientific conclusion.")


def conclusion_boundary(grade: str) -> str:
    return {
        "A": "Reliability grade A permits relatively strong statistical conclusions with explicit limitations, but not causal claims.",
        "B": "Reliability grade B permits cautious supportive conclusions with limitations.",
        "C": "Reliability grade C permits exploratory findings only.",
        "D": "Reliability grade D is not recommended for formal scientific conclusions.",
        "E": "Reliability grade E does not support scientific conclusions.",
    }.get(grade, "Conclusion level is unavailable.")


def _expected_artifact_status(path: Path, relative_path: str, run_result: Dict[str, Any]) -> str:
    run_mode = run_result.get("mode", "mock")
    if path.exists():
        return "present"
    if run_mode == "mock":
        return "not_applicable"
    primary_status = (run_result.get("run_status") or {}).get("primary_method_status")
    validation_status = (run_result.get("run_status") or {}).get("validation_method_status") or {}
    if relative_path.startswith("05_validation_results/edger") and validation_status.get("edgeR") == "skipped":
        return "not_applicable"
    if relative_path.startswith("05_validation_results/limma") and validation_status.get("limma_voom") == "skipped":
        return "not_applicable"
    if primary_status not in {"completed", "completed_with_warning"} and not relative_path.startswith("09_environment/"):
        return "missing"
    return "missing"


def _manifest_entry(
    artifact_root: Path,
    relative_path: str,
    artifact_type: str,
    status: str,
    description: str,
) -> Dict[str, Any]:
    path = artifact_root / relative_path
    entry: Dict[str, Any] = {
        "relative_path": relative_path,
        "type": artifact_type,
        "status": status,
        "description": description,
    }
    if status == "present" and path.exists() and path.is_file():
        entry["sha256"] = sha256_file(path)
        entry["size_bytes"] = path.stat().st_size
    return entry


def _input_file_info(file_path: str) -> Dict[str, Any]:
    try:
        inspection = inspect_file(file_path)
        return {
            "path": inspection.file_path,
            "hash": inspection.sha256,
            "rows": inspection.row_count,
            "columns": inspection.columns,
        }
    except Exception as exc:
        return {
            "path": file_path,
            "hash": None,
            "rows": None,
            "columns": [],
            "error": str(exc),
        }


def _run_status_payload(run_result: Dict[str, Any]) -> Dict[str, Any]:
    run_status = run_result.get("run_status") or {}
    return {
        "status": run_result.get("status"),
        "primary_method_status": run_status.get("primary_method_status", run_result.get("primary_result", {}).get("status")),
        "validation_method_status": run_status.get("validation_method_status", run_result.get("validation_status", {})),
    }


def _r_session_info_path(run_result: Dict[str, Any]) -> Optional[str]:
    run_status = run_result.get("run_status") or {}
    return run_status.get("r_session_info_path")


def _package_versions(run_result: Dict[str, Any]) -> Dict[str, Any]:
    run_status = run_result.get("run_status") or {}
    package_status = run_status.get("package_status") or {}
    versions: Dict[str, Any] = {}
    for package_name, package_info in package_status.items():
        if isinstance(package_info, dict):
            versions[package_name] = package_info.get("version")
        else:
            versions[package_name] = package_info
    return versions


def _check_status(qc_report: QCReport, check_names: List[str]) -> str:
    statuses = [
        check.status.value
        for check in qc_report.checks
        if check.name in check_names
    ]
    if not statuses:
        return "unknown"
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"


def _library_size_text(summary: Any) -> str:
    if not summary:
        return "Library size summary is unavailable."
    return (
        f"- Samples: {summary.sample_count}\n"
        f"- Minimum: {summary.minimum}\n"
        f"- Maximum: {summary.maximum}\n"
        f"- Mean: {summary.mean}\n"
        f"- Median: {summary.median}"
    )


def _low_count_text(summary: Any) -> str:
    if not summary:
        return "Low-count gene summary is unavailable."
    return (
        f"- Total genes: {summary.total_genes}\n"
        f"- Low-count genes: {summary.low_count_genes}\n"
        f"- Low-count fraction: {summary.low_count_fraction}\n"
        f"- Minimum total count rule: {summary.min_total_count}"
    )


def _stop_conditions(qc_report: QCReport) -> List[str]:
    return [
        check.message
        for check in qc_report.checks
        if check.status == QCStatus.FAIL and check.severity == QCSeverity.ERROR
    ]


def _warnings(qc_report: QCReport) -> List[str]:
    return [
        check.message
        for check in qc_report.checks
        if check.status == QCStatus.WARN or check.severity == QCSeverity.WARNING
    ]


def _conditions_satisfied(reliability: ReliabilityAssessment, run_result: Dict[str, Any]) -> List[str]:
    conditions = []
    run_status = run_result.get("run_status") or {}
    if run_status.get("primary_method_status") in {"completed", "completed_with_warning"}:
        conditions.append("Primary method completed.")
    if run_status.get("fdr_applied"):
        conditions.append("FDR was applied.")
    validation_status = run_status.get("validation_method_status") or {}
    completed = [method for method, status in validation_status.items() if status == "completed"]
    if completed:
        conditions.append(f"Validation completed for: {', '.join(completed)}.")
    if reliability.strong_conclusion_allowed:
        conditions.append("Reliability grade allows strong conclusions within documented boundaries.")
    return conditions


def _conditions_failed(reliability: ReliabilityAssessment, run_result: Dict[str, Any]) -> List[str]:
    conditions = []
    run_status = run_result.get("run_status") or {}
    if run_status.get("primary_method_status") == "failed":
        conditions.append("Primary method failed.")
    validation_status = run_status.get("validation_method_status") or {}
    failed_or_skipped = [method for method, status in validation_status.items() if status in {"failed", "skipped"}]
    if failed_or_skipped:
        conditions.append(f"Validation not completed for: {', '.join(failed_or_skipped)}.")
    conditions.extend(reliability.stop_conditions)
    conditions.extend(reliability.downgrade_conditions)
    return conditions


def _required_improvements(reliability: ReliabilityAssessment, run_result: Dict[str, Any]) -> List[str]:
    improvements = []
    run_status = run_result.get("run_status") or {}
    if run_status.get("primary_method_status") not in {"completed", "completed_with_warning"}:
        improvements.append("Resolve primary method execution failure and regenerate results.")
    if _validation_missing(run_result):
        improvements.append("Run at least one independent validation method and compute validation consistency.")
    if not reliability.strong_conclusion_allowed:
        improvements.append("Address stop or downgrade conditions until reliability grade reaches A or B.")
    return improvements


def _validation_missing(run_result: Dict[str, Any]) -> bool:
    run_status = run_result.get("run_status") or {}
    validation_status = run_status.get("validation_method_status") or {}
    if not validation_status:
        validation_status = (run_result.get("validation_status") or {}).get("validation_method_status") or {}
    return not any(status == "completed" for status in validation_status.values())


def _bullet_list(items: List[str], empty_text: str) -> List[str]:
    if not items:
        return [f"- {empty_text}"]
    return [f"- {item}" for item in items]


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_to_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
