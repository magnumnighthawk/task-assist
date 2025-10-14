# Use official Python image
FROM python:3.11-slim

# Install nginx and supervisor
RUN apt-get update && apt-get install -y nginx supervisor && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy all files
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose only the nginx port
EXPOSE 8000

# Start all services with supervisor
CMD ["supervisord", "-c", "/app/supervisord.conf"]
