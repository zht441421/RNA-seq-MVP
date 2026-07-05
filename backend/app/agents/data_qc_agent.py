from backend.app.models.qc_report import QCReport
from backend.app.models.schemas import BulkRNASeqAnalysisConfig
from backend.app.services.qc_service import run_qc


class DataQCAgent:
    name = "data_qc_agent"

    def run(self, config: BulkRNASeqAnalysisConfig) -> QCReport:
        return run_qc(config)

