FROM python:3.8

# Install poetry
ENV POETRY_VERSION=1.1.4
RUN pip install "poetry==$POETRY_VERSION"

# Install the project
WORKDIR /db-update-util
ADD poetry.lock pyproject.toml /db-update-util/
RUN poetry config virtualenvs.create false && poetry install

# Copy project files
ADD src /db-update-util/src
ADD tests /db-update-util/tests

EXPOSE 80

ENTRYPOINT ["python"]
CMD ["src/main.py"]