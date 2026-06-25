FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# FastAPI 포트 노출
EXPOSE 8005

# 서버 실행 (uvicorn)
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8005"]
