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

1. Create resource group:
	```sh
	az group create --name <resource-group> --location <location>
	```
2. Create AKS cluster (smallest VM):
	```sh
	az aks create --resource-group <resource-group> --name <aks-name> --node-count 1 --node-vm-size Standard_B2s --generate-ssh-keys --attach-acr <ACR_NAME>
	```
3. Get AKS credentials:
	```sh
	az aks get-credentials --resource-group <resource-group> --name <aks-name>
	```

---

## 3. Deploy Kubernetes Manifests

1. Apply all manifests:
	```sh
	kubectl apply -f k8s/
	```
2. (Optional) Install NGINX Ingress Controller:
	```sh
	kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.9.0/deploy/static/provider/cloud/deploy.yaml
	```
3. Update DNS or use external IP from Ingress for access.

---

## 4. Use Azure Free/Cheapest Tiers

- **AKS**: Control plane is free, pay for nodes. Use Standard_B2s for lowest cost.
- **ACR**: Use Basic SKU (free for small usage).
- **Redis**: Use Azure Cache for Redis (has free tier), or deploy in-cluster as shown in `redis-deployment.yaml`.
- **Storage**: Use Azure Storage (Blob/Table) for persistent storage (free tier available).
- **Key Vault**: Use Azure Key Vault for secrets (free tier available).

---

## 5. Environment Variables & Secrets
- Store secrets in Azure Key Vault or Kubernetes secrets.
- Update manifests to use secrets as needed.

---

## 6. Clean Up Resources
To avoid charges, delete resources when done:
```sh
az group delete --name <resource-group>
```

---

## References
- [AKS Pricing](https://azure.microsoft.com/en-us/pricing/details/kubernetes-service/)
- [Azure Free Services](https://azure.microsoft.com/en-us/free/)
- [Azure Cache for Redis](https://azure.microsoft.com/en-us/services/cache/)

