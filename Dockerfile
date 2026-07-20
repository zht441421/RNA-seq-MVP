FROM python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db

ARG VCS_REF=local-uncommitted
ARG DEBIAN_SNAPSHOT=20250601T000000Z
ARG R_BASE_CORE_VERSION=4.2.2.20221110-2
ARG BIOCMANAGER_DEBIAN_VERSION=1.30.20+dfsg-1
ARG BIOCVERSION_DEBIAN_VERSION=3.16.0-1
ARG DESEQ2_DEBIAN_VERSION=1.38.3+dfsg-1
LABEL org.opencontainers.image.title="Bioinformatics Agent API"
LABEL org.opencontainers.image.description="Single-instance protected staging runtime"
LABEL org.opencontainers.image.revision="${VCS_REF}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/bioinformatics-agent \
    R_ENVIRON_USER=/dev/null \
    R_PROFILE_USER=/dev/null

# The timestamped Debian snapshot fixes the complete apt dependency closure.
# R/Bioconductor packages are installed only while the image is built.
RUN printf '%s\n' \
      "deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT} bookworm main" \
      "deb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT} bookworm-security main" \
      > /etc/apt/sources.list \
    && rm -f /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install --yes --no-install-recommends \
      "r-base-core=${R_BASE_CORE_VERSION}" \
      "r-cran-biocmanager=${BIOCMANAGER_DEBIAN_VERSION}" \
      "r-bioc-biocversion=${BIOCVERSION_DEBIAN_VERSION}" \
      "r-bioc-deseq2=${DESEQ2_DEBIAN_VERSION}" \
    && R --version \
    && Rscript --version \
    && Rscript --vanilla -e 'expected <- c(DESeq2="1.38.3", SummarizedExperiment="1.28.0", S4Vectors="0.36.1", IRanges="2.32.0", BiocGenerics="0.44.0", BiocManager="1.30.20", BiocVersion="3.16.0"); invisible(lapply(names(expected), function(pkg) { suppressPackageStartupMessages(library(pkg, character.only=TRUE)); actual <- as.character(packageVersion(pkg)); if (!identical(actual, unname(expected[[pkg]]))) stop(sprintf("%s version mismatch", pkg)) })); if (!identical(as.character(BiocManager::version()), "3.16")) stop("Bioconductor version mismatch")' \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /tmp/*

RUN groupadd --gid 10001 bioinfo \
    && useradd --uid 10001 --gid bioinfo --create-home --shell /usr/sbin/nologin bioinfo \
    && mkdir -p /opt/bioinformatics-agent /var/lib/bioinfo/state /var/lib/bioinfo/artifacts \
    && chown -R bioinfo:bioinfo /opt/bioinformatics-agent /var/lib/bioinfo

WORKDIR /opt/bioinformatics-agent

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=bioinfo:bioinfo backend ./backend
COPY --chown=bioinfo:bioinfo docs/runtime/r-deseq2-runtime.json ./docs/runtime/r-deseq2-runtime.json
COPY --chown=bioinfo:bioinfo deploy/staging/start-app.sh /usr/local/bin/start-bioinfo-api
COPY --chown=bioinfo:bioinfo scripts/probe_phase_8_6_1_r_deseq2_runtime.py ./scripts/probe_phase_8_6_1_r_deseq2_runtime.py
RUN chmod 0555 /usr/local/bin/start-bioinfo-api \
    && chmod -R a-w /opt/bioinformatics-agent

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"]

ENTRYPOINT ["/usr/local/bin/start-bioinfo-api"]
