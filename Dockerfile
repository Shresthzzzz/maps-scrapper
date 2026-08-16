# Use slim Python base image
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HEADLESS=true

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Automatically install correct OS dependencies & Chromium browser via Playwright
RUN playwright install-deps chromium && playwright install chromium

COPY . .

CMD ["python", "bot.py"]
