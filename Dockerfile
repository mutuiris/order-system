ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system django \
    && adduser --system --ingroup django django

# Set work directory
WORKDIR /app

# Copy and install requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy project files
COPY --chown=django:django . .

RUN mkdir -p staticfiles media && chown -R django:django staticfiles media

USER django

EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python manage.py check || exit 1

# Updated CMD to use $PORT and include migrations
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py create_superuser && python manage.py collectstatic --noinput && gunicorn --bind 0.0.0.0:$PORT --workers 2 order_system.wsgi:application"]