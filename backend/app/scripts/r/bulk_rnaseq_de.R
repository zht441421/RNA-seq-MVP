#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) {
  stop("Usage: Rscript bulk_rnaseq_de.R analysis_config.json")
}

config_path <- normalizePath(args[[1]], mustWork = TRUE)

jsonlite_available <- requireNamespace("jsonlite", quietly = TRUE)
if (!jsonlite_available) {
  fallback_dir <- dirname(config_path)
  dir.create(file.path(fallback_dir, "09_environment"), recursive = TRUE, showWarnings = FALSE)
  writeLines(
    "{\"execution_mode\":\"real_r\",\"primary_method_status\":\"failed\",\"error\":\"Required R package jsonlite is not installed.\"}",
    file.path(fallback_dir, "09_environment", "run_status.json")
  )
  stop("Required R package jsonlite is not installed.")
}

config <- jsonlite::fromJSON(config_path)
output_dir <- normalizePath(config$output_dir, mustWork = FALSE)

dirs <- list(
  main = file.path(output_dir, "04_main_results"),
  validation = file.path(output_dir, "05_validation_results"),
  figures = file.path(output_dir, "06_figures"),
  tables = file.path(output_dir, "07_tables"),
  environment = file.path(output_dir, "09_environment")
)
for (dir_path in dirs) {
  dir.create(dir_path, recursive = TRUE, showWarnings = FALSE)
}

status <- list(
  project_id = config$project_id,
  execution_mode = "real_r",
  started_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC"),
  completed_at = NULL,
  primary_method = "DESeq2",
  primary_method_status = "not_started",
  validation_method_status = list(edgeR = "not_started", limma_voom = "not_started"),
  fdr_applied = FALSE,
  validation_consistency_score = NA,
  validation_consistency_status = "not_evaluated",
  errors = list(),
  warnings = list(),
  artifacts = list()
)

status_path <- file.path(dirs$environment, "run_status.json")

add_error <- function(message) {
  status$errors[[length(status$errors) + 1]] <<- message
}

add_warning <- function(message) {
  status$warnings[[length(status$warnings) + 1]] <<- message
}

write_status <- function(final = FALSE) {
  if (final) {
    status$completed_at <<- format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC")
  }
  jsonlite::write_json(status, status_path, pretty = TRUE, auto_unbox = TRUE, null = "null", na = "null")
}

has_package <- function(package_name) {
  requireNamespace(package_name, quietly = TRUE)
}

package_info <- function(package_name) {
  installed <- has_package(package_name)
  version <- NULL
  if (installed) {
    version <- as.character(utils::packageVersion(package_name))
  }
  list(installed = installed, version = version)
}

required_packages <- c("DESeq2", "edgeR", "limma", "ggplot2", "pheatmap", "jsonlite", "readr")
package_status <- stats::setNames(lapply(required_packages, package_info), required_packages)
status$package_status <- package_status
write_status()

if (!isTRUE(package_status$DESeq2$installed)) {
  status$primary_method_status <- "failed"
  add_error("Required R package DESeq2 is not installed. Primary analysis cannot run.")
  write_status(final = TRUE)
  stop("Required R package DESeq2 is not installed.")
}

if (!isTRUE(package_status$readr$installed)) {
  status$primary_method_status <- "failed"
  add_error("Required R package readr is not installed. Input files cannot be read.")
  write_status(final = TRUE)
  stop("Required R package readr is not installed.")
}

if (!isTRUE(package_status$edgeR$installed)) {
  status$validation_method_status$edgeR <- "skipped"
  add_warning("edgeR is not installed. edgeR validation was skipped.")
}

if (!isTRUE(package_status$limma$installed)) {
  status$validation_method_status$limma_voom <- "skipped"
  add_warning("limma is not installed. limma-voom validation was skipped.")
} else if (!isTRUE(package_status$edgeR$installed)) {
  status$validation_method_status$limma_voom <- "skipped"
  add_warning("edgeR is not installed. limma-voom validation was skipped because DGEList normalization is unavailable.")
}

read_table <- function(path) {
  ext <- tolower(tools::file_ext(path))
  if (ext == "csv") {
    return(readr::read_csv(path, show_col_types = FALSE))
  }
  if (ext %in% c("tsv", "txt")) {
    return(readr::read_tsv(path, show_col_types = FALSE))
  }
  stop(sprintf("Unsupported file extension for real R runner: .%s", ext))
}

safe_write_csv <- function(data, path) {
  readr::write_csv(as.data.frame(data), path)
  status$artifacts[[length(status$artifacts) + 1]] <<- path
}

primary_method_completed <- function() {
  status$primary_method_status %in% c("completed", "completed_with_warning")
}

vst_for_plots <- function(dds) {
  if (nrow(dds) < 1000) {
    return(DESeq2::varianceStabilizingTransformation(dds, blind = FALSE))
  }
  DESeq2::vst(dds, blind = FALSE)
}

tryCatch({
  count_matrix <- read_table(config$count_matrix_path)
  metadata <- read_table(config$metadata_path)

  required_count_columns <- c(config$gene_id_column)
  required_metadata_columns <- c(config$sample_id_column, config$group_column)
  if (!is.null(config$batch_column) && !is.na(config$batch_column) && nzchar(config$batch_column)) {
    required_metadata_columns <- c(required_metadata_columns, config$batch_column)
  }
  if (length(config$covariates) > 0) {
    required_metadata_columns <- c(required_metadata_columns, config$covariates)
  }

  missing_count_columns <- setdiff(required_count_columns, colnames(count_matrix))
  missing_metadata_columns <- setdiff(required_metadata_columns, colnames(metadata))
  if (length(missing_count_columns) > 0) {
    stop(sprintf("Missing count matrix columns: %s", paste(missing_count_columns, collapse = ", ")))
  }
  if (length(missing_metadata_columns) > 0) {
    stop(sprintf("Missing metadata columns: %s", paste(missing_metadata_columns, collapse = ", ")))
  }

  gene_ids <- as.character(count_matrix[[config$gene_id_column]])
  count_sample_columns <- setdiff(colnames(count_matrix), config$gene_id_column)
  metadata[[config$sample_id_column]] <- as.character(metadata[[config$sample_id_column]])
  metadata <- metadata[metadata[[config$group_column]] %in% c(config$reference_group, config$test_group), , drop = FALSE]
  metadata_sample_ids <- metadata[[config$sample_id_column]]

  missing_in_metadata <- setdiff(count_sample_columns, metadata_sample_ids)
  missing_in_counts <- setdiff(metadata_sample_ids, count_sample_columns)
  if (length(missing_in_metadata) > 0 || length(missing_in_counts) > 0) {
    stop(sprintf(
      "Sample IDs do not align. Missing in metadata: %s. Missing in count matrix: %s.",
      paste(missing_in_metadata, collapse = ", "),
      paste(missing_in_counts, collapse = ", ")
    ))
  }

  count_data <- as.data.frame(count_matrix[, metadata_sample_ids, drop = FALSE])
  count_data[] <- lapply(count_data, as.numeric)
  if (any(is.na(count_data))) {
    stop("Count matrix contains non-numeric values.")
  }
  if (any(as.matrix(count_data) < 0)) {
    stop("Count matrix contains negative values.")
  }
  count_data <- round(as.matrix(count_data))
  rownames(count_data) <- make.unique(gene_ids)
  metadata <- as.data.frame(metadata)
  rownames(metadata) <- metadata[[config$sample_id_column]]
  metadata[[config$group_column]] <- stats::relevel(as.factor(metadata[[config$group_column]]), ref = config$reference_group)

  design_terms <- c()
  if (!is.null(config$batch_column) && !is.na(config$batch_column) && nzchar(config$batch_column)) {
    metadata[[config$batch_column]] <- as.factor(metadata[[config$batch_column]])
    design_terms <- c(design_terms, config$batch_column)
  }
  if (length(config$covariates) > 0) {
    design_terms <- c(design_terms, config$covariates)
  }
  design_terms <- c(design_terms, config$group_column)
  design_formula <- stats::as.formula(paste("~", paste(unique(design_terms), collapse = " + ")))
  status$design_formula <- paste(deparse(design_formula), collapse = "")

  keep <- rowSums(count_data) >= 10
  if (sum(keep) == 0) {
    stop("No genes remain after low-count filtering.")
  }
  count_data <- count_data[keep, , drop = FALSE]

  dds <- DESeq2::DESeqDataSetFromMatrix(countData = count_data, colData = metadata, design = design_formula)
  deseq2_primary_status <- "completed"
  deseq2_error <- tryCatch({
    dds <- DESeq2::DESeq(dds)
    NULL
  }, error = function(e) {
    e
  })
  if (inherits(deseq2_error, "error")) {
    deseq2_error_message <- conditionMessage(deseq2_error)
    if (grepl("all gene-wise dispersion estimates", deseq2_error_message, fixed = TRUE)) {
      add_warning("DESeq2 standard dispersion fit failed; used gene-wise dispersion fallback.")
      fallback_error <- tryCatch({
        dds <- DESeq2::estimateSizeFactors(dds)
        dds <- DESeq2::estimateDispersionsGeneEst(dds)
        dds <- DESeq2::`dispersions<-`(dds, value = S4Vectors::mcols(dds)$dispGeneEst)
        dds <- DESeq2::nbinomWaldTest(dds)
        NULL
      }, error = function(e) {
        e
      })
      if (inherits(fallback_error, "error")) {
        stop(sprintf(
          "DESeq2 standard dispersion fit failed and gene-wise dispersion fallback also failed: %s",
          conditionMessage(fallback_error)
        ))
      }
      deseq2_primary_status <- "completed_with_warning"
    } else {
      stop(deseq2_error)
    }
  }
  res <- DESeq2::results(dds, contrast = c(config$group_column, config$test_group, config$reference_group))
  res_df <- as.data.frame(res)
  res_df$gene_id <- rownames(res_df)
  res_df <- res_df[, c("gene_id", setdiff(colnames(res_df), "gene_id"))]
  res_df$significant <- !is.na(res_df$padj) &
    res_df$padj <= config$fdr_threshold &
    abs(res_df$log2FoldChange) >= config$log2fc_threshold
  deseq2_path <- file.path(dirs$main, "deseq2_results.csv")
  safe_write_csv(res_df, deseq2_path)

  normalized_counts <- as.data.frame(DESeq2::counts(dds, normalized = TRUE))
  normalized_counts$gene_id <- rownames(normalized_counts)
  normalized_counts <- normalized_counts[, c("gene_id", setdiff(colnames(normalized_counts), "gene_id"))]
  safe_write_csv(normalized_counts, file.path(dirs$tables, "normalized_counts.csv"))

  significant_path <- file.path(dirs$tables, "significant_genes_deseq2.csv")
  safe_write_csv(res_df[res_df$significant, , drop = FALSE], significant_path)

  status$primary_method_status <- deseq2_primary_status
  status$fdr_applied <- TRUE

  if (isTRUE(package_status$ggplot2$installed)) {
    tryCatch({
      vst_data <- vst_for_plots(dds)
      pca_data <- DESeq2::plotPCA(vst_data, intgroup = config$group_column, returnData = TRUE)
      percent_var <- round(100 * attr(pca_data, "percentVar"))
      p <- ggplot2::ggplot(pca_data, ggplot2::aes(x = PC1, y = PC2, color = .data[[config$group_column]])) +
        ggplot2::geom_point(size = 3) +
        ggplot2::xlab(paste0("PC1: ", percent_var[1], "% variance")) +
        ggplot2::ylab(paste0("PC2: ", percent_var[2], "% variance")) +
        ggplot2::theme_minimal()
      ggplot2::ggsave(file.path(dirs$figures, "pca_plot.png"), p, width = 7, height = 5, dpi = 150)
      status$artifacts[[length(status$artifacts) + 1]] <- file.path(dirs$figures, "pca_plot.png")

      volcano_df <- res_df
      volcano_df$neg_log10_padj <- -log10(volcano_df$padj)
      volcano <- ggplot2::ggplot(volcano_df, ggplot2::aes(x = log2FoldChange, y = neg_log10_padj, color = significant)) +
        ggplot2::geom_point(alpha = 0.7) +
        ggplot2::theme_minimal() +
        ggplot2::labs(x = "log2 fold change", y = "-log10 adjusted p-value")
      ggplot2::ggsave(file.path(dirs$figures, "volcano_deseq2.png"), volcano, width = 7, height = 5, dpi = 150)
      status$artifacts[[length(status$artifacts) + 1]] <- file.path(dirs$figures, "volcano_deseq2.png")

      png(file.path(dirs$figures, "ma_plot_deseq2.png"), width = 900, height = 700)
      DESeq2::plotMA(res)
      dev.off()
      status$artifacts[[length(status$artifacts) + 1]] <- file.path(dirs$figures, "ma_plot_deseq2.png")
    }, error = function(e) {
      add_warning(paste("DESeq2 figure generation failed:", conditionMessage(e)))
    })
  } else {
    add_warning("ggplot2 is not installed. PCA and volcano plots were skipped.")
  }

  if (isTRUE(package_status$pheatmap$installed)) {
    tryCatch({
      vst_data <- vst_for_plots(dds)
      sample_dist <- stats::dist(t(SummarizedExperiment::assay(vst_data)))
      sample_dist_matrix <- as.matrix(sample_dist)
      png(file.path(dirs$figures, "sample_distance_heatmap.png"), width = 900, height = 800)
      pheatmap::pheatmap(sample_dist_matrix)
      dev.off()
      status$artifacts[[length(status$artifacts) + 1]] <- file.path(dirs$figures, "sample_distance_heatmap.png")
    }, error = function(e) {
      add_warning(paste("Sample distance heatmap generation failed:", conditionMessage(e)))
    })
  } else {
    add_warning("pheatmap is not installed. Sample distance heatmap was skipped.")
  }

  model_matrix <- stats::model.matrix(design_formula, metadata)
  group_coef <- grep(paste0("^", make.names(config$group_column), make.names(config$test_group), "$"), colnames(model_matrix), value = TRUE)
  if (length(group_coef) == 0) {
    group_coef <- grep(make.names(config$test_group), colnames(model_matrix), value = TRUE)
  }
  if (length(group_coef) > 0) {
    group_coef <- group_coef[[1]]
  }

  if (isTRUE(package_status$edgeR$installed)) {
    tryCatch({
      y <- edgeR::DGEList(counts = count_data, group = metadata[[config$group_column]])
      y <- edgeR::calcNormFactors(y)
      y <- edgeR::estimateDisp(y, model_matrix)
      fit <- edgeR::glmQLFit(y, model_matrix)
      qlf <- edgeR::glmQLFTest(fit, coef = group_coef)
      edger_df <- edgeR::topTags(qlf, n = Inf)$table
      edger_df$gene_id <- rownames(edger_df)
      edger_df <- edger_df[, c("gene_id", setdiff(colnames(edger_df), "gene_id"))]
      edger_df$significant <- !is.na(edger_df$FDR) &
        edger_df$FDR <= config$fdr_threshold &
        abs(edger_df$logFC) >= config$log2fc_threshold
      safe_write_csv(edger_df, file.path(dirs$validation, "edger_results.csv"))
      status$validation_method_status$edgeR <- "completed"
    }, error = function(e) {
      status$validation_method_status$edgeR <<- "failed"
      add_warning(paste("edgeR validation failed:", conditionMessage(e)))
    })
  }

  if (isTRUE(package_status$limma$installed) && isTRUE(package_status$edgeR$installed)) {
    tryCatch({
      y <- edgeR::DGEList(counts = count_data, group = metadata[[config$group_column]])
      y <- edgeR::calcNormFactors(y)
      v <- limma::voom(y, model_matrix, plot = FALSE)
      fit <- limma::lmFit(v, model_matrix)
      fit <- limma::eBayes(fit)
      limma_df <- limma::topTable(fit, coef = group_coef, number = Inf, sort.by = "P")
      limma_df$gene_id <- rownames(limma_df)
      limma_df <- limma_df[, c("gene_id", setdiff(colnames(limma_df), "gene_id"))]
      limma_df$significant <- !is.na(limma_df$adj.P.Val) &
        limma_df$adj.P.Val <= config$fdr_threshold &
        abs(limma_df$logFC) >= config$log2fc_threshold
      safe_write_csv(limma_df, file.path(dirs$validation, "limma_voom_results.csv"))
      status$validation_method_status$limma_voom <- "completed"
    }, error = function(e) {
      status$validation_method_status$limma_voom <<- "failed"
      add_warning(paste("limma-voom validation failed:", conditionMessage(e)))
    })
  }

  comparison_rows <- data.frame(gene_id = res_df$gene_id, stringsAsFactors = FALSE)
  comparison_rows$deseq2_log2fc <- res_df$log2FoldChange
  comparison_rows$significant_by_deseq2 <- res_df$significant
  comparisons_total <- 0
  comparisons_consistent <- 0

  add_validation_comparison <- function(results_path, method_name, logfc_column, fdr_column) {
    if (!file.exists(results_path)) {
      comparison_rows[[paste0(method_name, "_logfc")]] <<- NA_real_
      comparison_rows[[paste0("significant_by_", method_name)]] <<- FALSE
      comparison_rows[[paste0(method_name, "_direction_consistent")]] <<- NA
      return()
    }
    validation_df <- readr::read_csv(results_path, show_col_types = FALSE)
    merged <- merge(comparison_rows["gene_id"], validation_df, by = "gene_id", all.x = TRUE)
    logfc_values <- merged[[logfc_column]]
    significant_values <- !is.na(merged[[fdr_column]]) &
      merged[[fdr_column]] <= config$fdr_threshold &
      abs(logfc_values) >= config$log2fc_threshold
    direction_consistent <- sign(comparison_rows$deseq2_log2fc) == sign(logfc_values)
    direction_consistent[is.na(direction_consistent)] <- FALSE
    comparison_rows[[paste0(method_name, "_logfc")]] <<- logfc_values
    comparison_rows[[paste0("significant_by_", method_name)]] <<- significant_values
    comparison_rows[[paste0(method_name, "_direction_consistent")]] <<- direction_consistent
    sig_idx <- which(comparison_rows$significant_by_deseq2 & !is.na(logfc_values))
    comparisons_total <<- comparisons_total + length(sig_idx)
    comparisons_consistent <<- comparisons_consistent + sum(direction_consistent[sig_idx], na.rm = TRUE)
  }

  add_validation_comparison(file.path(dirs$validation, "edger_results.csv"), "edger", "logFC", "FDR")
  add_validation_comparison(file.path(dirs$validation, "limma_voom_results.csv"), "limma", "logFC", "adj.P.Val")

  if (sum(comparison_rows$significant_by_deseq2, na.rm = TRUE) == 0) {
    status$validation_consistency_status <- "insufficient_significant_genes"
    status$validation_consistency_score <- NA
  } else if (comparisons_total == 0) {
    status$validation_consistency_status <- "no_validation_comparisons"
    status$validation_consistency_score <- NA
  } else {
    status$validation_consistency_score <- comparisons_consistent / comparisons_total
    status$validation_consistency_status <- "computed"
  }

  comparison_path <- file.path(dirs$validation, "validation_comparison.csv")
  safe_write_csv(comparison_rows, comparison_path)

}, error = function(e) {
  if (!primary_method_completed()) {
    status$primary_method_status <<- "failed"
  }
  add_error(conditionMessage(e))
})

session_path <- file.path(dirs$environment, "r_session_info.txt")
writeLines(capture.output(utils::sessionInfo()), session_path)
status$r_session_info_path <- session_path
status$run_status_path <- status_path
status$artifacts[[length(status$artifacts) + 1]] <- session_path
status$artifacts[[length(status$artifacts) + 1]] <- status_path
write_status(final = TRUE)

if (!primary_method_completed()) {
  quit(status = 1)
}
quit(status = 0)
