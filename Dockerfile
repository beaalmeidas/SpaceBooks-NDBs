FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-db.txt .
RUN --mount=type=secret,id=pip_ca,required=false \
    if [ -f /run/secrets/pip_ca ]; then \
      PIP_CERT=/run/secrets/pip_ca pip install --no-cache-dir -r requirements-db.txt; \
    else \
      pip install --no-cache-dir -r requirements-db.txt; \
    fi
COPY src ./src
COPY tests ./tests
COPY data/books-processed.csv data/users.csv ./data/
CMD ["python", "-m", "src.bootstrap", "--prepare"]
