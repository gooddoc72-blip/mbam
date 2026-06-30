# MBAM 백엔드(분석/계정/관리) - Railway 배포용
# Playwright 공식 이미지(브라우저 + 시스템 의존성 포함, playwright==1.59.0 매칭)
FROM mcr.microsoft.com/playwright/python:v1.59.0-jammy

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1

# 의존성 먼저 (레이어 캐시)
COPY requirements.cloud.txt .
RUN pip install --no-cache-dir -r requirements.cloud.txt

# 백엔드 코드 (프론트 mbam-web 은 Vercel 이 담당하므로 제외)
COPY mbam_nextgen ./mbam_nextgen
COPY run_backend.py .

# Railway 가 $PORT 를 주입 → run_backend.py 가 읽음
EXPOSE 8000
CMD ["python", "run_backend.py"]
