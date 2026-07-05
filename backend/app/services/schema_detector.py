from typing import Any, Dict, List, Optional

from backend.app.models.schemas import FileInspection


SAMPLE_ID_NAMES = ("sample_id", "sample", "sampleid", "sample_name", "run", "library")
GROUP_NAMES = ("group", "condition", "treatment", "phenotype", "case_control", "class")
GENE_ID_NAMES = ("gene_id", "gene", "geneid", "ensembl", "feature_id", "symbol")


def detect_schema(count_matrix: FileInspection, metadata: FileInspection) -> Dict[str, Any]:
    sample_id_candidates = _rank_columns(metadata.columns, SAMPLE_ID_NAMES)
    group_candidates = [
        column
        for column in _rank_columns(metadata.columns, GROUP_NAMES)
        if column not in sample_id_candidates[:1]
    ]
    gene_id_candidates = _rank_columns(count_matrix.columns, GENE_ID_NAMES)
    gene_id_column = gene_id_candidates[0] if gene_id_candidates else _first_column(count_matrix.columns)
    sample_columns = _detect_count_sample_columns(count_matrix, gene_id_column)

    return {
        "metadata": {
            "sample_id_column_candidates": sample_id_candidates,
            "group_column_candidates": group_candidates,
            "all_columns": metadata.columns,
        },
        "count_matrix": {
            "gene_id_column_candidates": gene_id_candidates or ([gene_id_column] if gene_id_column else []),
            "sample_columns": sample_columns,
            "all_columns": count_matrix.columns,
        },
        "recommended": {
            "sample_id_column": sample_id_candidates[0] if sample_id_candidates else None,
            "group_column": group_candidates[0] if group_candidates else None,
            "gene_id_column": gene_id_column,
        },
    }


def _rank_columns(columns: List[str], preferred_names: tuple[str, ...]) -> List[str]:
    scored = []
    for index, column in enumerate(columns):
        normalized = _normalize(column)
        score = 0
        if normalized in preferred_names:
            score += 100
        if any(name in normalized for name in preferred_names):
            score += 50
        scored.append((score, -index, column))
    return [column for score, _, column in sorted(scored, reverse=True) if score > 0]


def _first_column(columns: List[str]) -> Optional[str]:
    return columns[0] if columns else None


def _detect_count_sample_columns(count_matrix: FileInspection, gene_id_column: Optional[str]) -> List[str]:
    if not gene_id_column:
        return []
    return [column for column in count_matrix.columns if column != gene_id_column]


def _normalize(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")

