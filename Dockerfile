FROM python:3.8

# Install poetry
ENV POETRY_VERSION=1.1.4
RUN pip install "poetry==$POETRY_VERSION"

# Copy in the config files:
WORKDIR /app
COPY pyproject.toml poetry.lock ./
# Install only dependencies:
RUN poetry install --no-root --no-dev

# Copy in everything else and install:
COPY . .
CMD ["uvicorn", "main:app"]
