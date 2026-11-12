FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
ARG REQUIREMENTS_FILE=requirements-db.txt
COPY requirements-db.txt requirements-app.txt ./
RUN --mount=type=secret,id=pip_ca,required=false \
    if [ -f /run/secrets/pip_ca ]; then \
      PIP_CERT=/run/secrets/pip_ca pip install --no-cache-dir -r "$REQUIREMENTS_FILE"; \
    else \
      pip install --no-cache-dir -r "$REQUIREMENTS_FILE"; \
    fi
COPY src ./src
COPY tests ./tests
COPY data/books-processed.csv data/users.csv ./data/
COPY data/recommendation-demo.json ./data/
CMD ["python", "-m", "src.bootstrap", "--prepare"]
