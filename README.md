# 🏔️ Oura Ring Twin Physiology Dashboard

A Streamlit-based monitoring dashboard for tracking biometric data from identical twins during a high-altitude expedition using Oura Ring Gen 4 devices.

## Features

- **Secure Authentication**: Password-protected access (username/password)
- **OAuth2 Authorization**: Secure connection for two separate Oura accounts (Twin A and Twin B)
- **Real-time Monitoring**: Near real-time display of critical altitude physiology metrics
- **Comparative Visualization**: Side-by-side comparison charts with Twin A (Blue) and Twin B (Red)
- **Doctor's Heads-Up Display**: Big, bold KPI metrics for quick assessment
- **Critical Alerts**: Visual warnings when SpO2 drops below 90%

## Metrics Tracked

| Metric | Endpoint | Clinical Significance |
|--------|----------|----------------------|
| **SpO2 %** | `/v2/usercollection/daily_spo2` | Critical for altitude acclimatization, requires Gen 3/4 ring |
| **Resting Heart Rate** | `/v2/usercollection/sleep` | Indicates cardiovascular stress and adaptation |
| **HRV** | `/v2/usercollection/sleep` | Key indicator of autonomic nervous system balance (stress/recovery) |
| **Respiratory Rate** | `/v2/usercollection/sleep` | Proxy for Hypoxic Ventilatory Response (HVR) |
| **Sleep Score** | `/v2/usercollection/daily_sleep` | Overall recovery and sleep quality |

> **Note on SpO2:** SpO2 data is critical for this high-altitude study. Ensure `spo2` scope is enabled and users have SpO2 tracking enabled in their Oura app.

## Quick Start (Local Development)

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/blara1999/oura-twin-dashboard.git
cd oura-twin-dashboard

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Credentials

Create a `.oura_twin_dashboard_config.json` file in your home directory OR launch the app and enter credentials in the sidebar.

### 3. Run the App

```bash
streamlit run app.py
```

## Streamlit Cloud Deployment (Production)

This app is designed to run securely on Streamlit Cloud using **Secrets** for credentials management.

### 1. Register Oura Application
1. Go to [Oura Cloud Developer Portal](https://cloud.ouraring.com/oauth/applications)
2. Create an App with these settings:
   - **Name**: Twin Physiology Monitor
   - **Redirect URI**: `https://<your-app-url>.streamlit.app` (Exact match required!)
   - **Scopes**: `email` `personal` `daily` `heartrate` `spo2`

### 2. Deploy to Streamlit Cloud
1. Push your code to a GitHub repository (Public or Private)
2. Go to [share.streamlit.io](https://share.streamlit.io) and deploy the app
3. In App Settings -> **Secrets**, paste the following configuration:

```toml
[passwords]
authorized_user = "YourSecurePasswordHere"

[oura]
client_id = "your_oura_client_id"
client_secret = "your_oura_client_secret"
redirect_uri = "https://<your-app-url>.streamlit.app"
```

> **Important:** The `redirect_uri` in Secrets MUST match exactly what is in the Oura Developer Portal.

### 3. Accessing the Dashboard
- **Login**: Use the username (`authorized_user`) and password defined in secrets.
- **Connect**: Click "Connect Twin A" and "Connect Twin B" in the sidebar to authorize Oura access.

## Project Structure

```
oura-twin-dashboard/
├── app.py              # Main dashboard application
├── requirements.txt    # Python dependencies
├── .gitignore         # Version control exclusion
├── .streamlit/
│   └── secrets.toml.example  # Template for secrets
└── README.md          # Documentation
```

## Security & Privacy
- **Authentication**: Requires login to access any data (powered by Streamlit Secrets).
- **Token Storage**: OAuth tokens persist across Cloud Run deployments using Google Cloud Storage (when configured) or local files for development.
- **Data Privacy**: No data is saved to a database; it is fetched live from Oura API on demand.

## Cloud Run Token Persistence (GCS)

To persist OAuth tokens across Cloud Run deployments (so you don't need to reconnect Twin A/B after each deploy):

### 1. Create a GCS Bucket
```bash
gcloud storage buckets create gs://YOUR_BUCKET_NAME --location=us-central1
```

### 2. Add Environment Variable to Cloud Run
Add this environment variable to your Cloud Run service:
```
GCS_BUCKET_NAME=YOUR_BUCKET_NAME
```

> **Note**: Cloud Run's default service account already has read/write access to GCS buckets in the same GCP project. No additional IAM changes needed.

## Troubleshooting

### "400 Invalid Request" during connection
- Check that your `redirect_uri` in Oura Portal matches EXACTLY the URL in your Streamlit Secrets.
- Ensure no trailing slashes mismatch (e.g. `...app` vs `...app/`).

### SpO2 Data Missing
- Verify exact scope is `spo2` (old docs might say `spo2Daily` which is incorrect).
- Ensure the user's ring is Gen 3 or Gen 4.
- Data availability usually has a slight delay compared to other daily metrics.

## Keep-Alive Mechanism

Streamlit Community Cloud puts apps to sleep after 12 hours of inactivity. This repository includes a GitHub Actions workflow (`.github/workflows/keep-alive.yml`) that automatically pings the app every 10 hours to prevent hibernation.

### Setup
Add your Streamlit app URL as a repository secret:
1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Create a secret named `STREAMLIT_APP_URL` with your full app URL

The workflow runs automatically at 00:00, 10:00, and 20:00 UTC. You can also trigger it manually from the Actions tab.

## License
MIT License - Research Use Only.
