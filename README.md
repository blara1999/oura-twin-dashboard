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
- **Token Storage**: OAuth tokens are stored in session state and survive refresh but are not persisted permanently on the server disk for security.
- **Data Privacy**: No data is saved to a database; it is fetched live from Oura API on demand.

## Troubleshooting

### "400 Invalid Request" during connection
- Check that your `redirect_uri` in Oura Portal matches EXACTLY the URL in your Streamlit Secrets.
- Ensure no trailing slashes mismatch (e.g. `...app` vs `...app/`).

### SpO2 Data Missing
- Verify exact scope is `spo2` (old docs might say `spo2Daily` which is incorrect).
- Ensure the user's ring is Gen 3 or Gen 4.
- Data availability usually has a slight delay compared to other daily metrics.

## License
MIT License - Research Use Only.
