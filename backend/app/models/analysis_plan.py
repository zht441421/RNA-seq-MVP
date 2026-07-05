from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.models.project import utc_now


class LowCountFilteringRule(BaseModel):
    min_total_count: int = 10
    min_samples: int = 2
    description: str = "Keep genes with sufficient total count in at least a minimal number of samples."


class AnalysisPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: f"plan_{uuid4().hex}")
    project_id: str
    primary_method: str = "DESeq2"
    validation_methods: List[str] = Field(default_factory=lambda: ["edgeR", "limma_voom"])
    normalization: str = "DESeq2_size_factor"
    design_formula: str
    fdr_threshold: float = 0.05
    log2fc_threshold: float = 1.0
    low_count_filtering: LowCountFilteringRule = Field(default_factory=LowCountFilteringRule)
    enrichment: Optional[str] = None
    requires_user_confirmation: bool = True
    confirmed: bool = False
    notes: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)

