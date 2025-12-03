# Quick Start: Database Persistence

## For Local Development

**Option 1: Docker Compose (Recommended)**
```bash
# Start everything with persistent storage
docker-compose up --build

# Your data is now safe! It persists in the 'task-manager-db' volume
```

**Option 2: Standalone Docker**
```bash
docker build -t task-assist .
docker run -p 8000:8000 \
  -v task-manager-data:/app/data \
  -e DATABASE_PATH=/app/data/task_manager.db \
  --env-file .env \
  task-assist
```

**Test it works:**
1. Open http://localhost:8000
2. Create some work/tasks
3. Stop and rebuild: `docker-compose down && docker-compose up --build`
4. Data should still be there ✓

---

## For Azure Web App

**Quick Setup (5 commands):**
```bash
# Set your variables
RG="your-resource-group"
APP="your-app-name"
STORAGE="yourstorageacct"  # must be unique, lowercase, no dashes

# 1. Create storage account
az storage account create --name $STORAGE --resource-group $RG --sku Standard_LRS

# 2. Get storage key
KEY=$(az storage account keys list --account-name $STORAGE --resource-group $RG --query "[0].value" -o tsv)

# 3. Create file share
az storage share create --name task-manager-data --account-name $STORAGE --account-key $KEY --quota 1

# 4. Mount to web app
az webapp config storage-account add \
  --resource-group $RG \
  --name $APP \
  --custom-id TaskManagerData \
  --storage-type AzureFiles \
  --share-name task-manager-data \
  --account-name $STORAGE \
  --access-key $KEY \
  --mount-path /app/data

# 5. Set database path and restart
az webapp config appsettings set --resource-group $RG --name $APP --settings DATABASE_PATH=/app/data/task_manager.db
az webapp restart --name $APP --resource-group $RG
```

**Done!** Your database now persists across redeployments.

---

## Backup & Restore

```bash
# Backup your database
python scripts/manage_db_volume.py backup ./my_backup.db

# Restore from backup
python scripts/manage_db_volume.py restore ./my_backup.db

# List what's in the volume
python scripts/manage_db_volume.py list
```

---

## Troubleshooting

**"Database not found" after restart?**
- Check: `docker volume ls` - is `task-manager-db` there?
- Check: `docker inspect <container>` - is volume mounted to `/app/data`?
- Check: Environment variable `DATABASE_PATH=/app/data/task_manager.db`

**Azure: "File not found"?**
- Verify mount: `az webapp config storage-account list --name $APP --resource-group $RG`
- Check logs: `az webapp log tail --name $APP --resource-group $RG`
- SSH and verify: `az webapp ssh --name $APP --resource-group $RG` then `ls -la /app/data`

**Want to start fresh?**
```bash
# Delete volume (WARNING: destroys all data)
docker volume rm task-manager-db
# Or use the helper:
python scripts/manage_db_volume.py delete
```

---

## More Details

- **Full guide:** See `docs/DATABASE_PERSISTENCE.md`
- **Azure setup:** See `docs/DEPLOYMENT.md`
- **Implementation:** See `docs/PERSISTENCE_IMPLEMENTATION.md`
