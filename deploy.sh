#!/bin/zsh
# Deploy script for Azure Web App

# Name of the zip file
deploy_zip="slack-interactions.zip"

# Remove old zip if exists
if [ -f "$deploy_zip" ]; then
    rm "$deploy_zip"
fi

# Zip all files in the current directory, excluding the zip itself, __pycache__, venv, .venv, .git folders, and .gitignore files
zip -r "$deploy_zip" . -x "$deploy_zip" -x "__pycache__/*" -x "venv/*" -x ".venv/*" -x ".git/*" -x ".gitignore"

# Deploy to Azure Web App
az webapp deploy --resource-group small-apps --name slack-interactions --src-path "$deploy_zip" --type zip
