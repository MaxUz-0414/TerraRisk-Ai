# The WEBSITE image (Django). The eight services are built from services/Dockerfile.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# The website waits for the services while an analysis runs (up to ~3 minutes with real Earth Engine data), so it uses a few
# workers with several threads each instead of many single-threaded workers.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers ${WEB_WORKERS:-2} --threads ${WEB_THREADS:-4} --timeout 200 --access-logfile -"]
