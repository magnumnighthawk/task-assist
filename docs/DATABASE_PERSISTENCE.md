# Database Persistence Guide

## Problem
SQLite database (`task_manager.db`) is stored inside the container and gets wiped on every rebuild/redeploy.

## Solution
Mount a persistent volume to `/app/data` and configure the app to use `/app/data/task_manager.db`.

---

## Quick Reference by Platform

### Local Development - Docker Compose
```bash
docker-compose up --build
```
✅ Volume automatically mounted via `docker-compose.yml`
✅ Data persists in named volume `task-manager-db`

### Local Development - Standalone Docker/Podman
```bash
# Build image
podman build -t task-assist .

# Run with persistent volume
podman run -p 8000:8000 \
  -v task-manager-data:/app/data \
  -e DATABASE_PATH=/app/data/task_manager.db \
  --env-file .env \
  task-assist
```

### Azure Web App for Containers

**Step 1: Create Storage Account & File Share**
```bash
STORAGE_ACCOUNT="taskassistdata"
RG="your-resource-group"
LOCATION="eastus"

az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RG \
  --location $LOCATION \
  --sku Standard_LRS

STORAGE_KEY=$(az storage account keys list \
  --account-name $STORAGE_ACCOUNT \
  --resource-group $RG \
  --query "[0].value" -o tsv)

az storage share create \
  --name task-manager-data \
  --account-name $STORAGE_ACCOUNT \
  --account-key $STORAGE_KEY \
  --quota 1
```

**Step 2: Mount to Web App**
```bash
APP_NAME="your-app-name"

az webapp config storage-account add \
  --resource-group $RG \
  --name $APP_NAME \
  --custom-id TaskManagerData \
  --storage-type AzureFiles \
  --share-name task-manager-data \
  --account-name $STORAGE_ACCOUNT \
  --access-key $STORAGE_KEY \
  --mount-path /app/data
```

**Step 3: Set Database Path**
```bash
az webapp config appsettings set \
  --resource-group $RG \
  --name $APP_NAME \
  --settings DATABASE_PATH=/app/data/task_manager.db

az webapp restart --name $APP_NAME --resource-group $RG
```

### AWS (ECS/Elastic Beanstalk)
1. Create EFS file system
2. Mount to `/app/data` in task definition
3. Set `DATABASE_PATH=/app/data/task_manager.db` environment variable

### Google Cloud Run
1. Create Cloud Filestore instance
2. Mount volume to `/app/data`
3. Set `DATABASE_PATH=/app/data/task_manager.db` environment variable

Note: Cloud Run has limited persistent storage support. Consider Cloud SQL for production.

### Generic Docker Host (VPS/Dedicated Server)
```bash
# Create directory on host
mkdir -p /opt/task-manager/data

# Run with bind mount
docker run -p 8000:8000 \
  -v /opt/task-manager/data:/app/data \
  -e DATABASE_PATH=/app/data/task_manager.db \
  --env-file .env \
  --restart unless-stopped \
  task-assist
```

---

## Verification

### Check if database is persisted
```bash
# Local Docker
docker exec <container_id> ls -lh /app/data/

# Azure Web App
az webapp ssh --name <app_name> --resource-group <rg>
ls -lh /app/data/
```

### Test persistence
1. Create some work/tasks in the UI
2. Rebuild and redeploy container
3. Check if data is still there

---

## Troubleshooting

### Database file not found
- Check `DATABASE_PATH` environment variable is set correctly
- Verify volume is mounted: `docker inspect <container>` or check Azure mount config
- Check file permissions in `/app/data`

### Permission denied errors
```bash
# Fix permissions on host (for bind mounts)
sudo chown -R 1000:1000 /opt/task-manager/data

# Or run container with appropriate user
docker run --user 1000:1000 ...
```

### Azure Storage mount not working
- Verify storage account key is correct
- Check mount path doesn't have typos: `/app/data` (not `/app/data/`)
- View app settings: `az webapp config appsettings list --name <app> --resource-group <rg>`
- Check logs: `az webapp log tail --name <app> --resource-group <rg>`

### Want to migrate existing data
```bash
# Copy database from container to host
docker cp <container_id>:/app/task_manager.db ./backup.db

# Copy to persistent volume
docker run --rm -v task-manager-data:/data -v $(pwd):/backup \
  alpine cp /backup/backup.db /data/task_manager.db
```

---

## Migration Path

If you already have deployed containers without persistence:

1. **Backup existing data** (if any):
   ```bash
   docker cp <container>:/app/task_manager.db ./backup.db
   ```

2. **Set up persistent storage** (follow platform-specific steps above)

3. **Restore data** to the mounted volume:
   ```bash
   # For Docker: copy to volume
   docker run --rm -v task-manager-data:/app/data -v $(pwd):/backup \
     alpine cp /backup/backup.db /app/data/task_manager.db
   
   # For Azure: use Azure Storage Explorer or az storage file upload
   ```

4. **Redeploy** with persistent storage configured

---

## Best Practices

- ✅ Always use persistent volumes for production deployments
- ✅ Set `DATABASE_PATH` environment variable explicitly
- ✅ Test persistence by rebuilding containers
- ✅ Keep backups of your database file
- ✅ Use named volumes (not anonymous volumes) for easier management
- ✅ Document storage configuration in deployment runbooks

## Alternative: Use PostgreSQL/MySQL

For production at scale, consider migrating to PostgreSQL or MySQL:
- Better concurrent access
- Native cloud database services (Azure SQL, AWS RDS, Cloud SQL)
- Automatic backups and high availability
- No need to manage file storage

Update `db.py`:
```python
# PostgreSQL example
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///task_manager.db')
engine = create_engine(DATABASE_URL)
```

Then set `DATABASE_URL` to your cloud database connection string.
