FROM bioconductor/bioconductor_docker:RELEASE_3_19

LABEL org.opencontainers.image.title="Bioinformatics Agent Bulk RNA-seq R Runtime"
LABEL org.opencontainers.image.description="Reproducible R/Bioconductor runtime for Phase 1 Bulk RNA-seq count matrix differential expression"
LABEL org.opencontainers.image.version="0.1"

ENV R_REMOTES_NO_ERRORS_FROM_WARNINGS=true
ENV BIOCONDUCTOR_ONLINE_VERSION_DIAGNOSIS=FALSE

RUN R -q -e "options(repos = c( \
  BioCsoft='https://bioconductor.org/packages/3.19/bioc', \
  BioCann='https://bioconductor.org/packages/3.19/data/annotation', \
  BioCexp='https://bioconductor.org/packages/3.19/data/experiment', \
  BioCworkflows='https://bioconductor.org/packages/3.19/workflows', \
  CRAN='https://packagemanager.posit.co/cran/2024-06-01' \
)); pkgs <- c('DESeq2', 'edgeR', 'limma', 'ggplot2', 'pheatmap', 'jsonlite', 'readr', 'optparse'); missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly=TRUE)]; if (length(missing)) install.packages(missing) else message('All required packages already installed')"

RUN mkdir -p /opt/bioinformatics-agent/scripts
COPY backend/app/scripts/r/bulk_rnaseq_de.R /opt/bioinformatics-agent/scripts/bulk_rnaseq_de.R
COPY backend/app/scripts/r/check_bioconductor_env.R /opt/bioinformatics-agent/scripts/check_bioconductor_env.R

WORKDIR /workspace

CMD ["Rscript", "/opt/bioinformatics-agent/scripts/check_bioconductor_env.R"]
