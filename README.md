# 🏔️ Oura Twin Physiology Dashboard

A monitoring dashboard for tracking biometric data from identical twins during a high-altitude expedition, integrating data from **Oura Ring Gen 4** and **Polar H10** chest straps.

## Features

- **Secure Authentication**: Password-protected access (username/password)
- **OAuth2 Authorization**: Secure connection for multiple accounts:
  - **Oura Ring**: Daily sleep, readiness, and SpO2 metrics
  - **Polar AccessLink**: High-fidelity workout heart rate and training load
- **Real-time Monitoring**: Near real-time display of critical altitude physiology metrics
- **Comparative Visualization**: Side-by-side comparison charts (Twin A vs Twin B)
- **Doctor's Heads-Up Display**: Big, bold KPI metrics for quick assessment
- **Critical Alerts**: Visual warnings when SpO2 drops below 90%

## Metrics Tracked

| Metric | Source | Endpoint | Clinical Significance |
|--------|--------|----------|----------------------|
| **SpO2 %** | Oura | `/v2/usercollection/daily_spo2` | Critical for altitude acclimatization |
| **Resting Heart Rate** | Oura | `/v2/usercollection/sleep` | Cardiovascular stress adaptation |
| **HRV** | Oura | `/v2/usercollection/sleep` | Autonomic nervous system balance |
| **Respiratory Rate** | Oura | `/v2/usercollection/sleep` | Hypoxic Ventilatory Response (HVR) |
| **Workout HR** | Polar | `/v3/exercises` | Accurate active heart rate (5s intervals) |
| **Training Load** | Polar | `/v3/exercises` | Cardio load (TRIMP) monitoring |

## Quick Start (Local Development)

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/blara1999/oura-twin-dashboard.git
cd oura-twin-dashboard

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the App

```bash
streamlit run app.py
```

## Google Cloud Platform (Cloud Run) Deployment

This app is containerized using Docker and is ready for deployment on **Google Cloud Run**.

### 1. Build and Deploy
```bash
# Build the container image
gcloud builds submit --tag gcr.io/PROJECT_ID/oura-dashboard

# Deploy to Cloud Run
gcloud run deploy oura-dashboard \
  --image gcr.io/PROJECT_ID/oura-dashboard \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### 2. Configure Environment Variables
Cloud Run uses environment variables for configuration. Set these in the Cloud Run console or via CLI:

| Variable | Description |
|----------|-------------|
| `OURA_CLIENT_ID` | Oura OAuth Client ID |
| `OURA_CLIENT_SECRET` | Oura OAuth Client Secret |
| `OURA_REDIRECT_URI` | Your Cloud Run URL (e.g., `https://oura-dashboard-xyz.run.app`) |
| `POLAR_CLIENT_ID` | Polar OAuth Client ID |
| `POLAR_CLIENT_SECRET` | Polar OAuth Client Secret |
| `POLAR_REDIRECT_URI` | Your Cloud Run URL |
| `AUTHORIZED_USER_PASSWORD` | Password for dashboard login |
| `GCS_BUCKET_NAME` | Bucket name for persisting tokens (optional but recommended) |

> **Important:** Ensure your `OURA_REDIRECT_URI` and `POLAR_REDIRECT_URI` match EXACTLY what you registered in the respective developer portals.

## Project Structure

```
oura-twin-dashboard/
├── app.py              # Main dashboard application
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container configuration
├── .dockerignore      # Build exclusion
└── README.md          # Documentation
```

## Security & Privacy
- **Authentication**: Requires login to access any data.
- **Token Storage**: OAuth tokens persist across Cloud Run deployments using **Google Cloud Storage**.
- **Data Privacy**: No data is saved to a database; it is fetched live from APIs on demand.

## Cloud Run Token Persistence (GCS)

To persist OAuth tokens across Cloud Run deployments (so you don't need to reconnect after each deploy or restart), you **MUST** configure a GCS bucket.

### 1. Create a GCS Bucket
```bash
gcloud storage buckets create gs://YOUR_BUCKET_NAME --location=us-central1
```

### 2. Add Environment Variable
Add `GCS_BUCKET_NAME=YOUR_BUCKET_NAME` to your Cloud Run service variables.

> **Note**: Cloud Run's default service account usually has read/write access to GCS buckets in the same project. If not, grant `Storage Object Admin` role to the service account.

## Troubleshooting

### "400 Invalid Request" during connection
- Check that your `redirect_uri` in Oura/Polar Portal matches EXACTLY the URL in your Environment Variables.
- Ensure no trailing slashes mismatch (e.g. `...app` vs `...app/`).

### SpO2 Data Missing
- Verify exact scope is `spo2`.
- Ensure the user's ring is Gen 3 or Gen 4.

## License
MIT License - Research Use Only.
