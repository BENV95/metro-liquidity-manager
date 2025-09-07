# Google Cloud Run CLI Deployment Guide for Windows

## Prerequisites

### Install Google Cloud SDK
1. Download the Google Cloud SDK installer for Windows from [cloud.google.com/sdk](https://cloud.google.com/sdk)
2. Run the installer and follow the setup wizard
3. Restart your command prompt or PowerShell

### Authentication and Setup
```bash
# Login to Google Cloud
gcloud auth login

# Set your default project
gcloud config set project YOUR_PROJECT_ID

# Enable Cloud Run API
gcloud services enable run.googleapis.com

# Set default region (optional)
gcloud config set run/region us-central1
```

## Basic Cloud Run Commands

### Deploy a Service
```bash
# Deploy from source code
gcloud run deploy SERVICE_NAME --source .

# Deploy from container image
gcloud run deploy SERVICE_NAME --image gcr.io/PROJECT_ID/IMAGE_NAME

# Deploy with specific settings
gcloud run deploy SERVICE_NAME \
  --image gcr.io/PROJECT_ID/IMAGE_NAME \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --concurrency 100 \
  --max-instances 10
```

### List and Describe Services
```bash
# List all services
gcloud run services list

# Describe a specific service
gcloud run services describe SERVICE_NAME --region=REGION

# Get service URL
gcloud run services describe SERVICE_NAME --region=REGION --format="value(status.url)"
```

### Update Services
```bash
# Update environment variables
gcloud run services update SERVICE_NAME \
  --set-env-vars KEY1=value1,KEY2=value2

# Update memory and CPU
gcloud run services update SERVICE_NAME \
  --memory 1Gi \
  --cpu 2

# Update traffic allocation
gcloud run services update-traffic SERVICE_NAME \
  --to-latest
```

### Delete Services
```bash
# Delete a service
gcloud run services delete SERVICE_NAME --region=REGION
```

## YAML Configuration

### Service YAML Structure
Create a `service.yaml` file with the following structure:

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: my-service
  labels:
    cloud.googleapis.com/location: us-central1
  annotations:
    run.googleapis.com/ingress: all
    run.googleapis.com/execution-environment: gen2
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/maxScale: "10"
        autoscaling.knative.dev/minScale: "0"
        run.googleapis.com/cpu-throttling: "true"
        run.googleapis.com/execution-environment: gen2
    spec:
      containerConcurrency: 100
      timeoutSeconds: 300
      serviceAccountName: my-service-account@project.iam.gserviceaccount.com
      containers:
      - name: my-container
        image: gcr.io/PROJECT_ID/my-image:latest
        ports:
        - containerPort: 8080
          name: http1
        env:
        - name: NODE_ENV
          value: production
        - name: DATABASE_URL
          value: "postgresql://user:pass@host:5432/db"
        resources:
          limits:
            cpu: 1000m
            memory: 512Mi
          requests:
            cpu: 100m
            memory: 128Mi
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Replace Service from YAML
```bash
# Replace/deploy service using YAML file
gcloud run services replace service.yaml --region=REGION

# Replace with custom region
gcloud run services replace service.yaml --region=us-west1
```

## Common Configuration Options

### Environment Variables
```yaml
env:
- name: PORT
  value: "8080"
- name: NODE_ENV
  value: production
- name: SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: my-secret
      key: secret-key
```

### Resource Limits
```yaml
resources:
  limits:
    cpu: "2"          # 2 vCPUs
    memory: "2Gi"     # 2 GiB memory
  requests:
    cpu: "1"          # Minimum 1 vCPU
    memory: "512Mi"   # Minimum 512 MiB
```

### Scaling Configuration
```yaml
metadata:
  annotations:
    autoscaling.knative.dev/maxScale: "100"    # Max instances
    autoscaling.knative.dev/minScale: "1"      # Min instances
    run.googleapis.com/cpu-throttling: "false" # Always allocate CPU
```

### Traffic Management
```yaml
spec:
  traffic:
  - percent: 100
    latestRevision: true
  # Or split traffic between revisions
  # - percent: 80
  #   revisionName: my-service-v1
  # - percent: 20
  #   revisionName: my-service-v2
```

## Advanced Commands

### Revision Management
```bash
# List revisions
gcloud run revisions list --service=SERVICE_NAME

# Describe revision
gcloud run revisions describe REVISION_NAME

# Delete old revisions
gcloud run revisions delete REVISION_NAME
```

### IAM and Security
```bash
# Make service public
gcloud run services add-iam-policy-binding SERVICE_NAME \
  --member="allUsers" \
  --role="roles/run.invoker"

# Restrict to authenticated users
gcloud run services remove-iam-policy-binding SERVICE_NAME \
  --member="allUsers" \
  --role="roles/run.invoker"

# Grant specific user access
gcloud run services add-iam-policy-binding SERVICE_NAME \
  --member="user:email@example.com" \
  --role="roles/run.invoker"
```

### Logs and Monitoring
```bash
# View logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=SERVICE_NAME" --limit=50

# Stream logs in real-time
gcloud logs tail "resource.type=cloud_run_revision AND resource.labels.service_name=SERVICE_NAME"

# Get service metrics
gcloud run services describe SERVICE_NAME --region=REGION --format="table(metadata.name,status.conditions[0].type,status.conditions[0].status)"
```

## Useful Tips

### Environment-Specific Deployments
Create different YAML files for different environments:
- `service-dev.yaml`
- `service-staging.yaml` 
- `service-prod.yaml`

### Using gcloud with PowerShell
When using PowerShell on Windows, you may need to escape certain characters or use quotes:
```powershell
# PowerShell example
gcloud run deploy my-service `
  --image "gcr.io/my-project/my-image" `
  --platform managed `
  --region us-central1
```

### Common Troubleshooting
```bash
# Check service status
gcloud run services describe SERVICE_NAME --region=REGION

# View deployment logs
gcloud logs read "resource.type=cloud_run_revision" --limit=20

# Test service locally (if using buildpacks)
gcloud run services proxy SERVICE_NAME --port=8080
```

### Cleanup Commands
```bash
# Delete all revisions except latest
gcloud run revisions list --service=SERVICE_NAME --format="value(metadata.name)" | tail -n +2 | xargs -I {} gcloud run revisions delete {}

# List and clean up unused images
gcloud container images list-tags gcr.io/PROJECT_ID/IMAGE_NAME --limit=999999 --sort-by=timestamp
```

This guide covers the most commonly used Cloud Run CLI commands and YAML configurations for Windows deployment workflows.