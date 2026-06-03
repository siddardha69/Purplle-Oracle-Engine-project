FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies for OpenCV and Git
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Set environment variables (pointing backend to local sqlite and redis fallback)
ENV ENVIRONMENT=production
ENV DATABASE_URL=sqlite:///./store_intelligence.db
ENV REDIS_URL=redis://localhost:6379/0
ENV API_HOST=localhost
ENV API_PORT=8000

# Expose Streamlit port (Hugging Face routes traffic through 7860)
EXPOSE 7860

# Make start script executable and define it as entrypoint
RUN chmod +x start.sh
CMD ["./start.sh"]
