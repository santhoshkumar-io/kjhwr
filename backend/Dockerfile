# Python 3.12 to match decision 0003 and Vercel's default runtime, so the
# container and production run the same interpreter.
#
# Pinned to the patch version rather than the floating 3.12-slim tag: that tag moves
# whenever upstream publishes a new patch, so two people building "the same" image on
# different days could get different interpreters.
FROM python:3.12.16-slim

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

# Run as a normal user. Nothing here needs root: the dependencies are already
# installed, the data is read-only at runtime, and the port is above 1024.
#
# Honest framing, per decision 0003: Vercel never builds this Dockerfile - it builds a
# Python function from the same source. So this hardens the development environment and
# satisfies the brief's Docker requirement; it is not what protects production.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /srv
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
