FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8005

# server.py 안의 uvicorn.run 이 PORT 환경변수를 사용
CMD ["python", "server.py"]
