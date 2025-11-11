# Use official Python image
FROM python:3.11-slim

# Install nginx, supervisor, and redis-server
RUN apt-get update && apt-get install -y nginx redis-server && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy all files
COPY . .

# Ensure a VERSION file is available inside the image for runtime version reporting
COPY VERSION /app/VERSION

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
# Install supervisor via pip to ensure a python entrypoint (avoids platform exec-format issues)
RUN pip install supervisor

# Expose only the nginx port
EXPOSE 8000

# Start all services with supervisor
CMD ["python", "-m", "supervisor.supervisord", "-c", "/app/supervisord.conf"]
