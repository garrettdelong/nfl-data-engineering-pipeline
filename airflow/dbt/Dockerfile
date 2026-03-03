FROM python:3.11-slim

WORKDIR /usr/app

# Optional but helpful packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
 && rm -rf /var/lib/apt/lists/*

# Install dbt (pin versions)
RUN pip install --no-cache-dir \
    dbt-core==1.11.0 \
    dbt-snowflake==1.11.0

# Default entrypoint can be dbt
ENTRYPOINT ["dbt"]