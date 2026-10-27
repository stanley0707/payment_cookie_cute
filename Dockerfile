FROM python:3.13-slim-bookworm AS base

ARG PYPI_INDEX_URL=https://pypi.org/simple
ARG POETRY_VERSION=2.5.1

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=$PYPI_INDEX_URL \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /usr/src/app

RUN rm -rf /var/lib/apt/lists/* /root/.cache/* /root/.config/* /root/.local/*

RUN groupadd -g 1001 appuser \
 && useradd -r -u 1001 -g appuser -m -d /home/appuser appuser \
 && chown -R appuser:appuser /usr/src/app \
 && chmod 755 /usr/src/app \

# ---------- Production deps ----------
FROM base AS prod-deps

COPY pyproject.toml poetry.lock ./

RUN pip install "poetry==$POETRY_VERSION" \
 && poetry install --no-root --only main \
 && pip uninstall -y poetry \
 && rm -rf /var/lib/apt/lists/* /root/.cache/* /root/.config/* /root/.local/*

# ---------- Dev deps ----------
FROM prod-deps AS dev-deps

RUN pip install "poetry==$POETRY_VERSION" \
 && poetry install --no-root --only dev \
 && pip uninstall -y poetry \
 && rm -rf /root/.cache/* /root/.config/* /root/.local/*

# ---------- Code ----------
FROM base AS code-layer
COPY ./payment_cookie_cute ./payment_cookie_cute

# ---------- API (prod-like) ----------
FROM prod-deps AS main
COPY --from=code-layer --chown=appuser:appuser /usr/src/app/ ./
USER appuser
CMD ["gunicorn", "payment_cookie_cute.app:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--log-level", "info", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", "--error-logfile", "-"]

# ---------- API (dev) ----------
FROM dev-deps AS dev
COPY --from=code-layer --chown=appuser:appuser /usr/src/app/ ./
USER appuser
CMD ["uvicorn", "payment_cookie_cute.app:app", \
     "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------- Consumer ----------
FROM prod-deps AS consumer
COPY --from=code-layer --chown=appuser:appuser /usr/src/app/ ./
COPY --chown=appuser:appuser ./consumer ./consumer
USER appuser
CMD ["python", "-m", "consumer.main"]

# ---------- Consumer ----------
FROM prod-deps AS outbox_relay
COPY --from=code-layer --chown=appuser:appuser /usr/src/app/ ./
COPY --chown=appuser:appuser ./consumer ./consumer
USER appuser
CMD ["python", "-m", "outbox_relay.main"]

# ---------- Migrations ----------
FROM prod-deps AS migrations
COPY --from=code-layer --chown=appuser:appuser /usr/src/app/ ./
COPY --chown=appuser:appuser ./alembic ./alembic
COPY --chown=appuser:appuser alembic.ini ./
USER appuser
CMD ["alembic", "upgrade", "head"]

# ---------- Tests ----------
FROM dev-deps AS tests
COPY --from=code-layer --chown=appuser:appuser /usr/src/app/ ./
COPY --chown=appuser:appuser ./tests ./tests
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser ./alembic ./alembic

USER appuser
CMD ["sh", "-c", "python -m alembic upgrade head && python -m pytest tests -v"]