# Use official Playwright image pre-packaged with Python 3.11 and Chromium browser
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HEADLESS=true

# Set working directory
WORKDIR /app

# Copy requirement files first for layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Run Telegram bot
CMD ["python", "bot.py"]
