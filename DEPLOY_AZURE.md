# Deploying ComicMe to Azure Container Apps

This guide walks you through deploying the ComicMe backend to Azure Container Apps (ACA). The frontend stays on Vercel (or optionally moves to Azure Static Web Apps). External services (Neon Postgres, Cloudflare R2) remain unchanged.

---

## Prerequisites

1. **Azure account** — [Free trial](https://azure.microsoft.com/free/) or existing subscription
2. **Azure CLI** installed — https://learn.microsoft.com/cli/azure/install-azure-cli
3. **Docker** installed — https://www.docker.com/get-docker
4. **GitHub account** (for CI/CD)
5. **Existing services** (unchanged):
   - Neon Postgres connection string
   - Cloudflare R2 credentials (Account ID, Access Key, Secret Key, Bucket)
   - Resend API key
   - Gemini API key
   - Razorpay keys (if using payments)

---

## Step 1: Log in to Azure

```bash
az login
```

Choose your subscription. Note the output.

---

## Step 2: Create a Resource Group

A resource group is a logical container for all Azure resources.

```bash
az group create --name rg-comicme --location eastus2
```

You can change `eastus2` to any region near your users.

---

## Step 3: Create Azure Container Registry (ACR)

This stores your Docker image.

```bash
az acr create --name comicmeacr --resource-group rg-comicme --sku Basic --admin-enabled true
```

Note the login server name: `comicmeacr.azurecr.io`

---

## Step 4: Build and Push the Docker Image

```bash
# Build the image
docker build -t comicme-backend:latest .

# Tag it for ACR
docker tag comicme-backend:latest comicmeacr.azurecr.io/comicme-backend:v1

# Login to ACR
az acr login --name comicmeacr

# Push
docker push comicmeacr.azurecr.io/comicme-backend:v1
```

---

## Step 5: Create the Container Apps Environment

This is the infrastructure that runs your containers.

```bash
az containerapp env create \
  --name comicme-env \
  --resource-group rg-comicme \
  --location eastus2 \
  --cpu 2 \
  --memory 8Gi
```

Adjust `--cpu` and `--memory` based on your expected load. The ML stack (torch) needs at least 2 CPU and 4GB RAM. 8GB is recommended for comfort.

---

## Step 6: Create the Container App

```bash
az containerapp create \
  --name comicme-api \
  --resource-group rg-comicme \
  --environment comicme-env \
  --image comicmeacr.azurecr.io/comicme-backend:v1 \
  --registry-server comicmeacr.azurecr.io \
  --registry-username comicmeacr \
  --registry-password $(az acr credential show -n comicmeacr --query passwords[0].value -o tsv) \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 5 \
  --cpu 2 \
  --memory 8Gi \
  --env-vars \
    ENVIRONMENT=production \
    SECRET_KEY=<your-production-secret-key> \
    GEMINI_API_KEY=<your-gemini-api-key> \
    GEMINI_TEXT_MODEL=gemini-2.5-flash \
    GEMINI_IMAGE_MODEL_MULTIMODAL=gemini-2.5-flash-image \
    GEMINI_IMAGE_MODEL_TXT2IMG=imagen-4.0-generate-001 \
    GEMINI_IMAGE_MODEL_SUBJECT_REF=imagen-3.0-capability-001 \
    DATABASE_URL=<your-neon-connection-string> \
    DB_HOST= \
    DB_PORT=5432 \
    DB_USER= \
    DB_PASSWORD= \
    DB_NAME=neondb \
    DB_SSLMODE=require \
    CORS_ORIGINS=https://your-frontend-domain.vercel.app \
    R2_ENABLED=true \
    R2_ACCOUNT_ID=<your-cloudflare-account-id> \
    R2_ACCESS_KEY_ID=<your-r2-access-key> \
    R2_SECRET_ACCESS_KEY=<your-r2-secret-key> \
    R2_BUCKET_NAME=comicme-pdfs \
    R2_PUBLIC_URL=https://pub-<your-account-id>.r2.dev \
    RAZORPAY_ENABLED=false \
    TEMPLATE_BASE_DIR=templates/base \
    TEMPLATE_MASK_DIR=templates/mask \
    RESEND_API_KEY=<your-resend-api-key> \
    RESEND_FROM_EMAIL="ComicMe <onboarding@resend.dev>" \
    COMIC_EMAIL_ENABLED=true
```

**Important**: Replace every `<placeholder>` with your actual values.

---

## Step 7: Get the API URL

After creation completes (takes 2-5 minutes), get the URL:

```bash
az containerapp show \
  --name comicme-api \
  --resource-group rg-comicme \
  --query properties.configuration.ingress.fqdn \
  --output tsv
```

This outputs something like `comicme-api.azurecontainerapps.io`. Save this URL.

---

## Step 8: Update Frontend API Base URL

If keeping the frontend on Vercel:

1. Go to [Vercel Dashboard](https://vercel.com/dashboard) → your ComicMe project → Settings → Environment Variables
2. Add or update `VITE_API_BASE`:
   - **Production**: `https://comicme-api.azurecontainerapps.io` (or your custom domain)
   - **Preview**: Same URL (ACA URLs are stable per revision)
3. Redeploy from Vercel dashboard

If using Azure Static Web Apps for the frontend instead, set `VITE_API_BASE` in the SWA configuration:

```bash
az staticwebapp environment add \
  --name comicme-frontend \
  --resource-group rg-comicme \
  --property-names VITE_API_BASE=https://comicme-api.azurecontainerapps.io
```

---

## Step 9: (Optional) Custom Domain with SSL

To use a custom domain like `api.comicme.app`:

```bash
# Map the domain to ACA
az containerapp hostname bind \
  --name comicme-api \
  --resource-group rg-comicme \
  --environment comicme-env \
  --hostname api.comicme.app
```

Then point your DNS CNAME record to the ACA default domain. SSL is automatically provisioned via Let's Encrypt.

---

## Step 10: (Optional) Set Up GitHub Actions CI/CD

1. Go to GitHub → your repo → Settings → Secrets and variables → Actions
2. Add these secrets:
   - `AZURE_CLIENT_ID` — Service principal app ID
   - `AZURE_TENANT_ID` — Azure AD tenant ID
   - `AZURE_SUBSCRIPTION_ID` — Your subscription ID
3. Create a service principal:

```bash
az ad sp create-for-rbac \
  --name comicme-deploy \
  --role Contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/rg-comicme \
  --sdk-auth
```

Copy the JSON output and paste it as `AZURE_CREDENTIALS` secret.

4. Add `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` as individual secrets (the workflow reads them separately).

5. Also add ACR push permission:

```bash
az role assignment create \
  --assignee <SERVICE_PRINCIPAL_APP_ID> \
  --scope /subscriptions/<SUB_ID>/resourceGroups/rg-comicme/providers/Microsoft.ContainerRegistry/registries/comicmeacr \
  --role AcrPush
```

6. Enable GitHub Actions in the workflow file (`.github/workflows/deploy.yml`). Push to `main` triggers a build and deploy.

---

## Step 11: Configure Azure Key Vault for Production Secrets (Recommended)

Instead of storing secrets as plain env vars in ACA, use Azure Key Vault:

```bash
# Create Key Vault
az keyvault create --name comicme-kv --resource-group rg-comicme --location eastus2

# Add secrets
az keyvault secret set --vault-name comicme-kv --name GeminiApiKey --value "<your-key>"
az keyvault secret set --vault-name comicme-kv --name DatabaseUrl --value "<your-neon-url>"
az keyvault secret set --vault-name comicme-kv --name ResendApiKey --value "<your-key>"
# ... add all other secrets

# Create managed identity for the container app
az identity create --name comicme-id --resource-group rg-comicme

# Grant Key Vault access
az keyvault set-policy \
  --name comicme-kv \
  --object-id $(az identity show --name comicme-id --resource-group rg-comicme --query principalId -o tsv) \
  --secret-permissions get list
```

Then update your FastAPI code to fetch secrets from Key Vault at runtime using `DefaultAzureCredential` from `azure-identity`. This requires adding `azure-identity` to `requirements.txt`.

---

## Monitoring

```bash
# View logs
az containerapp logs show --name comicme-api --resource-group rg-comicme --follow

# View metrics
az monitor metrics list \
  --resource $(az containerapp show --name comicme-api --resource-group rg-comicme --query id -o tsv) \
  --metric cpuPercentage memoryPercentage \
  --interval PT1M

# Scale manually
az containerapp update \
  --name comicme-api \
  --resource-group rg-comicme \
  --min-replicas 3 \
  --max-replicas 10
```

---

## Cost Reference (East US 2, 2026)

| Resource | Monthly Cost |
|----------|-------------|
| ACA Environment (2 vCPU, 8GB) | ~$50-80 |
| ACA (scale-to-zero) | ~$0 idle, ~$50-80 active |
| ACR (Basic) | ~$5-10 |
| Azure SWA (Free tier) | $0 |
| Key Vault (Standard) | ~$1-3 |
| **Total (CPU only)** | **~$60-100/month** |
| **Total (GPU, T4)** | **~$250-400/month** |

---

## Troubleshooting

### Container fails to start
- Check logs: `az containerapp logs show --name comicme-api --resource-group rg-comicme`
- Common cause: missing system deps in Dockerfile (libgl1-mesa-glx for torchvision/opencv)
- Increase start-period in HEALTHCHECK if model loading is slow

### Database connection fails
- Verify `DATABASE_URL` or `DB_*` env vars match your Neon credentials
- Check Neon allows your Azure IP (or use SSL)

### CORS errors in frontend
- Update `CORS_ORIGINS` env var to include your Vercel/SWA domain
- Redeploy the ACA app

### Out of memory
- Increase `--memory` on the ACA environment and container app
- Consider using `onnxruntime` (CPU) instead of `onnxruntime-gpu` if GPU-less

### Image too large
- Use multi-stage Dockerfile (already included)
- Use CPU-only PyTorch: replace torch/torchvision with CPU wheels

---

## Architecture Notes

| Component | Service | Why |
|-----------|---------|-----|
| Backend API | Azure Container Apps | Full container control, ML deps, auto-scaling |
| Frontend | Vercel (existing) | Already handles TanStack/Nitro builds |
| Database | Neon Postgres (existing) | Serverless, no migration needed |
| File Storage | Cloudflare R2 (existing) | S3-compatible, no migration needed |
| Email | Resend (existing) | Already integrated |
| Secrets | Azure Key Vault (optional) | Better than env vars for production |
```