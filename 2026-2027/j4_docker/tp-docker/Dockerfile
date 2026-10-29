FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --uid 1000 --create-home appuser

COPY . .

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s CMD ["python", "healthcheck.py"]

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
