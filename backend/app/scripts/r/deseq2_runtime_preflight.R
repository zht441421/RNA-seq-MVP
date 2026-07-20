#!/usr/bin/env Rscript

# Controlled runtime-only probe. It loads the package set used by the formal
# DESeq2 executor but performs no differential-expression analysis.
suppressPackageStartupMessages({
  library(DESeq2)
  library(SummarizedExperiment)
  library(S4Vectors)
  library(IRanges)
  library(BiocGenerics)
  library(BiocManager)
  library(BiocVersion)
})

cat("BIOCONDUCTOR\t", as.character(BiocManager::version()), "\n", sep = "")
for (package_name in c(
  "DESeq2",
  "SummarizedExperiment",
  "S4Vectors",
  "IRanges",
  "BiocGenerics",
  "BiocManager",
  "BiocVersion"
)) {
  cat(
    "PACKAGE\t",
    package_name,
    "\t",
    as.character(packageVersion(package_name)),
    "\n",
    sep = ""
  )
}
