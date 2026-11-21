# One recipe for all eight services. Build from the project root:
#   docker build -f services/Dockerfile --build-arg SERVICE=risk -t terrarisk-risk .
# Each image contains only the shared library + its own service + its own dependencies.
FROM python:3.12-slim

ARG SERVICE
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SERVICE=${SERVICE} PYTHONPATH=/app/common:/app/service

WORKDIR /app
COPY services/common/requirements.txt /tmp/common-requirements.txt
COPY services/${SERVICE}/requirements.txt /tmp/service-requirements.txt
RUN pip install --no-cache-dir -r /tmp/common-requirements.txt -r /tmp/service-requirements.txt

COPY services/common /app/common
COPY services/${SERVICE} /app/service

# Run as a normal user; /data is where a service keeps its own files (databases, caches) and is a Docker volume.
RUN useradd --system --uid 10001 app && mkdir -p /data && chown -R app /data /app/service
USER app

# The chatbot "trains" at build time (a tenth of a second) so the first question is not slower.
RUN if [ "${SERVICE}" = "chatbot" ]; then python -m tr_chatbot.train; fi

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=4s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)"

# One worker with many threads (not many workers): the service keeps its counters and caches in one process,
# and SQLite (billing, geocode) is happiest with one writer process. Scale by running more containers instead.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:8000 --workers ${WORKERS:-1} --threads ${THREADS:-8} --timeout ${TIMEOUT:-150} --access-logfile - \"tr_${SERVICE}.app:create_app()\""]
