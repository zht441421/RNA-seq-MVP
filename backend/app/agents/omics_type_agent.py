from typing import Dict


class OmicsTypeAgent:
    name = "omics_type_agent"

    def infer(self, file_context: Dict[str, str]) -> Dict[str, str]:
        return {
            "omics_type": "bulk_rnaseq",
            "input_level": "count_matrix",
            "confidence": "placeholder",
            "note": "Phase 1 supports only Bulk RNA-seq count matrices.",
        }

