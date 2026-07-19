FROM python:3.12.10-slim-bookworm

ARG VCS_REF=local-uncommitted
LABEL org.opencontainers.image.title="Bioinformatics Agent API"
LABEL org.opencontainers.image.description="Single-instance protected staging runtime"
LABEL org.opencontainers.image.revision="${VCS_REF}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/bioinformatics-agent

RUN groupadd --gid 10001 bioinfo \
    && useradd --uid 10001 --gid bioinfo --create-home --shell /usr/sbin/nologin bioinfo \
    && mkdir -p /opt/bioinformatics-agent /var/lib/bioinfo/state /var/lib/bioinfo/artifacts \
    && chown -R bioinfo:bioinfo /opt/bioinformatics-agent /var/lib/bioinfo

WORKDIR /opt/bioinformatics-agent

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=bioinfo:bioinfo backend ./backend
COPY --chown=bioinfo:bioinfo deploy/staging/start-app.sh /usr/local/bin/start-bioinfo-api
RUN chmod 0555 /usr/local/bin/start-bioinfo-api

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"]

ENTRYPOINT ["/usr/local/bin/start-bioinfo-api"]
