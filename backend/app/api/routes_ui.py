from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter(tags=["ui"])


@router.get("/ui", response_class=HTMLResponse)
def local_ui() -> HTMLResponse:
    return HTMLResponse(_html())


def _html() -> str:
    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Bulk RNA-seq Mock Workflow</title>
  <style>
    :root {
      color-scheme: light;
      --border: #d4d7de;
      --muted: #626b7a;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --accent: #155eef;
      --danger: #b42318;
      --warn-bg: #fff4ed;
    }
    body {
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: var(--bg);
      color: #172033;
    }
    header {
      padding: 20px 28px;
      border-bottom: 1px solid var(--border);
      background: var(--panel);
    }
    h1 {
      margin: 0 0 6px;
      font-size: 24px;
      letter-spacing: 0;
    }
    main {
      max-width: 1180px;
      margin: 0 auto;
      padding: 22px;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 16px;
    }
    h2 {
      margin: 0 0 14px;
      font-size: 18px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }
    label {
      display: flex;
      flex-direction: column;
      gap: 5px;
      font-size: 13px;
      color: var(--muted);
    }
    input, select {
      min-height: 36px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 7px 9px;
      font-size: 14px;
      color: #172033;
      background: #fff;
    }
    input[type="checkbox"] {
      min-height: auto;
      width: 18px;
      height: 18px;
    }
    .inline {
      flex-direction: row;
      align-items: center;
      color: #172033;
    }
    button {
      margin-top: 14px;
      border: 0;
      border-radius: 6px;
      background: var(--accent);
      color: #fff;
      padding: 9px 14px;
      font-size: 14px;
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      background: #111827;
      color: #e5e7eb;
      border-radius: 6px;
      padding: 12px;
      max-height: 360px;
      overflow: auto;
      font-size: 12px;
    }
    .summary {
      margin-top: 12px;
      padding: 10px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: #fafafa;
    }
    .danger {
      display: none;
      margin: 12px 0;
      padding: 12px;
      border: 1px solid #fda29b;
      border-radius: 6px;
      background: var(--warn-bg);
      color: var(--danger);
      font-weight: 700;
    }
    .warning {
      border-color: #fdb022;
      background: #fffaeb;
      color: #93370d;
    }
    .artifact-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
      font-size: 13px;
    }
    .artifact-table th,
    .artifact-table td {
      border: 1px solid var(--border);
      padding: 7px 8px;
      text-align: left;
      vertical-align: top;
    }
    .artifact-table th {
      background: #f3f4f6;
    }
    .status-present {
      color: #067647;
      font-weight: 700;
    }
    .status-missing {
      color: var(--danger);
      font-weight: 700;
    }
    .issues {
      margin-top: 10px;
      display: grid;
      gap: 8px;
    }
    .issue {
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 9px;
      background: #fafafa;
    }
    .issue-error {
      border-color: #fda29b;
      background: #fff4ed;
    }
    .issue-warning {
      border-color: #fdb022;
      background: #fffaeb;
    }
    .issue-code {
      font-weight: 700;
    }
    .muted {
      color: var(--muted);
      font-size: 14px;
    }
    .markdown {
      background: #fafafa;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px;
      white-space: pre-wrap;
      margin-top: 10px;
    }
  </style>
</head>
<body>
  <header>
    <h1>Bulk RNA-seq Mock Workflow</h1>
    <div class="muted">Local UI for exercising the existing /coze API. No real Coze upload is used.</div>
  </header>
  <main>
    <section>
      <h2>Step 1: Create Project</h2>
      <div class="grid">
        <label>project_name <input id="project_name" value="demo_bulk_rnaseq" /></label>
        <label>organism <input id="organism" value="human" /></label>
        <label>gene_id_type <input id="gene_id_type" value="symbol" /></label>
        <label>annotation_version <input id="annotation_version" value="unknown" /></label>
      </div>
      <button onclick="createProject()">Create Project</button>
      <div class="summary">Project ID: <strong id="project_id_display">not created</strong></div>
      <pre id="create_json">{}</pre>
    </section>

    <section>
      <h2>Step 2: Register and Inspect Files</h2>
      <div class="grid">
        <label>count_matrix_path <input id="count_matrix_path" value="examples/real_small_count_matrix.csv" /></label>
        <label>metadata_path <input id="metadata_path" value="examples/real_small_metadata.csv" /></label>
      </div>
      <button onclick="inspectFiles()">Inspect Files</button>
      <div class="summary" id="inspect_summary"></div>
      <pre id="inspect_json">{}</pre>
    </section>

    <section>
      <h2>Step 3: Confirm Schema Mapping</h2>
      <div class="grid">
        <label>gene_id_column <input id="gene_id_column" value="gene_id" /></label>
        <label>sample_id_column <input id="sample_id_column" value="sample_id" /></label>
        <label>group_column <input id="group_column" value="condition" /></label>
        <label>reference_group <input id="reference_group" value="control" /></label>
        <label>test_group <input id="test_group" value="treatment" /></label>
        <label>batch_column <input id="batch_column" value="" /></label>
        <label>covariates <input id="covariates" value="" placeholder="comma,separated" /></label>
        <label>fdr_threshold <input id="fdr_threshold" value="0.05" /></label>
        <label>log2fc_threshold <input id="log2fc_threshold" value="1.0" /></label>
        <label class="inline"><input id="run_enrichment" type="checkbox" /> run_enrichment</label>
      </div>
      <button onclick="prepareAnalysis()">Prepare Analysis</button>
      <div class="summary" id="prepare_summary"></div>
      <pre id="prepare_json">{}</pre>
    </section>

    <section>
      <h2>Step 4: Confirm and Run</h2>
      <div class="grid">
        <label>run_mode
          <select id="run_mode">
            <option value="mock" selected>mock</option>
            <option value="real_r">real_r</option>
            <option value="docker_r">docker_r</option>
          </select>
        </label>
        <label class="inline"><input id="confirmed" type="checkbox" checked /> confirmed</label>
      </div>
      <button onclick="confirmAndRun()">Confirm and Run</button>
      <div class="summary" id="run_summary"></div>
      <pre id="run_json">{}</pre>
    </section>

    <section>
      <h2>Step 5: Get Report</h2>
      <button onclick="getReport()">Get Report</button>
      <div id="risk_warning" class="danger" style="display: none;">当前证据不足以支持强科研结论。</div>
      <div id="method_warning" class="danger warning" style="display: none;">主分析已完成，但存在方法学 warning，请谨慎解释结果。</div>
      <div class="summary" id="report_summary"></div>
      <h3>Artifact Review</h3>
      <div class="summary" id="artifact_review"></div>
      <h3>Export Package</h3>
      <button onclick="createExportPackage()">Create Export Package</button>
      <div class="summary" id="export_package">Export package has not been generated.</div>
      <h3>Result Interpretation</h3>
      <div class="summary" id="result_interpretation"></div>
      <h3>Summary</h3>
      <div id="summary_markdown" class="markdown"></div>
      <h3>QC Report</h3>
      <div id="qc_report_markdown" class="markdown"></div>
      <h3>Method Selection</h3>
      <div id="method_selection_markdown" class="markdown"></div>
      <h3>Reliability Report</h3>
      <div id="reliability_report_markdown" class="markdown"></div>
      <pre id="report_json">{}</pre>
    </section>
  </main>
  <script>
    let projectId = "";

    function byId(id) {
      return document.getElementById(id);
    }

    function setJson(id, data) {
      byId(id).textContent = JSON.stringify(data, null, 2);
    }

    function requireProject() {
      if (!projectId) {
        throw new Error("Create a project first.");
      }
      return projectId;
    }

    async function api(path, options) {
      const response = await fetch(path, {
        headers: {"Content-Type": "application/json"},
        ...options
      });
      const text = await response.text();
      let payload = {};
      try {
        payload = text ? JSON.parse(text) : {};
      } catch (error) {
        payload = {raw: text};
      }
      if (!response.ok) {
        const error = new Error(JSON.stringify(payload, null, 2));
        error.payload = payload;
        throw error;
      }
      return payload;
    }

    function splitList(value) {
      return value.split(",").map(item => item.trim()).filter(Boolean);
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[character]));
    }

    function renderIssues(issues) {
      if (!issues || issues.length === 0) {
        return "<div>No validation issues.</div>";
      }
      return `<div class="issues">${issues.map(issue => {
        const severity = issue.severity || "warning";
        const details = issue.details ? JSON.stringify(issue.details) : "{}";
        return `
          <div class="issue issue-${escapeHtml(severity)}">
            <div><span class="issue-code">${escapeHtml(issue.code || "VALIDATION_ISSUE")}</span> (${escapeHtml(severity)})</div>
            <div>${escapeHtml(issue.message || "")}</div>
            <div><strong>Suggestion:</strong> ${escapeHtml(issue.suggestion || "")}</div>
            <div><strong>Details:</strong> ${escapeHtml(details)}</div>
          </div>
        `;
      }).join("")}</div>`;
    }

    function issuesFromError(error) {
      const detail = error && error.payload ? error.payload.detail : null;
      if (detail && detail.validation_issues) {
        return detail.validation_issues;
      }
      if (error && error.payload && error.payload.validation_issues) {
        return error.payload.validation_issues;
      }
      return [];
    }

    function reliabilityGradeFromResults(results) {
      if (results.reliability_grade) {
        return results.reliability_grade;
      }
      if (results.reliability && results.reliability.grade) {
        return results.reliability.grade;
      }
      return "";
    }

    function artifactRows(manifest, artifactPresenceSummary) {
      const keyArtifacts = [
        "04_main_results/deseq2_results.csv",
        "05_validation_results/edger_results.csv",
        "05_validation_results/limma_voom_results.csv",
        "05_validation_results/validation_comparison.csv",
        "09_environment/run_status.json",
        "09_environment/r_session_info.txt",
        "10_audit_log.json",
        "11_reliability_report.md",
        "12_interpretation_summary.md",
        "manifest.json",
        "08_reproducible_code/README_REPRODUCE.md",
        "08_reproducible_code/analysis_config.json",
        "08_reproducible_code/run_command.txt",
        "08_reproducible_code/docker_command.txt",
        "08_reproducible_code/input_hashes.json",
        "08_reproducible_code/software_versions.json"
      ];
      const files = manifest && manifest.files ? manifest.files : [];
      const statusByPath = {};
      files.forEach(entry => {
        statusByPath[entry.relative_path] = entry.status;
      });
      const keyRows = keyArtifacts.map(relativePath => {
        const status = (artifactPresenceSummary && artifactPresenceSummary[relativePath]) || statusByPath[relativePath] || "missing";
        return `<tr><td>${escapeHtml(relativePath)}</td><td class="status-${escapeHtml(status)}">${escapeHtml(status)}</td><td>key artifact</td></tr>`;
      }).join("");
      const allRows = files.map(entry => (
        `<tr><td>${escapeHtml(entry.relative_path)}</td><td class="status-${escapeHtml(entry.status)}">${escapeHtml(entry.status)}</td><td>${escapeHtml(entry.description || entry.type || "")}</td></tr>`
      )).join("");
      return `
        <h4>Key Artifact Status</h4>
        <table class="artifact-table"><thead><tr><th>relative_path</th><th>status</th><th>note</th></tr></thead><tbody>${keyRows}</tbody></table>
        <h4>Manifest Artifact List</h4>
        <table class="artifact-table"><thead><tr><th>relative_path</th><th>status</th><th>description</th></tr></thead><tbody>${allRows || "<tr><td colspan='3'>No manifest files available.</td></tr>"}</tbody></table>
      `;
    }

    function renderArtifactReview(report, results, manifest) {
      const runStatus = (results.result_summary && results.result_summary.run_status) || {};
      const primaryMethodStatus = report.primary_method_status || results.primary_method_status || runStatus.primary_method_status || "";
      const warnings = report.warnings || results.warnings || runStatus.warnings || [];
      const errors = report.errors || results.errors || runStatus.errors || [];
      const finalStatus = report.final_status || (results.status || "");
      const reliabilityGrade = report.reliability_grade || reliabilityGradeFromResults(results);
      const validationScore = report.validation_consistency_score ?? results.validation_consistency_score ?? runStatus.validation_consistency_score ?? "";
      const artifactPresenceSummary = report.artifact_presence_summary || results.artifact_presence_summary || {};
      const artifactManifest = manifest && manifest.files ? manifest : (report.artifact_manifest || {});

      byId("method_warning").style.display = primaryMethodStatus === "completed_with_warning" ? "block" : "none";
      byId("artifact_review").innerHTML = `
        <div>final status: ${escapeHtml(finalStatus)}</div>
        <div>reliability grade: ${escapeHtml(reliabilityGrade)}</div>
        <div>strong_conclusion_allowed: ${escapeHtml(report.strong_conclusion_allowed)}</div>
        <div>primary_method_status: ${escapeHtml(primaryMethodStatus)}</div>
        <div>validation_consistency_score: ${escapeHtml(validationScore)}</div>
        <div>warnings: ${escapeHtml(warnings.join("; "))}</div>
        <div>errors: ${escapeHtml(errors.join("; "))}</div>
        ${artifactRows(artifactManifest, artifactPresenceSummary)}
      `;
    }

    function renderResultInterpretation(report, results) {
      const interpretation = report.interpretation_summary || results.interpretation_summary || {};
      const summary = interpretation.summary || {};
      const topGenes = report.top_genes || results.top_genes || interpretation.top_genes || [];
      const guardrails = report.interpretation_guardrails || results.interpretation_guardrails || interpretation.guardrails || [];
      const rows = topGenes.map(gene => `
        <tr>
          <td>${escapeHtml(gene.gene_id)}</td>
          <td>${escapeHtml(gene.log2FoldChange)}</td>
          <td>${escapeHtml(gene.padj)}</td>
          <td>${escapeHtml(gene.direction)}</td>
          <td>${escapeHtml((gene.method_support || []).join(", "))}</td>
        </tr>
      `).join("");
      byId("result_interpretation").innerHTML = `
        <div>interpretation_allowed: ${escapeHtml(interpretation.interpretation_allowed)}</div>
        <div>strong_conclusion_allowed: ${escapeHtml(interpretation.strong_conclusion_allowed)}</div>
        <div>total genes: ${escapeHtml(summary.deseq2_total_genes)}</div>
        <div>significant genes: ${escapeHtml(summary.deseq2_significant_genes)}</div>
        <div>upregulated genes: ${escapeHtml(summary.upregulated_genes)}</div>
        <div>downregulated genes: ${escapeHtml(summary.downregulated_genes)}</div>
        <div>validation_consistency_score: ${escapeHtml(summary.validation_consistency_score)}</div>
        <h4>Top candidate statistical signals</h4>
        <table class="artifact-table">
          <thead><tr><th>gene_id</th><th>log2FoldChange</th><th>padj</th><th>direction</th><th>method_support</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='5'>No candidate statistical signals to display.</td></tr>"}</tbody>
        </table>
        <h4>Guardrails</h4>
        <ul>${guardrails.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      `;
    }

    function renderExportPackage(metadata) {
      const warnings = metadata.warnings || [];
      byId("export_package").innerHTML = `
        <div>export status: ${escapeHtml(metadata.status || "not_created")}</div>
        <div>export package path: ${escapeHtml(metadata.export_package_path || "")}</div>
        <div>sha256: ${escapeHtml(metadata.export_package_sha256 || "")}</div>
        <div>size: ${escapeHtml(metadata.size_bytes || "")}</div>
        <div>included file count: ${escapeHtml(metadata.included_file_count || 0)}</div>
        <div>warnings: ${escapeHtml(warnings.join("; "))}</div>
      `;
    }

    function renderExportError(error) {
      const detail = error && error.payload ? error.payload.detail : {};
      byId("export_package").innerHTML = `
        <div class="issue issue-error">
          <div><span class="issue-code">${escapeHtml(detail.code || "EXPORT_FAILED")}</span></div>
          <div>${escapeHtml(detail.message || error.message || "Export package could not be created.")}</div>
          <div><strong>Details:</strong> ${escapeHtml(JSON.stringify(detail.details || {}))}</div>
        </div>
      `;
    }

    async function createProject() {
      try {
        const payload = {
          project_name: byId("project_name").value,
          omics_type: "bulk_rnaseq",
          input_level: "count_matrix",
          organism: byId("organism").value,
          gene_id_type: byId("gene_id_type").value,
          annotation_version: byId("annotation_version").value
        };
        const data = await api("/coze/projects", {method: "POST", body: JSON.stringify(payload)});
        projectId = data.project_id;
        byId("project_id_display").textContent = projectId;
        setJson("create_json", data);
      } catch (error) {
        alert(error.message);
      }
    }

    async function inspectFiles() {
      try {
        const id = requireProject();
        const payload = {
          count_matrix_path: byId("count_matrix_path").value,
          metadata_path: byId("metadata_path").value
        };
        const data = await api(`/coze/projects/${id}/inspect`, {method: "POST", body: JSON.stringify(payload)});
        byId("inspect_summary").innerHTML = `
          <div>${data.human_readable_summary}</div>
          <div>detected_gene_id_column_candidates: ${(data.gene_id_column_candidates || []).join(", ")}</div>
          <div>detected_sample_columns: ${(data.sample_columns || []).join(", ")}</div>
          <div>detected_metadata_columns: ${(data.metadata_columns || []).join(", ")}</div>
          <div>possible_sample_id_column: ${data.possible_sample_id_column || ""}</div>
          <div>possible_group_column: ${data.possible_group_column || ""}</div>
          <div>possible_batch_column: ${data.possible_batch_column || ""}</div>
          <div>warnings: ${(data.warnings || []).join("; ")}</div>
          <h4>Validation Issues</h4>
          ${renderIssues(data.validation_issues || [])}
        `;
        setJson("inspect_json", data);
      } catch (error) {
        const issues = issuesFromError(error);
        byId("inspect_summary").innerHTML = `<h4>Validation Issues</h4>${renderIssues(issues)}`;
        setJson("inspect_json", error.payload || {error: error.message});
      }
    }

    async function prepareAnalysis() {
      try {
        const id = requireProject();
        const batchColumn = byId("batch_column").value.trim();
        const payload = {
          gene_id_column: byId("gene_id_column").value,
          sample_id_column: byId("sample_id_column").value,
          group_column: byId("group_column").value,
          reference_group: byId("reference_group").value,
          test_group: byId("test_group").value,
          batch_column: batchColumn || null,
          covariates: splitList(byId("covariates").value),
          fdr_threshold: Number(byId("fdr_threshold").value),
          log2fc_threshold: Number(byId("log2fc_threshold").value),
          run_enrichment: byId("run_enrichment").checked
        };
        const data = await api(`/coze/projects/${id}/prepare-analysis`, {method: "POST", body: JSON.stringify(payload)});
        byId("prepare_summary").innerHTML = `
          <div>${data.human_readable_summary}</div>
          <div>qc_status: ${data.qc_status}</div>
          <div>stop_conditions: ${(data.stop_conditions || []).join("; ")}</div>
          <div>warnings: ${(data.warnings || []).join("; ")}</div>
          <div>recommended_plan: ${data.recommended_plan ? JSON.stringify(data.recommended_plan) : ""}</div>
          <div>requires confirmation: ${data.requires_user_confirmation}</div>
          <div>next_action: ${data.next_action}</div>
          <h4>Validation Issues</h4>
          ${renderIssues(data.validation_issues || [])}
        `;
        setJson("prepare_json", data);
      } catch (error) {
        const issues = issuesFromError(error);
        byId("prepare_summary").innerHTML = `<h4>Validation Issues</h4>${renderIssues(issues)}`;
        setJson("prepare_json", error.payload || {error: error.message});
      }
    }

    async function confirmAndRun() {
      try {
        const id = requireProject();
        const payload = {
          confirmed: byId("confirmed").checked,
          run_mode: byId("run_mode").value,
          analysis_plan_overrides: {}
        };
        const data = await api(`/coze/projects/${id}/confirm-and-run`, {method: "POST", body: JSON.stringify(payload)});
        byId("run_summary").innerHTML = `
          <div>${data.human_readable_summary}</div>
          <div>run_status: ${data.run_status}</div>
          <div>reliability_grade: ${data.reliability_grade || ""}</div>
          <div>allowed_conclusion_level: ${data.allowed_conclusion_level}</div>
          <div>artifact_manifest files: ${data.artifact_manifest && data.artifact_manifest.files ? data.artifact_manifest.files.length : 0}</div>
          <div>next_action: ${data.next_action}</div>
        `;
        setJson("run_json", data);
      } catch (error) {
        alert(error.message);
      }
    }

    async function createExportPackage() {
      try {
        const id = requireProject();
        const data = await api(`/projects/${id}/export`, {method: "POST"});
        renderExportPackage(data);
      } catch (error) {
        renderExportError(error);
      }
    }

    async function getReport() {
      try {
        const id = requireProject();
        const data = await api(`/coze/projects/${id}/report`, {method: "GET"});
        const results = await api(`/projects/${id}/results`, {method: "GET"});
        const manifest = await api(`/projects/${id}/artifacts`, {method: "GET"});
        const exportMetadata = await api(`/projects/${id}/export`, {method: "GET"});
        byId("risk_warning").style.display = data.strong_conclusion_allowed ? "none" : "block";
        byId("report_summary").innerHTML = `
          <div>final_status: ${data.final_status || results.status || ""}</div>
          <div>reliability_grade: ${data.reliability_grade || reliabilityGradeFromResults(results)}</div>
          <div>strong_conclusion_allowed: ${data.strong_conclusion_allowed}</div>
          <div>primary_method_status: ${data.primary_method_status || results.primary_method_status || ""}</div>
          <div>validation_consistency_score: ${data.validation_consistency_score ?? results.validation_consistency_score ?? ""}</div>
          <div>allowed_conclusion_level: ${data.allowed_conclusion_level}</div>
          <div>manifest files: ${manifest && manifest.files ? manifest.files.length : 0}</div>
        `;
        renderArtifactReview(data, results, manifest);
        renderExportPackage(exportMetadata);
        renderResultInterpretation(data, results);
        byId("summary_markdown").textContent = data.summary_markdown || "";
        byId("qc_report_markdown").textContent = data.qc_report_markdown || "";
        byId("method_selection_markdown").textContent = data.method_selection_markdown || "";
        byId("reliability_report_markdown").textContent = data.reliability_report_markdown || "";
        setJson("report_json", {report: data, results, artifacts: manifest, export: exportMetadata});
      } catch (error) {
        alert(error.message);
      }
    }
  </script>
</body>
</html>"""
