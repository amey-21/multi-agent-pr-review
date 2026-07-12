# ---------- STAGE 1: builder ----------
FROM python:3.12-slim AS builder

WORKDIR /app

# install build dependencies needed only to INSTALL packages,
# not to run them
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY requirements.txt* .

# install into a separate prefix we can cleanly copy later
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---------- STAGE 2: runtime ----------
FROM python:3.12-slim AS runtime

WORKDIR /app

# install ONLY the CLI tools we actually need at runtime — 
# Semgrep, Bandit, Ruff, Radon, pydocstyle are all pip-installable,
# so they get copied over with the rest of Stage 1's packages below,
# no separate apt-get needed for them specifically
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# copy ONLY the installed packages from the builder stage — 
# none of gcc, pip's build cache, or apt's package lists come along
COPY --from=builder /install /usr/local

COPY src/ ./src/
COPY mcp/ ./mcp/

# CRITICAL: same stdin fix you already discovered is needed, but 
# now baked in as a Docker-level environment default rather than 
# something only your local .env handles
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "src.webhook.app:app", "--host", "0.0.0.0", "--port", "8000"]