#!/bin/bash
# Deployment script template for Task Assist
# Builds and pushes Docker image to Docker Hub
#
# Usage: Copy this to deploy.sh and replace <YOUR_DOCKERHUB_USERNAME> with your username

set -e  # Exit on error

# Configuration
DOCKERHUB_USERNAME="<YOUR_DOCKERHUB_USERNAME>"
IMAGE_NAME="task-manager"
VERSION_TAG="v1-amd64"

echo "==================================="
echo "Task Assist Deployment Script"
echo "==================================="

# Build for linux/amd64 and tag
echo ""
echo "Building image for linux/amd64..."
podman build --platform linux/amd64 -t docker.io/${DOCKERHUB_USERNAME}/${IMAGE_NAME}:${VERSION_TAG} .

# Push to Docker Hub
echo ""
echo "Pushing image to Docker Hub..."
podman push docker.io/${DOCKERHUB_USERNAME}/${IMAGE_NAME}:${VERSION_TAG}

echo ""
echo "==================================="
echo "✅ Deployment complete!"
echo "==================================="
echo "Image: docker.io/${DOCKERHUB_USERNAME}/${IMAGE_NAME}:${VERSION_TAG}"
