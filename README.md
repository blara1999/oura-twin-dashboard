# 🏔️ Oura Ring Twin Physiology Dashboard

A Streamlit-based monitoring dashboard for tracking biometric data from identical twins during a high-altitude expedition using Oura Ring Gen 4 devices.

## Features

- **OAuth2 Authorization Code Flow**: Secure authentication for two separate Oura accounts (Twin A and Twin B)
- **Real-time Monitoring**: Near real-time display of critical altitude physiology metrics
- **Comparative Visualization**: Side-by-side comparison charts with Twin A (Blue) and Twin B (Red)
- **Mock Data Mode**: Built-in realistic simulated data for testing without API credentials
- **Doctor's Heads-Up Display**: Big, bold KPI metrics for quick assessment
- **Critical Alerts**: Visual warnings when SpO2 drops below 90%

## Metrics Tracked

| Metric | Endpoint | Clinical Significance |
|--------|----------|----------------------|
| **SpO2 %** | `/v2/usercollection/daily_spo2` | Critical for altitude acclimatization |
| **Resting Heart Rate** | `/v2/usercollection/sleep` | Indicates cardiovascular stress |
| **HRV** | `/v2/usercollection/sleep` | Stress and recovery indicator |
| **Respiratory Rate** | `/v2/usercollection/sleep` | Hypoxic Ventilatory Response proxy |
| **Sleep Score** | `/v2/usercollection/daily_sleep` | Overall sleep quality |
| **Cardiovascular Age** | `/v2/usercollection/daily_cardiovascular_age` | Vascular health (Gen 4 feature) |

## Quick Start

### 1. Installation

```bash
# Clone or download the repository
cd oura_dashboard

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run with Mock Data (No API Required)

```bash
streamlit run app.py
```

The dashboard will open in your browser. The "Use Mock Data" toggle is enabled by default, allowing you to explore the full functionality immediately.

### 3. Configure for Real Data

#### A. Register an Oura API Application

1. Go to [Oura Cloud Developer Portal](https://cloud.ouraring.com/oauth/applications)
2. Click "Create Application"
3. Fill in the application details:
   - **Name**: Twin Physiology Monitor
   - **Redirect URI**: `http://localhost:8501` (or your deployment URL)
   - **Scopes**: Select `email`, `personal`, `daily`, `heartrate`, `spo2Daily`
4. Save your **Client ID** and **Client Secret**

#### B. Configure the Dashboard

1. Disable "Use Mock Data" in the sidebar
2. Expand "API Credentials"
3. Enter your Client ID and Client Secret
4. Click "Connect Twin A" and complete OAuth flow
5. Repeat for "Connect Twin B" with the second Oura account

## OAuth2 Flow

The application implements the standard OAuth2 Authorization Code flow:

```
┌─────────┐                              ┌─────────┐                              ┌─────────┐
│Dashboard│                              │  Oura   │                              │  User   │
└────┬────┘                              └────┬────┘                              └────┬────┘
     │  1. Generate auth URL with state       │                                        │
     │────────────────────────────────────────>                                        │
     │                                        │  2. Redirect to Oura login             │
     │                                        │────────────────────────────────────────>
     │                                        │  3. User grants permission             │
     │                                        │<────────────────────────────────────────
     │  4. Redirect with code + state         │                                        │
     │<────────────────────────────────────────                                        │
     │  5. Exchange code for tokens           │                                        │
     │────────────────────────────────────────>                                        │
     │  6. Return access + refresh tokens     │                                        │
     │<────────────────────────────────────────                                        │
     │  7. Store tokens in session            │                                        │
     │                                        │                                        │
```

## Project Structure

```
oura_dashboard/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Configuration Options

### Date Range
- Default: Last 14 days
- Quick select buttons for 7 or 14 days
- Custom date picker for specific ranges

### Rate Limiting
- Oura API limit: 5000 requests per 5 minutes
- Built-in request counter with visual progress bar
- Automatic rate limit checking before each request

## Mock Data Details

The mock data generator simulates a realistic high-altitude expedition:

| Phase | Days | Altitude Effect |
|-------|------|-----------------|
| Base Camp | 1-3 | Normal values |
| Ascending | 4-7 | Gradual stress increase |
| High Camp | 8-14 | Peak altitude effects |

Twin B is simulated with ~15% greater altitude sensitivity to demonstrate comparative analysis.

## Deployment

### Local Development
```bash
streamlit run app.py
```

### Production Deployment (Streamlit Cloud)

1. Push code to GitHub
2. Connect repository to [Streamlit Cloud](https://streamlit.io/cloud)
3. Set environment variables for `CLIENT_ID` and `CLIENT_SECRET`
4. Update redirect URI in Oura developer portal to match deployment URL

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501"]
```

## API Reference

Based on Oura API V2 (OpenAPI spec version 1.27):

- **Base URL**: `https://api.ouraring.com/v2`
- **Auth URL**: `https://cloud.ouraring.com/oauth/authorize`
- **Token URL**: `https://api.ouraring.com/oauth/token`

### Required Scopes
- `email` - User email for identification
- `personal` - Age, gender (for context)
- `daily` - Daily summaries including sleep scores
- `heartrate` - Heart rate data
- `spo2Daily` - SpO2 measurements

## Troubleshooting

### "401 Unauthorized" Error
- Token may be expired → App will attempt automatic refresh
- If persistent, disconnect and reconnect the affected twin

### "403 Forbidden" Error
- User's Oura subscription may have expired
- Required scopes may not have been granted during OAuth

### "429 Rate Limit Exceeded"
- Wait for the rate limit window to reset (5 minutes)
- Reduce date range to fetch less data

### No Data Showing
- Ensure the user has synced their ring with the Oura app
- Check that the date range includes days with recorded data
- SpO2 data requires the user to have SpO2 monitoring enabled

## Security Notes

- **Never commit** Client ID/Secret to version control
- Use environment variables for production deployments
- Tokens are stored in Streamlit session state (memory only)
- OAuth state parameter prevents CSRF attacks

## License

MIT License - Built for research purposes.

## Acknowledgments

- Built for Dr. Patrycja's High-Altitude Physiology Study
- Oura Ring API Documentation: https://cloud.ouraring.com/docs
- Streamlit Documentation: https://docs.streamlit.io
