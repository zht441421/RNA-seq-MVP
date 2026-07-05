# Input Schema

The Phase 1 request schema describes a Bulk RNA-seq count matrix workflow.

## Required Fields

| Field | Type | Description |
| --- | --- | --- |
| `project_id` | string | Project identifier. |
| `omics_type` | string | Must be `bulk_rnaseq`. |
| `input_level` | string | Must be `count_matrix`. |
| `count_matrix_file` | string | Path or object key for count matrix. |
| `metadata_file` | string | Path or object key for metadata. |
| `sample_id_column` | string | Metadata column containing sample IDs. |
| `gene_id_column` | string | Count matrix column containing gene IDs. |
| `group_column` | string | Metadata column containing group labels. |
| `reference_group` | string | Reference group for contrast. |
| `test_group` | string | Test group for contrast. |

## Optional Fields

| Field | Type | Description |
| --- | --- | --- |
| `batch_column` | string or null | Metadata column containing batch labels. |
| `covariates` | array[string] | Additional covariates for the model. |
| `organism` | string or null | Organism name, for example `human` or `mouse`. |
| `gene_id_type` | string or null | Gene ID type, for example `ensembl` or `symbol`. |
| `annotation_version` | string or null | Annotation release or reference label. |
| `fdr_threshold` | number | FDR cutoff, default `0.05`. |
| `log2fc_threshold` | number | Absolute log2 fold-change cutoff, default `1.0`. |
| `validation_methods` | array[string] | Validation methods, default `["edgeR", "limma_voom"]`. |

## JSON Schema

```json
{
  "type": "object",
  "required": [
    "project_id",
    "omics_type",
    "input_level",
    "count_matrix_file",
    "metadata_file",
    "sample_id_column",
    "gene_id_column",
    "group_column",
    "reference_group",
    "test_group"
  ],
  "properties": {
    "project_id": { "type": "string" },
    "omics_type": { "type": "string", "const": "bulk_rnaseq" },
    "input_level": { "type": "string", "const": "count_matrix" },
    "count_matrix_file": { "type": "string" },
    "metadata_file": { "type": "string" },
    "sample_id_column": { "type": "string" },
    "gene_id_column": { "type": "string" },
    "group_column": { "type": "string" },
    "reference_group": { "type": "string" },
    "test_group": { "type": "string" },
    "batch_column": { "type": ["string", "null"] },
    "covariates": {
      "type": "array",
      "items": { "type": "string" },
      "default": []
    },
    "organism": { "type": ["string", "null"] },
    "gene_id_type": { "type": ["string", "null"] },
    "annotation_version": { "type": ["string", "null"] },
    "fdr_threshold": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "default": 0.05
    },
    "log2fc_threshold": {
      "type": "number",
      "minimum": 0,
      "default": 1.0
    },
    "validation_methods": {
      "type": "array",
      "items": { "type": "string" },
      "default": ["edgeR", "limma_voom"]
    }
  }
}
```

