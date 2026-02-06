# Alternative Hosting Options

Streamlit Cloud is great for free hosting, but the "sleep" behavior after inactivity is unavoidable on the free tier. 
If the GitHub Action workaround is not reliable enough, here are the best low-cost alternatives that offer consistent uptime.

## Recommendation Summary

| Service | Best For | Approx Cost | Pros | Cons |
| :--- | :--- | :--- | :--- | :--- |
| **Railway** | **Ease of Use** | ~$5/mo | Very easy setup, auto-deploy from GitHub. | No free tier for always-on (trial involves credit). |
| **Render** | **Simplicity** | $7/mo | Simple "Web Service" tier prevents sleep. | Free tier spins down (like Streamlit). |
| **Hugging Face**| **Free Option** | Free | Very generous free tier, specifically for ML/Data apps. | Public spaces are visible to all (unless upgraded). |
| **DigitalOcean**| **Control** | $5/mo | "App Platform" is robust and professional. | Slightly more config than Railway/Render. |

## Detailed Breakdown

### 1. Railway (railway.app)
*Recommended for minimal hassle.*
- **How it works:** Connect your GitHub repo. It detects `requirements.txt` and `app.py` automatically.
- **Cost:** You pay for what you use. For a simple Streamlit app, it's usually around $5/month.
- **Why switch:** It never sleeps if you have a paid plan (even the "Hobby" tier keeps it running).

### 2. Render (render.com)
- **How it works:** Create a "Web Service". Connect GitHub.
- **Cost:** $7/month for the "Starter" instance.
- **Why switch:** The $7 tier offers 24/7 uptime. The *Free* tier on Render also spins down after inactivity (15 mins), so you must upgrade to solve the sleep issue.

### 3. Hugging Face Spaces (huggingface.co/spaces)
- **How it works:** Create a "Space", select "Streamlit" as the SDK. You can push your code there.
- **Cost:** Free for basic hardware (2 vCPU, 16GB RAM).
- **Why switch:** Their free tier is very generous and generally stays active longer, though they do "pause" spaces after 48+ hours of no traffic. Pro upgrade ($9/mo) guarantees persistent hardware.

### 4. DigitalOcean App Platform
- **How it works:** Similar to Heroku/Render to deploy directly from GitHub.
- **Cost:** $5/month for a "Basic" container.
- **Why switch:** Industry standard infrastructure. Very reliable.

### 5. Google Cloud Platform (Cloud Run)
*Best if you already have a GCP account.*
- **How it works:** You build a Docker container (using the `Dockerfile` I just added) and deploy it to Cloud Run.
- **Cost:** Pay-per-use. It has a generous free tier (2 million requests/month), BUT to prevent "sleeping" (cold starts), you need minimum 1 instance active, which costs ~$6-10/month depending on region and cpu settings.
    - *Note*: If you are okay with a few seconds of "cold start" delay when opening the app, it can be **nearly free**.
- **Why switch:** Enterprise-grade scaling and security.

## How to Migrate (General Steps)

### For Render/Railway/DigitalOcean:
1.  **Sign up** for the chosen service.
2.  **Connect GitHub**: Most allow you to authorize your GitHub account and select this repository (`oura-twin-dashboard`).
3.  **Environment Variables**: Copy your secrets (like `oura_personal_access_token`) from Streamlit Cloud dashboard to the new service's "Environment Variables" settings.
4.  **Deploy**: Push a commit or click "Deploy".

### For Google Cloud Run:
1.  **Install SDK**: Make sure you have the `gcloud` CLI installed.
2.  **Deploy**: Run this command in your terminal:
    ```bash
    gcloud run deploy oura-twin-dashboard --source . --region us-central1 --allow-unauthenticated
    ```
    *(Note: You'll need to set environment variables via the Google Cloud Console or add flags like `--set-env-vars KEY=VALUE`)*

