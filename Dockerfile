FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1
CMD ["python", "-m", "shadow.run", "--month", "2026-11"]