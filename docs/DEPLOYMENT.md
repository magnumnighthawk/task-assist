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

## Database Persistence

The application uses SQLite and stores data in `/app/data/task_manager.db`. To persist data across container rebuilds:

### Local Development (Docker Compose)
Use the provided `docker-compose.yml` which mounts a named volume:
```bash
docker-compose up --build
```
Data persists in the `task-manager-db` Docker volume across rebuilds.

### Azure Web App
Mount Azure Storage as a persistent volume:
1. Create a storage account and file share
2. Mount it to `/app/data` in your Web App settings
3. Set `DATABASE_PATH=/app/data/task_manager.db` as an app setting

See "Data Persistence on Azure" section below for detailed steps.

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
	
	# Build for Azure App Service (linux/amd64 platform)
	podman build --platform linux/amd64 -t docker.io/<username>/task-manager:v1-amd64 .
	```

2. Push to your registry:
	```bash
	# Push to Azure Container Registry (ACR)
	az acr login --name <ACR_NAME>
	podman push myregistry/myrepo/task-assist:v1.0.0
	
	# Push to Docker Hub (for Azure App Service)
	podman push docker.io/<username>/task-manager:v1-amd64
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

## Data Persistence on Azure Web App

Azure Web App containers are ephemeral - data is lost on restart/redeploy. To persist the SQLite database:

### Step 1: Create Azure Storage Account and File Share

```bash
# Create storage account (use same resource group as your web app)
az storage account create \
  --name <storage_account_name> \
  --resource-group <rg> \
  --location <location> \
  --sku Standard_LRS

# Get storage account key
STORAGE_KEY=$(az storage account keys list \
  --account-name <storage_account_name> \
  --resource-group <rg> \
  --query "[0].value" -o tsv)

# Create file share for database
az storage share create \
  --name task-manager-data \
  --account-name <storage_account_name> \
  --account-key $STORAGE_KEY \
  --quota 1
```

### Step 2: Mount Storage to Web App

```bash
# Add the storage mount to your web app
az webapp config storage-account add \
  --resource-group <rg> \
  --name <app_name> \
  --custom-id TaskManagerData \
  --storage-type AzureFiles \
  --share-name task-manager-data \
  --account-name <storage_account_name> \
  --access-key $STORAGE_KEY \
  --mount-path /app/data
```

### Step 3: Set Database Path Environment Variable

```bash
az webapp config appsettings set \
  --resource-group <rg> \
  --name <app_name> \
  --settings DATABASE_PATH=/app/data/task_manager.db
```

### Step 4: Restart Web App

```bash
az webapp restart --name <app_name> --resource-group <rg>
```

Your database will now persist across container rebuilds and redeployments!

### Alternative: Other Cloud Providers

The same pattern works on other platforms:

**AWS Elastic Beanstalk / ECS:**
- Use EFS (Elastic File System) mounted to `/app/data`
- Set `DATABASE_PATH` environment variable

**Google Cloud Run:**
- Mount Cloud Filestore or use Cloud SQL for PostgreSQL
- For SQLite: use persistent disks with volume mounts

**Generic Docker Host:**
- Use bind mount: `-v /host/path/data:/app/data`
- Or named volume: `-v task-manager-db:/app/data`

## Clean up resources
To avoid charges, delete the resource group when you are finished:
```bash
az group delete --name <rg>
```

----

## Helpful references
- Azure Web Apps for Containers: https://learn.microsoft.com/azure/app-service/quickstart-docker
- az webapp config container: https://learn.microsoft.com/cli/azure/webapp/config/container
- Azure Storage mounting: https://learn.microsoft.com/azure/app-service/configure-connect-to-azure-storage

