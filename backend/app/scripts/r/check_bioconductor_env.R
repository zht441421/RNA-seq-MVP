#!/usr/bin/env Rscript

json_escape <- function(value) {
  value <- as.character(value)
  value <- gsub("\\\\", "\\\\\\\\", value)
  value <- gsub("\"", "\\\\\"", value)
  value <- gsub("\n", "\\\\n", value)
  value <- gsub("\r", "\\\\r", value)
  value <- gsub("\t", "\\\\t", value)
  value
}

json_string <- function(value) {
  paste0("\"", json_escape(value), "\"")
}

json_bool <- function(value) {
  if (isTRUE(value)) "true" else "false"
}

json_array <- function(values) {
  if (length(values) == 0) {
    return("[]")
  }
  paste0("[", paste(vapply(values, json_string, character(1)), collapse = ","), "]")
}

package_info <- function(package_name) {
  installed <- requireNamespace(package_name, quietly = TRUE)
  version <- NULL
  if (installed) {
    version <- as.character(utils::packageVersion(package_name))
  }
  list(installed = installed, version = version)
}

package_json <- function(info) {
  version_value <- if (is.null(info$version)) "null" else json_string(info$version)
  paste0("{\"installed\":", json_bool(info$installed), ",\"version\":", version_value, "}")
}

packages_to_check <- c("DESeq2", "edgeR", "limma", "ggplot2", "pheatmap", "jsonlite", "readr")
package_results <- stats::setNames(lapply(packages_to_check, package_info), packages_to_check)

required_packages <- c("DESeq2", "jsonlite", "readr")
optional_packages <- c("edgeR", "limma", "ggplot2", "pheatmap")
missing_required <- required_packages[
  !vapply(required_packages, function(package_name) package_results[[package_name]]$installed, logical(1))
]
missing_optional <- optional_packages[
  !vapply(optional_packages, function(package_name) package_results[[package_name]]$installed, logical(1))
]

package_entries <- vapply(
  names(package_results),
  function(package_name) {
    paste0(json_string(package_name), ":", package_json(package_results[[package_name]]))
  },
  character(1)
)

payload <- paste0(
  "{",
  "\"r_available\":true,",
  "\"r_version\":", json_string(as.character(getRversion())), ",",
  "\"packages\":{", paste(package_entries, collapse = ","), "},",
  "\"ready_for_real_r\":", json_bool(length(missing_required) == 0), ",",
  "\"missing_required\":", json_array(missing_required), ",",
  "\"missing_optional\":", json_array(missing_optional),
  "}"
)

cat(payload)
