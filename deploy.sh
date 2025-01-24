#!/bin/bash

# Variables
RESOURCE_GROUP="VideoShotAnalysisResourceGroup"
ACR_NAME="videoshotanalysisacr"
APP_SERVICE_PLAN="VideoShotAnalysisAppServicePlan"
WEB_APP_NAME="videoshotanalysisapp"
LOCATION="eastus"
IMAGE_NAME="video-shot-analysis-demo"
DOCKER_IMAGE_TAG="latest"

# Check if already logged in to Azure
if ! az account show &>/dev/null; then
    echo "Logging in to Azure..."
    az login
else
    echo "Already logged in to Azure."
fi

# Set the subscription
SUBSCRIPTION_ID="$(az account show --query 'id' -o tsv)"
az account set --subscription "$SUBSCRIPTION_ID"

# Create a resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create an Azure Container Registry
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic --admin-enabled true

# Login to the Azure Container Registry
az acr login --name $ACR_NAME

# Build the Docker image
docker build --platform linux/amd64 -t $ACR_NAME.azurecr.io/$IMAGE_NAME:$DOCKER_IMAGE_TAG .

# Push the Docker image to the Azure Container Registry
docker push $ACR_NAME.azurecr.io/$IMAGE_NAME:$DOCKER_IMAGE_TAG

# The P1V3 tier (Premium v3 - P1v3) provides more CPU and memory resources for production workloads
# Create an App Service plan
az appservice plan create --name $APP_SERVICE_PLAN --resource-group $RESOURCE_GROUP --sku P1V3 --is-linux

# Create a Web App for Containers
az webapp create --resource-group $RESOURCE_GROUP --plan $APP_SERVICE_PLAN --name $WEB_APP_NAME
az webapp config container set --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP --container-image-name $ACR_NAME.azurecr.io/$IMAGE_NAME:$DOCKER_IMAGE_TAG --container-registry-url https://$ACR_NAME.azurecr.io

# Load environment variables from .env file
set -a
source .env
set +a

# Set environment variables in Azure Web App
az webapp config appsettings set --resource-group $RESOURCE_GROUP --name $WEB_APP_NAME --settings \
    AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT \
    AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY \
    AZURE_OPENAI_API_VERSION=$AZURE_OPENAI_API_VERSION \
    AZURE_OPENAI_DEPLOYMENT_NAME=$AZURE_OPENAI_DEPLOYMENT_NAME \
    WHISPER_ENDPOINT=$WHISPER_ENDPOINT \
    WHISPER_API_KEY=$WHISPER_API_KEY \
    WHISPER_API_VERSION=$WHISPER_API_VERSION \
    WHISPER_DEPLOYMENT_NAME=$WHISPER_DEPLOYMENT_NAME \
    SYSTEM_PROMPT="$SYSTEM_PROMPT"

echo "Deployment completed. You can access your Streamlit app at https://$WEB_APP_NAME.azurewebsites.net"
