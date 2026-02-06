# Hosting Options

This app is hosted on **Google Cloud Run**.

## Current Setup: Google Cloud Run

**URL:** https://oura-twin-dashboard-403260428861.europe-west1.run.app

**Cost:** Pay-per-use with generous free tier. For always-on with no cold starts (min 1 instance), ~$6-10/month.

**Features:**
- Auto-deploys from GitHub on every push
- Scales to zero when not in use (cost savings)
- Enterprise-grade security and scaling

## Environment Variables (Cloud Run)

Set these in the Cloud Run service configuration:

| Variable | Description |
| :--- | :--- |
| `APP_USERNAME` | Dashboard login username |
| `APP_PASSWORD` | Dashboard login password |
| `OURA_CLIENT_ID` | Oura API OAuth client ID |
| `OURA_CLIENT_SECRET` | Oura API OAuth client secret |
| `OURA_REDIRECT_URI` | OAuth redirect URL (your Cloud Run URL) |

## Local Development

For local development, the app will:
1. Skip authentication if `APP_USERNAME`/`APP_PASSWORD` are not set
2. Use a local config file for OAuth credentials (saved via the sidebar)
