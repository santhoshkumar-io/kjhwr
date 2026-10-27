# Python 3.12 to match decision 0003 and Vercel's default runtime, so the
# container and production run the same interpreter.
FROM python:3.12-slim

WORKDIR /srv

# Dependencies first, so editing application code does not reinvalidate the
# layer that installs them.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY data/ ./data/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/srv \
    DATA_DIR=/srv/data

EXPOSE 8000

# Phase 8 adds a non-root user and image hardening. Noted here so the gap is
# deliberate rather than forgotten.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
