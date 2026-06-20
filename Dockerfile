# syntax=docker/dockerfile:1

# --- Stage 1: build/install dependencies in isolation -----------------------
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .

# --user installs to a local site-packages dir we can copy wholesale into
# the final stage, instead of carrying pip's cache and build tooling into
# the shipped image.
RUN pip install --no-cache-dir --user -r requirements.txt

# --- Stage 2: runtime image ---------------------------------------------------
FROM python:3.12-slim

# Run as a non-root user. This pipeline writes to data/raw, data/processed,
# and docs/ at runtime (scrape-prices, validate) - granting only that user
# ownership instead of running as root limits the blast radius of any bug
# in a dependency (e.g. the BeautifulSoup/requests scraping path, which
# handles untrusted HTML from external sites).
RUN useradd --create-home --shell /bin/bash pipeline
WORKDIR /app

COPY --from=builder /root/.local /home/pipeline/.local
COPY . .

RUN chown -R pipeline:pipeline /app
USER pipeline

ENV PATH=/home/pipeline/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

# No EXPOSE - this is a CLI/batch pipeline (main.py), not a server.

# Default to the one command that needs no network access and no scraped
# credentials: validate the dataset already shipped in the image. Override
# at `docker run` time for scrape-prices / scrape-dividends / etc., e.g.:
#   docker run --rm idx-data-pipeline python main.py scrape-prices
ENTRYPOINT ["python", "main.py"]
CMD ["validate"]
