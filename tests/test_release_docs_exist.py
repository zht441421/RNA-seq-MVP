from pathlib import Path


def test_phase_1_release_docs_exist_and_define_boundaries() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    checklist = repo_root / "docs" / "15_phase_1_release_checklist.md"
    final_acceptance = repo_root / "docs" / "16_phase_1_final_acceptance.md"

    assert checklist.exists()
    assert final_acceptance.exists()

    checklist_text = checklist.read_text(encoding="utf-8")
    final_text = final_acceptance.read_text(encoding="utf-8")

    assert "Bulk RNA-seq count matrix + metadata" in checklist_text
    assert "single-cell RNA-seq" in checklist_text
    assert "clinical diagnosis" in checklist_text
    assert "Phase 1.13" in final_text
    assert "python scripts/acceptance_phase_1.py" in final_text
