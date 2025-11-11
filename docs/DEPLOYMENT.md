# Azure Kubernetes Deployment Guide

This guide helps you deploy the Task Manager application (Flask, Streamlit, Celery, Redis) on Azure Kubernetes Service (AKS) using the cheapest/free-tier options.

## Prerequisites
- Azure account (free tier available)
- Azure CLI installed
- Docker installed
- kubectl installed

---

## 1. Build and Push Docker Images to Azure Container Registry (ACR)

1. Create a free-tier ACR:
	```sh
	az acr create --resource-group <resource-group> --name <ACR_NAME> --sku Basic
	```
2. Log in to ACR:
	```sh
	az acr login --name <ACR_NAME>
	```
3. Build and tag images:
	```sh
	docker build -t <ACR_NAME>.azurecr.io/flask-app:latest -f Dockerfile .
	docker build -t <ACR_NAME>.azurecr.io/streamlit-app:latest -f Dockerfile .
	docker build -t <ACR_NAME>.azurecr.io/celery-worker:latest -f Dockerfile .
	```
4. Push images:
	```sh
	docker push <ACR_NAME>.azurecr.io/flask-app:latest
	docker push <ACR_NAME>.azurecr.io/streamlit-app:latest
	docker push <ACR_NAME>.azurecr.io/celery-worker:latest
	```

---

## 2. Create AKS Cluster (Cheapest Option)

# Azure Web App (Single-container) Deployment Guide

This project is intended to be deployed as a single container on Azure Web App for Containers (instead of AKS). That keeps the deployment simple and cost-effective while still allowing automated updates via image tags (semantic version tags or commit SHAs).

## Why single-container on Azure Web App
- Simpler and cheaper than running AKS for small projects.
- All services (Flask API, Streamlit UI, Celery worker managed by Supervisor, Nginx) run inside one container using Supervisor.
- Easy to push a single image to a registry (ACR or Docker Hub) and point an Azure Web App to that image.

## Prerequisites
- Azure account
- Azure CLI (az)
- Podman or Docker (podman is recommended for rootless builds on dev machines)
- An image registry (Azure Container Registry or Docker Hub)

----

## Quick deploy (recommended)

1. Build and tag locally (use semantic tags like v1.0.0 or the short git SHA):
	```bash
	# tag using semantic version
	podman build -t myregistry/myrepo/task-assist:v1.0.0 -f Dockerfile .

	# or tag with short commit SHA (recommended for CI/CD)
	podman build -t myregistry/myrepo/task-assist:$(git rev-parse --short HEAD) -f Dockerfile .
	```

2. Push to your registry (ACR example):
	```bash
	az acr login --name <ACR_NAME>
	podman push myregistry/myrepo/task-assist:v1.0.0
	```

3. Create an Azure Web App for Containers and point it to the image:
	```bash
	# create resource group and App Service plan
	az group create -n <rg> -l <location>
	az appservice plan create -n <plan> -g <rg> --is-linux --sku B1

	# create the webapp
	az webapp create -n <app_name> -g <rg> --plan <plan> --deployment-container-image-name myregistry/myrepo/task-assist:v1.0.0
	```

4. Configure environment variables in the Azure portal (or via CLI). Important ones:
	- SECRET_KEYS, SLACK_WEBHOOK, GOOGLE_CREDENTIALS, etc. (See `.env.sample`)
	- IMAGE_TAG — optional but useful: set to the value you used to tag the image (e.g. v1.0.0 or the commit SHA). The app exposes `/version` to report this.

5. Use Azure Log Stream to view logs from Supervisor-managed processes.

----

## Versioning & identifying the deployed version

There are two simple and compatible approaches to identify and control which version is deployed:

- Tagged images (recommended): push images with semantic tags (v1.2.0) and/or commit SHAs (e.g. 1a2b3c4). In Azure Web App, set the container image to the exact tag you want to run. This is easy to roll back or promote.
- IMAGE_TAG/commit file (fallback): the container reads an application `VERSION` file or environment variable `IMAGE_TAG` and serves it at `/version`. During CI/CD set IMAGE_TAG env var in Azure Web App settings to the deployed tag.

Commands to inspect deployed image in Azure:

```bash
# Show the configured container image for a webapp
az webapp config container show --name <app_name> --resource-group <rg>

# Show site configuration (contains linuxFxVersion with image name)
az webapp show -n <app_name> -g <rg> --query properties.siteConfig.linuxFxVersion -o tsv
```

If you set the `IMAGE_TAG` application setting, you can also call the app's `/version` endpoint:

```bash
curl https://<app_name>.azurewebsites.net/version
```

This will return a small JSON object with the string used for the deployed image (tag or commit) and the source (env or file).

----

## CI/CD notes

- In CI (GitHub Actions / Azure Pipelines), build and tag with both semantic tag and short SHA, push both tags to registry, then update Azure Web App to point to the desired tag. Example GitHub Actions step:

```yaml
- name: Build and push
  run: |
	TAG=${{ github.ref_name }} || $(git rev-parse --short HEAD)
	podman build -t myregistry/myrepo/task-assist:${{ github.sha }} -t myregistry/myrepo/task-assist:${{ github.ref_name }} .
	podman push myregistry/myrepo/task-assist:${{ github.sha }}
	podman push myregistry/myrepo/task-assist:${{ github.ref_name }}
```

Local version bumping helper

This repo includes a small helper script at `scripts/bump_version.py` that scans git commits since the last tag and suggests a semantic version bump (major/minor/patch) using Conventional Commit cues. Use it locally to prepare a release, or wire it into your CI to produce the VERSION file and tags.

Example (dry run):

```bash
python3 scripts/bump_version.py
```

Apply the bump, commit VERSION and create a tag:

```bash
python3 scripts/bump_version.py --apply --commit --tag
```

----

## Environment variables & secrets

- Store secrets in Azure App Service application settings or use Key Vault and reference from App Service.
- Keep `.env` locally only for development. Do NOT commit secrets to the repo.

----

## Clean up resources
To avoid charges, delete the resource group when you are finished:
```bash
az group delete --name <rg>
```

----

## Helpful references
- Azure Web Apps for Containers: https://learn.microsoft.com/azure/app-service/quickstart-docker
- az webapp config container: https://learn.microsoft.com/cli/azure/webapp/config/container

