"""
Oura Ring V2 Dashboard for Twin Physiology Study
================================================
A Streamlit dashboard for Dr. Patrycja to monitor biometric data
from identical twins during a high-altitude expedition.

Features:
- OAuth2 Authorization Code flow for two Oura accounts
- Near real-time monitoring of critical altitude physiology metrics
- Comparative visualization between Twin A (Blue) and Twin B (Red)

Author: Senior Full Stack Data Scientist
Date: January 2026
"""

import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, date
from urllib.parse import urlencode, parse_qs
import secrets
import time
from typing import Optional, Dict, Any, Tuple, List
import json
import os
import hashlib
# import extra_streamlit_components as stx  # Replaced with cookies controller
from streamlit_cookies_controller import CookieController
from pathlib import Path

# =============================================================================
# AUTHENTICATION (for Streamlit Cloud deployment)
# =============================================================================

def is_running_on_cloud() -> bool:
    """Check if running on Streamlit Cloud (secrets will be available)."""
    try:
        # st.secrets is available on cloud or if local secrets.toml exists
        return hasattr(st, 'secrets') and 'passwords' in st.secrets
    except Exception:
        return False

def check_password() -> bool:
    """
    Returns True if the user has entered a correct password.
    Shows a login form if not authenticated.
    """
    # Skip authentication if no passwords configured (local development)
    if not is_running_on_cloud():
        return True
    
    # Return True if already authenticated in session
    if st.session_state.get("authenticated", False):
        return True

    # Initialize Cookie Controller
    # key is important for streamlits component state
    cookie_controller = CookieController(key='auth_cookies')
    
    # Check for valid auth cookie
    # streamlit-cookies-controller reads cookies into component state
    cookies = cookie_controller.getAll()
    auth_cookie = cookies.get("dashboard_auth") if cookies else None
    
    if auth_cookie:
        try:
            # Format: username:hash
            username, token_hash = auth_cookie.split(":", 1)
            
            # Verify against secrets
            if username in st.secrets["passwords"]:
                stored_password = st.secrets["passwords"][username]
                # Reconstruct expected hash
                expected_hash = hashlib.sha256(f"{username}{stored_password}".encode()).hexdigest()
                
                if token_hash == expected_hash:
                    st.session_state["authenticated"] = True
                    st.session_state["current_user"] = username
                    return True
        except (ValueError, AttributeError):
            pass # Invalid cookie format
            
    # Show login form using st.form for stable state management
    st.markdown("""
    <style>
    .login-title {
        text-align: center;
        color: #1e293b;
        font-size: 1.8rem;
        margin-bottom: 8px;
    }
    .login-subtitle {
        text-align: center;
        color: #64748b;
        font-size: 0.9rem;
        margin-bottom: 24px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-title">🔬 Twin Physiology Monitor</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-subtitle">High-Altitude Expedition Dashboard</div>', unsafe_allow_html=True)
    
    # Use a form to prevent multiple submission issues
    with st.container():
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        remember_me = st.checkbox("Remember me")
        submitted = st.button("Log in", type="primary", use_container_width=True)
        
        if submitted:
            try:
                # Debug: Show what we're checking
                with st.expander("🔍 Debug Info", expanded=True):
                    st.write(f"Username entered: '{username}'")
                    st.write(f"Password length: {len(password) if password else 0}")
                    st.write(f"Available users: {list(st.secrets.get('passwords', {}).keys())}")
                    if username in st.secrets.get("passwords", {}):
                        stored = st.secrets["passwords"][username]
                        st.write(f"Stored password length: {len(stored)}")
                        st.write(f"Passwords match: {password == stored}")
                    else:
                        st.write(f"Username '{username}' not found in secrets")
                
                if username in st.secrets["passwords"] and password == st.secrets["passwords"][username]:
                    st.session_state["authenticated"] = True
                    st.session_state["current_user"] = username
                    
                    if remember_me:
                        # Create secure token: username:hash(username+password)
                        token_hash = hashlib.sha256(f"{username}{password}".encode()).hexdigest()
                        cookie_value = f"{username}:{token_hash}"
                        # Set cookie for 30 days
                        cookie_controller.set("dashboard_auth", cookie_value)
                        # Note: We might need to manually rerun or wait for cookie set?
                        # Usually controller.set updates frontend.
                    
                    st.rerun()
                else:
                    st.error("😕 Invalid username or password")
            except Exception as e:
                st.error(f"😕 Authentication error: {e}")
    
    return False

# =============================================================================
# CREDENTIAL PERSISTENCE (survives OAuth redirects)
# =============================================================================

CONFIG_FILE = Path.home() / ".oura_twin_dashboard_config.json"

def save_credentials(client_id: str, client_secret: str, redirect_uri: str):
    """Save OAuth credentials to a local config file."""
    config = {
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri
    }
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
    except Exception as e:
        st.warning(f"Could not save credentials: {e}")

def load_credentials() -> Dict[str, str]:
    """Load OAuth credentials from Streamlit secrets (cloud) or local config file."""
    # First, try Streamlit secrets (for cloud deployment)
    try:
        if hasattr(st, 'secrets') and 'oura' in st.secrets:
            return {
                'client_id': st.secrets['oura'].get('client_id', ''),
                'client_secret': st.secrets['oura'].get('client_secret', ''),
                'redirect_uri': st.secrets['oura'].get('redirect_uri', 'http://localhost:8501')
            }
    except Exception:
        pass
    
    # Fallback to local config file
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {'client_id': '', 'client_secret': '', 'redirect_uri': 'http://localhost:8501'}

def clear_credentials():
    """Remove saved credentials."""
    try:
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
    except Exception:
        pass

# =============================================================================
# TOKEN PERSISTENCE (survives OAuth redirects)
# =============================================================================

TOKEN_FILE = Path.home() / ".oura_twin_dashboard_tokens.json"

def save_tokens(tokens: Dict[str, Any]):
    """Save access tokens to a local config file."""
    try:
        # Load existing tokens first to preserve other twin's data
        existing = load_tokens()
        existing.update(tokens)
        
        with open(TOKEN_FILE, 'w') as f:
            json.dump(existing, f)
    except Exception as e:
        st.warning(f"Could not save tokens: {e}")

def remove_twin_tokens(twin: str):
    """Remove tokens for a specific twin."""
    try:
        tokens = load_tokens()
        keys_to_remove = [k for k in tokens.keys() if k.startswith(f"{twin}_")]
        for k in keys_to_remove:
            tokens.pop(k, None)
        
        with open(TOKEN_FILE, 'w') as f:
            json.dump(tokens, f)
    except Exception:
        pass

def load_tokens() -> Dict[str, Any]:
    """Load access tokens from local config file."""
    try:
        if TOKEN_FILE.exists():
            with open(TOKEN_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

# =============================================================================
# CONFIGURATION
# =============================================================================

# Oura API Configuration (from OpenAPI spec)
OURA_AUTH_URL = "https://cloud.ouraring.com/oauth/authorize"
OURA_TOKEN_URL = "https://api.ouraring.com/oauth/token"
OURA_API_BASE = "https://api.ouraring.com/v2"

# OAuth2 Scopes needed for our metrics
# See: https://cloud.ouraring.com/docs/authentication#scopes
# Available: email, personal, daily, heartrate, workout, tag, session, spo2
OURA_SCOPES = "email personal daily heartrate spo2"

# Rate limiting: 5000 requests per 5 minutes
RATE_LIMIT_REQUESTS = 5000
RATE_LIMIT_WINDOW = 300  # seconds

# Color scheme for twins - professional medical colors
TWIN_A_COLOR = "#0369a1"  # Sky blue - professional
TWIN_B_COLOR = "#be123c"  # Rose red - professional

# Page configuration
st.set_page_config(
    page_title="Twin Physiology Monitor",
    page_icon="▲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# CUSTOM CSS - Professional Medical Dashboard Theme
# =============================================================================

st.markdown("""
<style>
    /* Import professional font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Import Material Symbols for icons */
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
    
    /* Force all text to be visible - but EXCLUDE icon elements */
    *:not([data-testid="stIconMaterial"]):not(.exvv1vr0):not([class*="stIcon"]) {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    
    /* Ensure Material Icons font is used for icon elements */
    [data-testid="stIconMaterial"],
    .exvv1vr0,
    [class*="stIcon"] {
        font-family: 'Material Symbols Rounded' !important;
        font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
    }
    
    /* Main content text */
    .main .block-container,
    .main .block-container p,
    .main .block-container span,
    .main .block-container div,
    .main .stMarkdown,
    .main .stMarkdown p,
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] span {
        color: #1e293b !important;
    }
    
    /* Bold/strong text */
    strong, b,
    .main strong, .main b,
    [data-testid="stMarkdownContainer"] strong,
    [data-testid="stMarkdownContainer"] b {
        color: #0f172a !important;
        font-weight: 700 !important;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6,
    .main h1, .main h2, .main h3,
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3 {
        color: #0f172a !important;
        font-weight: 700 !important;
    }
    
    /* Main header styling */
    .main-header {
        font-size: 1.75rem;
        font-weight: 700;
        color: #0f172a !important;
        text-align: center;
        padding: 1rem 0 0.5rem 0;
        border-bottom: 2px solid #0ea5e9;
        margin-bottom: 0.25rem;
        margin-top: 0.5rem;
        letter-spacing: -0.025em;
        background: transparent !important;
    }
    
    /* Subheader */
    .expedition-context {
        text-align: center;
        color: #475569 !important;
        font-size: 0.75rem;
        font-weight: 500;
        margin-bottom: 1rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        background: transparent !important;
    }
    
    /* Sidebar text */
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] .block-container,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] strong,
    section[data-testid="stSidebar"] b {
        color: #1e293b !important;
    }
    
    section[data-testid="stSidebar"] strong,
    section[data-testid="stSidebar"] b {
        font-weight: 700 !important;
    }
    
    /* Sidebar background */
    section[data-testid="stSidebar"] {
        background-color: #f8fafc !important;
    }
    
    /* Captions - slightly lighter but readable */
    .stCaption, 
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p {
        color: #64748b !important;
    }
    
    /* Expander */
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary span {
        color: #1e293b !important;
    }
    
    /* White background */
    .stApp, .main {
        background: #ffffff !important;
    }
    
    /* Warning/Alert box */
    .altitude-warning {
        background-color: #fef3c7 !important;
        border-left: 4px solid #f59e0b !important;
        border-radius: 0 4px 4px 0;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        font-size: 0.875rem;
        color: #92400e !important;
    }
    
    /* Reduce padding */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1rem;
    }
    
    /* Metric card styling */
    .metric-card {
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
        transition: box-shadow 0.2s ease;
    }
    
    .metric-card:hover {
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
    }
    
    /* Section spacing */
    .section-header {
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
    }
</style>
""", unsafe_allow_html=True)

# Dark mode CSS (conditionally injected)
def inject_dark_mode_css():
    """Inject dark mode CSS when dark mode is enabled."""
    if st.session_state.get('dark_mode', False):
        st.markdown("""
<style>
    /* Dark mode overrides */
    .stApp, .main {
        background: #0f172a !important;
    }
    
    section[data-testid="stSidebar"] {
        background-color: #1e293b !important;
    }
    
    /* Text colors for dark mode */
    .main .block-container,
    .main .block-container p,
    .main .block-container span,
    .main .block-container div,
    .main .stMarkdown,
    .main .stMarkdown p,
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] span {
        color: #e2e8f0 !important;
    }
    
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] .block-container,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #e2e8f0 !important;
    }
    
    strong, b,
    .main strong, .main b,
    [data-testid="stMarkdownContainer"] strong,
    [data-testid="stMarkdownContainer"] b,
    section[data-testid="stSidebar"] strong,
    section[data-testid="stSidebar"] b {
        color: #f8fafc !important;
        font-weight: 700 !important;
    }
    
    h1, h2, h3, h4, h5, h6,
    .main h1, .main h2, .main h3,
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3 {
        color: #f8fafc !important;
    }
    
    .main-header {
        color: #f8fafc !important;
        border-bottom-color: #38bdf8 !important;
    }
    
    .expedition-context {
        color: #94a3b8 !important;
    }
    
    /* Metric cards dark mode */
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%) !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3) !important;
    }
    
    .metric-card:hover {
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4) !important;
    }
    
    /* Alert box dark mode */
    .altitude-warning {
        background-color: #451a03 !important;
        border-left-color: #f59e0b !important;
        color: #fcd34d !important;
    }
    
    /* Captions */
    .stCaption, 
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p {
        color: #94a3b8 !important;
    }
    
    /* Expander - comprehensive styling */
    [data-testid="stExpander"],
    [data-testid="stExpander"] details,
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary span,
    [data-testid="stExpander"] summary div,
    [data-testid="stExpander"] summary p,
    .st-emotion-cache-19v026h,
    .st-emotion-cache-11fa8fd,
    .st-emotion-cache-11fa8fd p,
    .e1x5aka43,
    .e1x5aka43 p,
    .e1x5aka44,
    .e1x5aka44 span {
        color: #e2e8f0 !important;
    }
    
    [data-testid="stExpander"] details {
        background-color: #1e293b !important;
        border-color: #334155 !important;
    }
    
    [data-testid="stExpanderDetails"],
    [data-testid="stExpanderDetails"] div,
    [data-testid="stExpanderDetails"] p,
    [data-testid="stExpanderDetails"] li {
        color: #e2e8f0 !important;
    }
    
    /* Tabs styling */
    [data-testid="stTabs"],
    [data-baseweb="tab-list"],
    [data-baseweb="tab"],
    [data-baseweb="tab"] p,
    [data-testid="stTab"],
    [data-testid="stTab"] p,
    .st-emotion-cache-175qzaj,
    .st-emotion-cache-175qzaj p {
        color: #e2e8f0 !important;
    }
    
    [data-baseweb="tab-panel"],
    [data-baseweb="tab-panel"] div {
        background-color: transparent !important;
    }
    
    [data-baseweb="tab-border"] {
        background-color: #334155 !important;
    }
    
    /* Alert/Info boxes in dark mode */
    [data-testid="stAlert"],
    [data-testid="stAlertContainer"],
    .stAlert,
    .stAlertContainer {
        background-color: #1e3a5f !important;
        color: #e2e8f0 !important;
    }
    
    [data-testid="stAlertContentInfo"],
    [data-testid="stAlertContentInfo"] p {
        color: #e2e8f0 !important;
    }
    
    /* Text inputs */
    [data-testid="stTextInput"] input,
    [data-testid="stTextInput"] label,
    .stTextInput input,
    .stTextInput label {
        color: #e2e8f0 !important;
        background-color: #1e293b !important;
        border-color: #475569 !important;
    }
    
    /* Buttons */
    .stButton button {
        color: #e2e8f0 !important;
        border-color: #475569 !important;
    }
    
    /* Date inputs */
    [data-testid="stDateInput"] input,
    [data-testid="stDateInput"] label {
        color: #e2e8f0 !important;
        background-color: #1e293b !important;
    }
    
    /* Dataframe/table */
    [data-testid="stDataFrame"],
    .stDataFrame {
        background-color: #1e293b !important;
    }
    
    /* Toggle/checkbox labels */
    [data-testid="stCheckbox"] label span,
    .stCheckbox label span {
        color: #e2e8f0 !important;
    }
    
    /* Progress bar */
    [data-testid="stProgress"] {
        background-color: #334155 !important;
    }
    
    /* Divider */
    hr {
        border-color: #334155 !important;
    }
    
    /* Link buttons */
    .stLinkButton a {
        color: #38bdf8 !important;
    }
</style>
        """, unsafe_allow_html=True)

# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

def init_session_state():
    """Initialize all session state variables."""
    # Load persisted credentials
    # Load persisted credentials and tokens
    saved_creds = load_credentials()
    token_data = load_tokens()
    
    defaults = {
        # OAuth tokens
        'twin_a_token': token_data.get('twin_a_token'),
        'twin_b_token': token_data.get('twin_b_token'),
        'twin_a_refresh_token': token_data.get('twin_a_refresh_token'),
        'twin_b_refresh_token': token_data.get('twin_b_refresh_token'),
        'twin_a_token_expiry': token_data.get('twin_a_token_expiry'),
        'twin_b_token_expiry': token_data.get('twin_b_token_expiry'),
        
        # Cached data
        'twin_a_data': None,
        'twin_b_data': None,
        'last_fetch_time': None,
        
        # UI state
        'date_range': (date.today() - timedelta(days=14), date.today()),
        
        # Rate limiting
        'request_count': 0,
        'rate_limit_reset': None,
        
        # Client credentials - load from file if available
        'client_id': saved_creds.get('client_id', ''),
        'client_secret': saved_creds.get('client_secret', ''),
        'redirect_uri': saved_creds.get('redirect_uri', 'http://localhost:8501'),
        
        # Flag to track if credentials were just saved
        'credentials_saved': False,
        
        # Dark mode
        'dark_mode': False
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# =============================================================================
# OAUTH2 AUTHENTICATION
# =============================================================================

def generate_oauth_state(twin: str) -> str:
    """
    Generate a deterministic state for OAuth2 that encodes the twin identifier.
    This survives Streamlit's session reset on redirect.
    
    Args:
        twin: 'twin_a' or 'twin_b'
    
    Returns:
        State string encoding the twin identifier
    """
    # Load credentials from file (persists across redirects)
    saved_creds = load_credentials()
    client_id = saved_creds.get('client_id', '')
    
    import hashlib
    secret_component = hashlib.sha256(
        f"{client_id}_{twin}_oura_twin_study".encode()
    ).hexdigest()[:16]
    return f"{twin}_{secret_component}"

def parse_oauth_state(state: str) -> Optional[str]:
    """
    Parse and validate the OAuth state parameter.
    
    Args:
        state: The state string from OAuth callback
    
    Returns:
        The twin identifier ('twin_a' or 'twin_b') or None if invalid
    """
    if not state:
        return None
    
    # Extract twin identifier from state
    if state.startswith('twin_a_'):
        twin = 'twin_a'
    elif state.startswith('twin_b_'):
        twin = 'twin_b'
    else:
        return None
    
    # Validate the state matches what we would generate
    expected_state = generate_oauth_state(twin)
    if state == expected_state:
        return twin
    
    return None

def get_authorization_url(twin: str) -> str:
    """
    Generate the OAuth2 authorization URL for a specific twin.
    
    Args:
        twin: 'twin_a' or 'twin_b'
    
    Returns:
        Authorization URL string
    """
    # Load credentials from file
    saved_creds = load_credentials()
    
    state = generate_oauth_state(twin)
    
    params = {
        'response_type': 'code',
        'client_id': saved_creds.get('client_id', ''),
        'redirect_uri': saved_creds.get('redirect_uri', 'http://localhost:8501'),
        'scope': OURA_SCOPES,
        'state': state,
        'prompt': 'login'  # Force fresh login - important for connecting different accounts
    }
    
    return f"{OURA_AUTH_URL}?{urlencode(params)}"

def exchange_code_for_token(code: str) -> Optional[Dict[str, Any]]:
    """
    Exchange an authorization code for access and refresh tokens.
    
    Args:
        code: The authorization code from OAuth callback
    
    Returns:
        Token response dict or None if failed
    """
    # Load credentials from file (persists across redirects)
    saved_creds = load_credentials()
    
    try:
        response = requests.post(
            OURA_TOKEN_URL,
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': saved_creds.get('client_id', ''),
                'client_secret': saved_creds.get('client_secret', ''),
                'redirect_uri': saved_creds.get('redirect_uri', 'http://localhost:8501')
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 400:
            # Code might have been used already or is invalid
            # This happens on browser reload after auth
            st.warning("Auth code expired or already used.")
            return None
        else:
            st.error(f"Token exchange failed: {response.status_code} - {response.text}")
            return None
            
    except requests.RequestException as e:
        st.error(f"Token exchange error: {str(e)}")
        return None

def refresh_access_token(twin: str) -> bool:
    """
    Refresh an expired access token.
    
    Args:
        twin: 'twin_a' or 'twin_b'
    
    Returns:
        True if refresh successful, False otherwise
    """
    refresh_token = st.session_state.get(f'{twin}_refresh_token')
    if not refresh_token:
        return False
    
    # Load credentials from file
    saved_creds = load_credentials()
    
    try:
        response = requests.post(
            OURA_TOKEN_URL,
            data={
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': saved_creds.get('client_id', ''),
                'client_secret': saved_creds.get('client_secret', '')
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30
        )
        
        if response.status_code == 200:
            token_data = response.json()
            st.session_state[f'{twin}_token'] = token_data.get('access_token')
            st.session_state[f'{twin}_refresh_token'] = token_data.get('refresh_token')
            expires_in = token_data.get('expires_in', 86400)
            st.session_state[f'{twin}_token_expiry'] = datetime.now() + timedelta(seconds=expires_in)
            # Save updated tokens
            save_tokens({
                f'{twin}_token': token_data.get('access_token'),
                f'{twin}_refresh_token': token_data.get('refresh_token'),
                f'{twin}_token_expiry': (datetime.now() + timedelta(seconds=expires_in)).isoformat()
            })
            return True
        return False
        
    except requests.RequestException:
        return False

def handle_oauth_callback():
    """Handle OAuth2 callback from URL query parameters."""
    query_params = st.query_params
    
    if 'code' in query_params and 'state' in query_params:
        code = query_params['code']
        state = query_params['state']
        
        # Debug info
        saved_creds = load_credentials()
        
        if not saved_creds.get('client_id'):
            st.error("❌ No saved credentials found. Please save your credentials first.")
            st.query_params.clear()
            return
        
        # Parse and validate state to get twin identifier
        twin = parse_oauth_state(state)
        
        if twin:
            # Exchange code for token
            with st.spinner(f"Connecting {twin.replace('_', ' ').title()}..."):
                token_data = exchange_code_for_token(code)
            
            if token_data:
                st.session_state[f'{twin}_token'] = token_data.get('access_token')
                st.session_state[f'{twin}_refresh_token'] = token_data.get('refresh_token')
                expires_in = token_data.get('expires_in', 86400)
                st.session_state[f'{twin}_token_expiry'] = datetime.now() + timedelta(seconds=expires_in)
                # Save tokens to file for persistence
                save_tokens({
                    f'{twin}_token': token_data.get('access_token'),
                    f'{twin}_refresh_token': token_data.get('refresh_token'),
                    f'{twin}_token_expiry': (datetime.now() + timedelta(seconds=expires_in)).isoformat()
                })
                
                st.success(f"✅ Successfully connected {twin.replace('_', ' ').title()}!")
                # Disable mock data since we now have a real connection
                st.session_state.use_mock_data = False
            
            # Clear URL parameters
            st.query_params.clear()
            st.rerun()
        else:
            st.error(f"❌ OAuth state validation failed. Please try again.")
            st.info("Make sure you saved your credentials before clicking Connect.")
            st.query_params.clear()
    
    elif 'error' in query_params:
        error = query_params.get('error', 'Unknown error')
        error_desc = query_params.get('error_description', '')
        st.error(f"❌ OAuth Error: {error}")
        if error_desc:
            st.error(f"Details: {error_desc}")
        st.query_params.clear()

def is_token_valid(twin: str) -> bool:
    """Check if a twin's token is valid and not expired."""
    token = st.session_state.get(f'{twin}_token')
    expiry = st.session_state.get(f'{twin}_token_expiry')
    
    if not token:
        return False
    
    if expiry:
        # Handle string expiry (from JSON persistence)
        if isinstance(expiry, str):
            try:
                expiry = datetime.fromisoformat(expiry)
            except ValueError:
                return True  # If parsing fails, assume valid
        
        if datetime.now() > expiry:
            # Try to refresh the token
            return refresh_access_token(twin)
    
    return True

# =============================================================================
# API DATA FETCHING
# =============================================================================

def check_rate_limit() -> bool:
    """
    Check if we're within rate limits.
    
    Returns:
        True if request can proceed, False if rate limited
    """
    now = datetime.now()
    
    # Reset counter if window has passed
    if st.session_state.rate_limit_reset is None or now > st.session_state.rate_limit_reset:
        st.session_state.request_count = 0
        st.session_state.rate_limit_reset = now + timedelta(seconds=RATE_LIMIT_WINDOW)
    
    if st.session_state.request_count >= RATE_LIMIT_REQUESTS:
        return False
    
    st.session_state.request_count += 1
    return True

def fetch_oura_data(
    endpoint: str,
    token: str,
    start_date: date,
    end_date: date
) -> Optional[Dict[str, Any]]:
    """
    Fetch data from the Oura API V2.
    
    Args:
        endpoint: API endpoint path (e.g., '/usercollection/daily_spo2')
        token: OAuth2 access token
        start_date: Start date for data range
        end_date: End date for data range
    
    Returns:
        API response data or None if failed
    """
    if not token:
        return None
    
    if not check_rate_limit():
        st.warning("Rate limit reached. Please wait before making more requests.")
        return None
    
    url = f"{OURA_API_BASE}{endpoint}"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    params = {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat()
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            # Don't show error here - will be shown once in the main area
            return None
        elif response.status_code == 403:
            # Silently fail - user may not have this data type enabled
            return None
        elif response.status_code == 429:
            st.error("⚡ Rate limit exceeded by API")
            return None
        else:
            # Silently fail for other errors
            return None
            
    except requests.RequestException as e:
        return None

def fetch_all_twin_data(twin: str, start_date: date, end_date: date) -> Dict[str, Any]:
    """
    Fetch all required data for a twin from multiple endpoints.
    
    Args:
        twin: 'twin_a' or 'twin_b'
        start_date: Start date for data range
        end_date: End date for data range
    
    Returns:
        Dictionary containing all fetched data
    """
    token = st.session_state.get(f'{twin}_token')
    if not token:
        return {}
    
    data = {
        'daily_spo2': None,
        'sleep': None,
        'daily_sleep': None,
        'cardiovascular_age': None,
        'daily_readiness': None
    }
    
    # Fetch SpO2 data
    spo2_response = fetch_oura_data('/usercollection/daily_spo2', token, start_date, end_date)
    if spo2_response:
        data['daily_spo2'] = spo2_response.get('data', [])
    
    # Fetch detailed sleep data (contains RHR, HRV, respiratory rate)
    sleep_response = fetch_oura_data('/usercollection/sleep', token, start_date, end_date)
    if sleep_response:
        data['sleep'] = sleep_response.get('data', [])
    
    # Fetch daily sleep scores
    daily_sleep_response = fetch_oura_data('/usercollection/daily_sleep', token, start_date, end_date)
    if daily_sleep_response:
        data['daily_sleep'] = daily_sleep_response.get('data', [])
    
    # Fetch cardiovascular age
    cv_response = fetch_oura_data('/usercollection/daily_cardiovascular_age', token, start_date, end_date)
    if cv_response:
        data['cardiovascular_age'] = cv_response.get('data', [])

    # Fetch daily readiness (for skin temperature)
    readiness_response = fetch_oura_data('/usercollection/daily_readiness', token, start_date, end_date)
    if readiness_response:
        data['daily_readiness'] = readiness_response.get('data', [])
    
    return data

# =============================================================================
# MOCK DATA GENERATION
# =============================================================================
# Mock data generation removed - now using real API data only

# =============================================================================
# INTRADAY HEART RATE DATA (for Exercise Session Comparison)
# =============================================================================

def fetch_intraday_heartrate(
    token: str,
    hours: int = 4
) -> List[Dict[str, Any]]:
    """
    Fetch intraday heart rate data for the last N hours.
    
    Args:
        token: OAuth2 access token
        hours: Number of hours to fetch (default 4)
    
    Returns:
        List of heart rate readings with timestamp and bpm
    """
    if not token:
        return []
    
    if not check_rate_limit():
        return []
    
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    
    url = f"{OURA_API_BASE}/usercollection/heartrate"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    params = {
        'start_datetime': start_time.isoformat(),
        'end_datetime': end_time.isoformat()
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', [])
        else:
            return []
            
    except requests.RequestException:
        return []

def get_intraday_data_for_twin(twin: str, hours: int = 4) -> List[Dict[str, Any]]:
    """
    Get intraday heart rate data for a twin from the Oura API.
    
    Args:
        twin: 'twin_a' or 'twin_b'
        hours: Number of hours of data
    
    Returns:
        List of heart rate readings
    """
    token = st.session_state.get(f'{twin}_token')
    if not token:
        return []
    
    return fetch_intraday_heartrate(token, hours)

def create_intraday_comparison_chart(
    data_a: List[Dict[str, Any]],
    data_b: List[Dict[str, Any]],
    dark_mode: bool = False
) -> go.Figure:
    """
    Create a comparative intraday heart rate chart for exercise session comparison.
    
    Args:
        data_a: Twin A heart rate data
        data_b: Twin B heart rate data
        dark_mode: Whether to use dark mode styling
    
    Returns:
        Plotly Figure object
    """
    fig = go.Figure()
    
    has_data = False
    
    def parse_timestamp_to_local(ts_str: str) -> pd.Timestamp:
        """Parse ISO 8601 timestamp and convert to Dubai timezone (UTC+4)."""
        # Parse with timezone info
        ts = pd.to_datetime(ts_str)
        # If timezone-aware, convert to Dubai time
        if ts.tzinfo is not None:
            # Fixed offset for Dubai (UTC+4)
            ts = ts.tz_convert('Etc/GMT-4')  # Note: Etc/GMT-4 is actually GMT+4
            ts = ts.tz_localize(None) # Remove tz info for plotting
        return ts
    
    # Process Twin A data
    if data_a:
        has_data = True
        timestamps_a = [parse_timestamp_to_local(d['timestamp']) for d in data_a]
        bpm_a = [d['bpm'] for d in data_a]
        
        fig.add_trace(go.Scatter(
            x=timestamps_a,
            y=bpm_a,
            name='Twin A (IHT)',
            line=dict(color=TWIN_A_COLOR, width=2),
            mode='lines+markers',
            marker=dict(size=4),
            hovertemplate='<b>Twin A</b><br>Time: %{x|%H:%M}<br>HR: %{y} bpm<extra></extra>'
        ))
    
    # Process Twin B data
    if data_b:
        has_data = True
        timestamps_b = [parse_timestamp_to_local(d['timestamp']) for d in data_b]
        bpm_b = [d['bpm'] for d in data_b]
        
        fig.add_trace(go.Scatter(
            x=timestamps_b,
            y=bpm_b,
            name='Twin B (Regular)',
            line=dict(color=TWIN_B_COLOR, width=2),
            mode='lines+markers',
            marker=dict(size=4),
            hovertemplate='<b>Twin B</b><br>Time: %{x|%H:%M}<br>HR: %{y} bpm<extra></extra>'
        ))
    
    # Styling
    bg_color = '#1e293b' if dark_mode else '#ffffff'
    text_color = '#e2e8f0' if dark_mode else '#1e293b'
    grid_color = '#334155' if dark_mode else '#e2e8f0'
    
    # Define fixed X-axis range (5am - 9pm) for the current view
    # Note: Timestamps in data are converted to Dubai time but stripped of tzinfo
    # So we use naive datetimes for the range
    current_date = datetime.now().date()
    start_range = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=5)
    end_range = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=21)
    
    fig.update_layout(
        title=None,
        height=280,
        margin=dict(l=40, r=20, t=20, b=40),
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color=text_color, family='Inter, sans-serif', size=11),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='left',
            x=0,
            bgcolor='rgba(0,0,0,0)'
        ),
        xaxis=dict(
            showgrid=False,
            gridcolor=grid_color,
            gridwidth=1,
            tickformat='%H:%M',
            title='Time',
            range=[start_range, end_range]
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=grid_color,
            gridwidth=1,
            title='Heart Rate (bpm)'
        ),
        hovermode='x unified'
    )
    
    if not has_data:
        fig.add_annotation(
            text="No intraday heart rate data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14, color=text_color)
        )
    
    return fig

# =============================================================================
# DATA PROCESSING
# =============================================================================

def process_twin_data(raw_data: Dict[str, Any]) -> pd.DataFrame:
    """
    Process raw API data into a unified DataFrame for visualization.
    
    Args:
        raw_data: Dictionary containing data from multiple endpoints
    
    Returns:
        Processed DataFrame with all metrics
    """
    if not raw_data:
        return pd.DataFrame()
    
    # Create base DataFrame from dates
    all_dates = set()
    
    # Collect all unique dates
    # Collect all unique dates
    for key in ['daily_spo2', 'sleep', 'daily_sleep', 'cardiovascular_age', 'daily_readiness']:
        if raw_data.get(key):
            for record in raw_data[key]:
                all_dates.add(record.get('day'))
    
    if not all_dates:
        return pd.DataFrame()
    
    df = pd.DataFrame({'day': sorted(list(all_dates))})
    df['day'] = pd.to_datetime(df['day'])
    
    # Process SpO2 data
    if raw_data.get('daily_spo2') and len(raw_data['daily_spo2']) > 0:
        spo2_df = pd.DataFrame(raw_data['daily_spo2'])
        spo2_df['day'] = pd.to_datetime(spo2_df['day'])
        
        # Debug: Print first record to see actual structure
        if len(raw_data['daily_spo2']) > 0:
            first_record = raw_data['daily_spo2'][0]
            print(f"[DEBUG] SpO2 first record keys: {first_record.keys()}")
            print(f"[DEBUG] SpO2 first record: {first_record}")
        
        # Extract average SpO2 from nested structure
        def extract_spo2(row):
            # Try multiple field names that Oura API might use
            # 1. spo2_percentage.average (documented structure)
            if 'spo2_percentage' in row.index:
                val = row['spo2_percentage']
                if isinstance(val, dict) and 'average' in val:
                    return val.get('average')
                if isinstance(val, (int, float)):
                    return val
            
            # 2. average_blood_oxygen (alternate field name)
            if 'average_blood_oxygen' in row.index:
                return row['average_blood_oxygen']
            
            # 3. breathing_disturbance_index might exist but we need SpO2
            # Check for any field containing 'oxygen' or 'spo2'
            for col in row.index:
                if 'oxygen' in col.lower() or 'spo2' in col.lower():
                    val = row[col]
                    if isinstance(val, dict):
                        return val.get('average', val.get('value'))
                    if isinstance(val, (int, float)):
                        return val
            
            return None
        
        spo2_df['spo2'] = spo2_df.apply(extract_spo2, axis=1)
        df = df.merge(spo2_df[['day', 'spo2']], on='day', how='left')
    else:
        df['spo2'] = None
        print("[DEBUG] No SpO2 data returned from API")
    
    # Process sleep data (for RHR, HRV, respiratory rate, and potentially SpO2)
    if raw_data.get('sleep'):
        sleep_df = pd.DataFrame(raw_data['sleep'])
        sleep_df['day'] = pd.to_datetime(sleep_df['day'])
        
        # Debug: show all available columns in sleep data
        print(f"[DEBUG] Sleep data columns: {list(sleep_df.columns)}")
        
        # Check if SpO2 is in sleep data (fallback if daily_spo2 endpoint failed)
        spo2_columns = [c for c in sleep_df.columns if 'spo2' in c.lower() or 'oxygen' in c.lower()]
        if spo2_columns and ('spo2' not in df.columns or df['spo2'].isna().all()):
            print(f"[DEBUG] Found SpO2-like columns in sleep data: {spo2_columns}")
            # Try to extract SpO2 from sleep data
            for col in spo2_columns:
                if col in sleep_df.columns:
                    sleep_df['spo2_from_sleep'] = sleep_df[col].apply(
                        lambda x: x.get('average') if isinstance(x, dict) else x
                    )
                    sleep_agg_spo2 = sleep_df.groupby('day')['spo2_from_sleep'].first().reset_index()
                    df = df.merge(sleep_agg_spo2.rename(columns={'spo2_from_sleep': 'spo2'}), on='day', how='left')
                    break
        
        # Aggregate by day (take the primary sleep period)
        agg_cols = {}
        if 'lowest_heart_rate' in sleep_df.columns:
            agg_cols['lowest_heart_rate'] = 'first'
        if 'average_hrv' in sleep_df.columns:
            agg_cols['average_hrv'] = 'first'
        if 'average_breath' in sleep_df.columns:
            agg_cols['average_breath'] = 'first'
        
        if agg_cols:
            sleep_agg = sleep_df.groupby('day').agg(agg_cols).reset_index()
            
            # Convert breath from breaths/second to breaths/minute if needed
            if 'average_breath' in sleep_agg.columns and sleep_agg['average_breath'].max() < 1:
                sleep_agg['average_breath'] = sleep_agg['average_breath'] * 60
            
            df = df.merge(sleep_agg, on='day', how='left')
    else:
        df['lowest_heart_rate'] = None
        df['average_hrv'] = None
        df['average_breath'] = None
    
    # Process daily sleep scores
    if raw_data.get('daily_sleep'):
        daily_sleep_df = pd.DataFrame(raw_data['daily_sleep'])
        daily_sleep_df['day'] = pd.to_datetime(daily_sleep_df['day'])
        df = df.merge(
            daily_sleep_df[['day', 'score']].rename(columns={'score': 'sleep_score'}),
            on='day',
            how='left'
        )
    else:
        df['sleep_score'] = None
    
    # Process cardiovascular age
    if raw_data.get('cardiovascular_age'):
        cv_df = pd.DataFrame(raw_data['cardiovascular_age'])
        cv_df['day'] = pd.to_datetime(cv_df['day'])
        df = df.merge(
            cv_df[['day', 'vascular_age']].rename(columns={'vascular_age': 'cardiovascular_age'}),
            on='day',
            how='left'
        )
    else:
        df['cardiovascular_age'] = None

    # Process daily readiness (Skin Temperature)
    if raw_data.get('daily_readiness'):
        readiness_df = pd.DataFrame(raw_data['daily_readiness'])
        readiness_df['day'] = pd.to_datetime(readiness_df['day'])
        df = df.merge(
            readiness_df[['day', 'temperature_deviation']],
            on='day',
            how='left'
        )
    else:
        df['temperature_deviation'] = None
    
    return df.sort_values('day')

def get_latest_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Extract the most recent metrics from the DataFrame.
    
    Args:
        df: Processed DataFrame
    
    Returns:
        Dictionary of latest metric values
    """
    if df.empty:
        return {
            'spo2': None,
            'rhr': None,
            'hrv': None,
            'respiratory_rate': None,
            'sleep_score': None,
            'last_sync': None
        }
    
    latest = df.iloc[-1]
    
    def safe_get(value):
        """Return None if value is NaN or doesn't exist."""
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        return value
    
    return {
        'spo2': safe_get(latest.get('spo2')),
        'rhr': safe_get(latest.get('lowest_heart_rate')),
        'hrv': safe_get(latest.get('average_hrv')),
        'respiratory_rate': safe_get(latest.get('average_breath')),
        'sleep_score': safe_get(latest.get('sleep_score')),
        'skin_temp': safe_get(latest.get('temperature_deviation')),
        'last_sync': safe_get(latest.get('day'))
    }

# =============================================================================
# VISUALIZATION FUNCTIONS
# =============================================================================

def create_comparative_line_chart(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    y_column: str,
    title: str,
    y_axis_title: str,
    show_reference_line: Optional[Tuple[float, str]] = None,
    dark_mode: bool = False
) -> go.Figure:
    """
    Create a comparative line chart for Twin A and Twin B.
    
    Args:
        df_a: Twin A DataFrame
        df_b: Twin B DataFrame
        y_column: Column name for y-axis values
        title: Chart title
        y_axis_title: Y-axis label
        show_reference_line: Optional tuple of (value, label) for reference line
    
    Returns:
        Plotly Figure object
    """
    fig = go.Figure()
    
    has_data = False
    
    # Twin A trace
    if not df_a.empty and y_column in df_a.columns:
        # Filter out None/NaN values
        df_a_clean = df_a.dropna(subset=[y_column])
        if not df_a_clean.empty:
            has_data = True
            fig.add_trace(go.Scatter(
                x=df_a_clean['day'],
                y=df_a_clean[y_column],
                name='Twin A',
                line=dict(color=TWIN_A_COLOR, width=3, shape='spline'),
                mode='lines+markers',
                marker=dict(size=8, symbol='circle'),
                hovertemplate='<b>Twin A</b><br>Date: %{x|%Y-%m-%d}<br>Value: %{y:.1f}<extra></extra>'
            ))
    
    # Twin B trace
    if not df_b.empty and y_column in df_b.columns:
        df_b_clean = df_b.dropna(subset=[y_column])
        if not df_b_clean.empty:
            has_data = True
            fig.add_trace(go.Scatter(
                x=df_b_clean['day'],
                y=df_b_clean[y_column],
                name='Twin B',
                line=dict(color=TWIN_B_COLOR, width=3, shape='spline'),
                mode='lines+markers',
                marker=dict(size=8, symbol='diamond'),
                hovertemplate='<b>Twin B</b><br>Date: %{x|%Y-%m-%d}<br>Value: %{y:.1f}<extra></extra>'
            ))
    
    # Add "No Data" annotation if no data exists
    if not has_data:
        fig.add_annotation(
            text="No data available for selected date range",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray")
        )
    
    # Add reference line if specified and there's data
    if show_reference_line and has_data:
        ref_value, ref_label = show_reference_line
        fig.add_hline(
            y=ref_value,
            line_dash="dash",
            line_color="orange",
            annotation_text=ref_label,
            annotation_position="right"
        )
    
    # Colors based on theme
    if dark_mode:
        bg_color = '#1e293b'
        paper_color = '#0f172a'  # Specific match for dark theme background
        text_color = '#f8fafc'
        grid_color = '#334155'
    else:
        bg_color = '#fafafa'
        paper_color = 'white'
        text_color = '#0f172a'
        grid_color = '#e2e8f0'

    # Layout - compact professional style with theme awareness
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color=text_color, family='Inter')),
        xaxis_title='Date',
        yaxis_title=y_axis_title,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.3,  # Pushed further down to avoid overlap
            xanchor="center",
            x=0.5,
            font=dict(size=10, color=text_color),
            bgcolor='rgba(0,0,0,0)'  # Transparent legend background
        ),
        hovermode='x unified',
        plot_bgcolor=bg_color,
        paper_bgcolor=paper_color,
        margin=dict(l=50, r=30, t=50, b=80),  # Increased bottom margin for legend
        height=320,  # Increased height for better legibility
        font=dict(color=text_color),
        xaxis=dict(
            showgrid=True,
            gridcolor=grid_color,
            tickformat='%b %d',
            tickfont=dict(size=10, color=text_color)
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=grid_color,
            tickfont=dict(size=10, color=text_color)
        )
    )
    
    return fig

def create_dual_axis_chart(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    y1_column: str,
    y2_column: str,
    title: str,
    y1_title: str,
    y2_title: str,
    dark_mode: bool = False
) -> go.Figure:
    """
    Create a chart with two y-axes for comparing related metrics.
    
    Args:
        df_a: Twin A DataFrame
        df_b: Twin B DataFrame
        y1_column: Primary y-axis column
        y2_column: Secondary y-axis column
        title: Chart title
        y1_title: Primary y-axis label
        y2_title: Secondary y-axis label
    
    Returns:
        Plotly Figure object
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    has_data = False
    
    # Primary metric - Twin A
    if not df_a.empty and y1_column in df_a.columns:
        df_a_clean = df_a.dropna(subset=[y1_column])
        if not df_a_clean.empty:
            has_data = True
            fig.add_trace(
                go.Scatter(
                    x=df_a_clean['day'],
                    y=df_a_clean[y1_column],
                    name=f'Twin A - {y1_title}',
                    line=dict(color=TWIN_A_COLOR, width=3, shape='spline'),
                    mode='lines+markers'
                ),
                secondary_y=False
            )
    
    # Primary metric - Twin B
    if not df_b.empty and y1_column in df_b.columns:
        df_b_clean = df_b.dropna(subset=[y1_column])
        if not df_b_clean.empty:
            has_data = True
            fig.add_trace(
                go.Scatter(
                    x=df_b_clean['day'],
                    y=df_b_clean[y1_column],
                    name=f'Twin B - {y1_title}',
                    line=dict(color=TWIN_B_COLOR, width=3, shape='spline'),
                    mode='lines+markers'
                ),
                secondary_y=False
            )
    
    # Secondary metric - Twin A
    if not df_a.empty and y2_column in df_a.columns:
        df_a_clean2 = df_a.dropna(subset=[y2_column])
        if not df_a_clean2.empty:
            has_data = True
            fig.add_trace(
                go.Scatter(
                    x=df_a_clean2['day'],
                    y=df_a_clean2[y2_column],
                    name=f'Twin A - {y2_title}',
                    line=dict(color=TWIN_A_COLOR, width=2, dash='dot', shape='spline'),
                    mode='lines+markers',
                    marker=dict(symbol='square', size=6)
                ),
                secondary_y=True
            )
    
    # Secondary metric - Twin B
    if not df_b.empty and y2_column in df_b.columns:
        df_b_clean2 = df_b.dropna(subset=[y2_column])
        if not df_b_clean2.empty:
            has_data = True
            fig.add_trace(
                go.Scatter(
                    x=df_b_clean2['day'],
                    y=df_b_clean2[y2_column],
                    name=f'Twin B - {y2_title}',
                    line=dict(color=TWIN_B_COLOR, width=2, dash='dot', shape='spline'),
                    mode='lines+markers',
                    marker=dict(symbol='square', size=6)
                ),
                secondary_y=True
            )
    
    # Add "No Data" annotation if no data exists
    if not has_data:
        fig.add_annotation(
            text="No data available for selected date range",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray")
        )
            # Colors based on theme
    if dark_mode:
        bg_color = '#1e293b'
        paper_color = '#0f172a'
        text_color = '#f8fafc'
        grid_color = '#334155'
    else:
        bg_color = '#fafafa'
        paper_color = 'white'
        text_color = '#0f172a'
        grid_color = '#e2e8f0'

    # Layout updates
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color=text_color, family='Inter')),
        xaxis_title='Date',
        yaxis=dict(
            title=y1_title,
            showgrid=True,
            gridcolor=grid_color,
            tickfont=dict(color=text_color)
        ),
        yaxis2=dict(
            title=y2_title,
            showgrid=False,
            overlaying='y',
            side='right',
            tickfont=dict(color=text_color)
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.3,
            xanchor="center",
            x=0.5,
            font=dict(size=10, color=text_color),
            bgcolor='rgba(0,0,0,0)'
        ),
        hovermode='x unified',
        plot_bgcolor=bg_color,
        paper_bgcolor=paper_color,
        margin=dict(l=50, r=50, t=50, b=80),
        height=320,
        font=dict(color=text_color),
        xaxis=dict(
            gridcolor=grid_color,
            tickfont=dict(color=text_color),
            tickformat='%b %d'
        )
    )
    
    return fig

def render_kpi_metric(label: str, value_a: Any, value_b: Any, unit: str = "", 
                      warning_threshold: Optional[float] = None,
                      warning_direction: str = "below") -> None:
    """
    Render a KPI metric card comparing both twins (stacked vertically).
    """
    def format_value(val):
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return "—"
        if isinstance(val, float):
            return f"{val:.1f}{unit}"
        return f"{val}{unit}"
    
    def check_warning(val):
        if val is None or warning_threshold is None:
            return False
        try:
            if np.isnan(val):
                return False
        except (TypeError, ValueError):
            pass
        if warning_direction == "below":
            return val < warning_threshold
        return val > warning_threshold
    
    is_warning_a = check_warning(value_a)
    is_warning_b = check_warning(value_b)
    
    # Determine colors
    color_a = "#dc2626" if (value_a is None or is_warning_a) else TWIN_A_COLOR
    color_b = "#dc2626" if (value_b is None or is_warning_b) else TWIN_B_COLOR
    
    border_a = "border-left: 3px solid " + TWIN_A_COLOR + ";"
    border_b = "border-left: 3px solid " + TWIN_B_COLOR + ";"
    
    if is_warning_a:
        border_a = "border: 2px solid #dc2626;"
    if is_warning_b:
        border_b = "border: 2px solid #dc2626;"
    
    st.markdown(f"""
    <div class="metric-card" style="{border_a} padding: 10px 14px; margin-bottom: 6px; border-radius: 6px;">
        <div style="font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 500;">Twin A</div>
        <div style="font-size: 1.4rem; font-weight: 700; color: {color_a}; font-variant-numeric: tabular-nums; margin-top: 2px;">{format_value(value_a)}</div>
    </div>
    <div class="metric-card" style="{border_b} padding: 10px 14px; border-radius: 6px;">
        <div style="font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 500;">Twin B</div>
        <div style="font-size: 1.4rem; font-weight: 700; color: {color_b}; font-variant-numeric: tabular-nums; margin-top: 2px;">{format_value(value_b)}</div>
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# MAIN APPLICATION
# =============================================================================

def render_sidebar():
    """Render the sidebar with authentication and settings."""
    with st.sidebar:
        st.markdown("**Expedition Control**")
        
        st.divider()
        
        # Display Settings
        st.markdown("**Display**")
        col1, col2 = st.columns(2)
        with col1:
            dark_mode = st.toggle(
                "🌙 Dark",
                value=st.session_state.dark_mode,
                help="Toggle dark mode for nighttime monitoring"
            )
            if dark_mode != st.session_state.dark_mode:
                st.session_state.dark_mode = dark_mode
                st.rerun()
        
        st.divider()
        
        # OAuth Configuration
        st.markdown("**API Credentials**")
        
        # Load saved credentials
        saved_creds = load_credentials()
        
        # Only show config if credentials not loaded from secrets
        if not (hasattr(st, 'secrets') and 'oura' in st.secrets):
            st.markdown("**API Credentials**")
            
            # Load saved credentials
            saved_creds = load_credentials()
            
            with st.expander("Configure", expanded=not saved_creds.get('client_id')):
                client_id = st.text_input(
                    "Client ID",
                    value=saved_creds.get('client_id', ''),
                    type="password"
                )
                client_secret = st.text_input(
                    "Client Secret",
                    value=saved_creds.get('client_secret', ''),
                    type="password"
                )
                redirect_uri = st.text_input(
                    "Redirect URI",
                    value=saved_creds.get('redirect_uri', 'http://localhost:8501')
                )
                
                # Save button
                if st.button("Save", type="primary", use_container_width=True):
                    if client_id and client_secret:
                        save_credentials(client_id, client_secret, redirect_uri)
                        st.session_state.client_id = client_id
                        st.session_state.client_secret = client_secret
                        st.session_state.redirect_uri = redirect_uri
                        st.success("Saved")
                        st.rerun()
                    else:
                        st.error("Enter both ID and Secret")
                
                if saved_creds.get('client_id'):
                    st.caption("Credentials saved")
            
        st.divider()
        
        # Twin A Connection
        st.markdown("**Twin A**")
        if is_token_valid('twin_a'):
            st.success("Connected")
            if st.button("Disconnect", key="disconnect_a", use_container_width=True):
                st.session_state.twin_a_token = None
                st.session_state.twin_a_refresh_token = None
                remove_twin_tokens('twin_a')
                st.rerun()
        else:
            st.error("Not Connected")
            # Ensure we have credentials before showing connect button
            if saved_creds.get('client_id') and saved_creds.get('client_secret'):
                auth_url = get_authorization_url('twin_a')
                st.link_button("Connect Twin A", auth_url, use_container_width=True)
            else:
                st.caption("Save credentials first")
        
        st.divider()
        
        # Twin B Connection
        st.markdown("**Twin B**")
        if is_token_valid('twin_b'):
            st.success("Connected")
            if st.button("Disconnect", key="disconnect_b", use_container_width=True):
                st.session_state.twin_b_token = None
                st.session_state.twin_b_refresh_token = None
                remove_twin_tokens('twin_b')
                st.rerun()
        else:
            st.error("Not Connected")
            if saved_creds.get('client_id') and saved_creds.get('client_secret'):
                auth_url = get_authorization_url('twin_b')
                st.link_button("Connect Twin B", auth_url, use_container_width=True)
                st.caption("Will prompt for fresh login")
            else:
                st.caption("Save credentials first")
        
        st.divider()
        
        # Date Range Selection
        st.markdown("**Date Range**")
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Start",
                value=st.session_state.date_range[0],
                max_value=date.today(),
                label_visibility="collapsed"
            )
        with col2:
            end_date = st.date_input(
                "End",
                value=st.session_state.date_range[1],
                max_value=date.today(),
                label_visibility="collapsed"
            )
        
        if start_date > end_date:
            st.error("Invalid date range")
        else:
            st.session_state.date_range = (start_date, end_date)
        
        # Quick date range buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("7 Days", use_container_width=True):
                st.session_state.date_range = (date.today() - timedelta(days=7), date.today())
                st.rerun()
        with col2:
            if st.button("14 Days", use_container_width=True):
                st.session_state.date_range = (date.today() - timedelta(days=14), date.today())
                st.rerun()
        
        st.divider()
        
        # Rate Limit Info - compact
        remaining = RATE_LIMIT_REQUESTS - st.session_state.request_count
        st.caption(f"API: {remaining:,}/{RATE_LIMIT_REQUESTS:,} requests")
        st.progress(remaining / RATE_LIMIT_REQUESTS)
        
        st.divider()
        st.caption("v2.0 - For Dr. Patrycja")

def render_main_content():
    """Render the main dashboard content."""
    
    # Header
    st.markdown('<div class="main-header">Twin Physiology Monitor</div>', unsafe_allow_html=True)
    st.markdown('<div class="expedition-context">High-Altitude Expedition • Biometric Monitoring Dashboard</div>', unsafe_allow_html=True)
    
    # Get data
    start_date, end_date = st.session_state.date_range
    
    # Fetch real data
    twin_a_connected = is_token_valid('twin_a')
    twin_b_connected = is_token_valid('twin_b')
    
    raw_data_a = fetch_all_twin_data('twin_a', start_date, end_date) if twin_a_connected else {}
    raw_data_b = fetch_all_twin_data('twin_b', start_date, end_date) if twin_b_connected else {}
    
    # Process data
    df_a = process_twin_data(raw_data_a)
    df_b = process_twin_data(raw_data_b)
    
    # Get latest metrics
    metrics_a = get_latest_metrics(df_a)
    metrics_b = get_latest_metrics(df_b)
    
    # ==========================================================================
    # STATUS SECTION - Compact
    # ==========================================================================
    col_status1, col_status2 = st.columns(2)
    with col_status1:
        if metrics_a['last_sync']:
            sync_time = metrics_a['last_sync']
            if isinstance(sync_time, pd.Timestamp):
                sync_time = sync_time.strftime('%Y-%m-%d')
            st.caption(f"**Twin A** synced: {sync_time}")
        else:
            st.caption("**Twin A**: No data")
    
    with col_status2:
        if metrics_b['last_sync']:
            sync_time = metrics_b['last_sync']
            if isinstance(sync_time, pd.Timestamp):
                sync_time = sync_time.strftime('%Y-%m-%d')
            st.caption(f"**Twin B** synced: {sync_time}")
        else:
            st.caption("**Twin B**: No data")
    
    st.divider()
    
    # ==========================================================================
    # EXERCISE SESSION COMPARISON (IHT Study - Intraday Heart Rate)
    # ==========================================================================
    st.markdown("### 🏃 Exercise Session Comparison")
    st.caption("Real-time heart rate monitoring: **Twin A** (IHT - Intermittent Hypoxic Training) vs **Twin B** (Regular Training)")
    
    # Timeframe selector
    exercise_col1, exercise_col2 = st.columns([1, 4])
    with exercise_col1:
        exercise_hours = st.selectbox(
            "Timeframe",
            options=[1, 2, 4, 8],
            index=2,  # Default to 4 hours
            format_func=lambda x: f"Last {x}h",
            key="exercise_timeframe"
        )
    
    # Fetch intraday data from API
    intraday_a = get_intraday_data_for_twin('twin_a', exercise_hours) if twin_a_connected else []
    intraday_b = get_intraday_data_for_twin('twin_b', exercise_hours) if twin_b_connected else []
    
    # Get dark mode state
    is_dark = st.session_state.get('dark_mode', False)
    
    # Create and display the chart
    fig_exercise = create_intraday_comparison_chart(intraday_a, intraday_b, dark_mode=is_dark)
    st.plotly_chart(fig_exercise, use_container_width=True)
    
    # Show quick stats
    if intraday_a or intraday_b:
        ex_stats_col1, ex_stats_col2, ex_stats_col3, ex_stats_col4 = st.columns(4)
        
        with ex_stats_col1:
            if intraday_a:
                max_hr_a = max(d['bpm'] for d in intraday_a)
                st.metric("Twin A Peak HR", f"{max_hr_a} bpm")
            else:
                st.metric("Twin A Peak HR", "—")
        
        with ex_stats_col2:
            if intraday_b:
                max_hr_b = max(d['bpm'] for d in intraday_b)
                st.metric("Twin B Peak HR", f"{max_hr_b} bpm")
            else:
                st.metric("Twin B Peak HR", "—")
        
        with ex_stats_col3:
            if intraday_a:
                avg_hr_a = int(sum(d['bpm'] for d in intraday_a) / len(intraday_a))
                st.metric("Twin A Avg HR", f"{avg_hr_a} bpm")
            else:
                st.metric("Twin A Avg HR", "—")
        
        with ex_stats_col4:
            if intraday_b:
                avg_hr_b = int(sum(d['bpm'] for d in intraday_b) / len(intraday_b))
                st.metric("Twin B Avg HR", f"{avg_hr_b} bpm")
            else:
                st.metric("Twin B Avg HR", "—")
    
    if not intraday_a and not intraday_b:
        st.caption("💡 *Connect Oura accounts to see intraday heart rate data.*")
    
    st.divider()
    
    # ==========================================================================
    # KPI METRICS SECTION (Doctor's Heads-Up Display)
    # ==========================================================================
    st.markdown("### Latest Readings")
    
    # Check for critical SpO2 levels
    critical_spo2_a = metrics_a['spo2'] is not None and metrics_a['spo2'] < 90
    critical_spo2_b = metrics_b['spo2'] is not None and metrics_b['spo2'] < 90
    
    if critical_spo2_a or critical_spo2_b:
        st.markdown("""
        <div class="altitude-warning">
            <strong>ALERT:</strong> SpO2 below 90% detected. Consider supplemental oxygen or descent.
        </div>
        """, unsafe_allow_html=True)
    
    # All KPIs in a single row using 5 columns
    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        st.write("**SpO2 %**")
        render_kpi_metric("SPO2", metrics_a['spo2'], metrics_b['spo2'], "%", warning_threshold=90, warning_direction="below")
    
    with c2:
        st.write("**Resting HR**")
        render_kpi_metric("RHR", metrics_a['rhr'], metrics_b['rhr'], " bpm")
    
    with c3:
        st.write("**HRV**")
        render_kpi_metric("HRV", metrics_a['hrv'], metrics_b['hrv'], " ms")
    
    with c4:
        st.write("**Resp Rate**")
        render_kpi_metric("RESP", metrics_a['respiratory_rate'], metrics_b['respiratory_rate'], "")
    
    with c5:
        st.write("**Sleep**")
        render_kpi_metric("SCORE", metrics_a['sleep_score'], metrics_b['sleep_score'], "")
    
    st.divider()
    
    # ==========================================================================
    # VISUALIZATION SECTION
    # ==========================================================================
    st.markdown("### Trend Analysis")
    
    # Info about data availability
    # Info about data availability
    with st.expander("About Data Availability", expanded=False):
            st.markdown("""
            **Why might some metrics show "No Data"?**
            - **SpO2**: Requires SpO2 monitoring enabled in Oura app settings
            - **Cardiovascular Age**: Requires consistent ring wear over time
            - **Sleep data**: User must sync their ring with the Oura mobile app
            """)
    
    # Create layout for charts - Row 1
    col1, col2 = st.columns(2)
    
    # Get dark mode state
    is_dark = st.session_state.get('dark_mode', False)

    with col1:
        # Chart 1: Nocturnal SpO2
        st.write("**Nocturnal SpO2** — Critical for altitude")
        fig_spo2 = create_comparative_line_chart(
            df_a, df_b,
            y_column='spo2',
            title='SpO2 %',
            y_axis_title='SpO2 (%)',
            show_reference_line=(90, '90% threshold'),
            dark_mode=is_dark
        )
        st.plotly_chart(fig_spo2, use_container_width=True)
    
    with col2:
        # Chart 2: Resting Heart Rate (New separate chart)
        st.write("**Resting Heart Rate** — Altitude response")
        fig_rhr = create_comparative_line_chart(
            df_a, df_b,
            y_column='lowest_heart_rate',
            title='Resting Heart Rate (bpm)',
            y_axis_title='RHR (bpm)',
            dark_mode=is_dark
        )
        st.plotly_chart(fig_rhr, use_container_width=True)
    
    # Row 2
    col3, col4 = st.columns(2)
    
    with col3:
        # Chart 3: HRV Trends
        st.write("**Heart Rate Variability** — Stress indicator")
        fig_hrv = create_comparative_line_chart(
            df_a, df_b,
            y_column='average_hrv',
            title='HRV (ms)',
            y_axis_title='HRV (ms)',
            dark_mode=is_dark
        )
        st.plotly_chart(fig_hrv, use_container_width=True)
    
    with col4:
        # Chart 4: Respiratory Rate (New separate chart)
        st.write("**Respiratory Rate** — Hypoxic response")
        fig_resp = create_comparative_line_chart(
            df_a, df_b,
            y_column='average_breath',
            title='Respiratory Rate (br/min)',
            y_axis_title='Resp (br/min)',
            dark_mode=is_dark
        )
        st.plotly_chart(fig_resp, use_container_width=True)

    # Row 3 (New Metrics)
    col5, col6 = st.columns(2)

    with col5:
        # Chart 5: Sleep Score
        st.write("**Sleep Score** — Recovery quality")
        fig_sleep = create_comparative_line_chart(
            df_a, df_b,
            y_column='sleep_score',
            title='Sleep Score',
            y_axis_title='Score (0-100)',
            show_reference_line=(85, 'Good'),
            dark_mode=is_dark
        )
        st.plotly_chart(fig_sleep, use_container_width=True)

    with col6:
        # Chart 6: Skin Temperature
        st.write("**Skin Temperature Deviation** — Illness indicator")
        fig_temp = create_comparative_line_chart(
            df_a, df_b,
            y_column='temperature_deviation',
            title='Skin Temp Deviation (°C)',
            y_axis_title='Deviation (°C)',
            show_reference_line=(0, 'Baseline'),
            dark_mode=is_dark
        )
        st.plotly_chart(fig_temp, use_container_width=True)
    

    
    # ==========================================================================
    # DATA TABLE (Expandable)
    # ==========================================================================
    with st.expander("View Raw Data Tables"):
        tab1, tab2 = st.tabs(["Twin A Data", "Twin B Data"])
        
        with tab1:
            if not df_a.empty:
                # Create a copy and fill NaN for display
                display_df_a = df_a.copy()
                st.dataframe(display_df_a, use_container_width=True)
            else:
                st.info("No data available for Twin A")
        
        with tab2:
            if not df_b.empty:
                display_df_b = df_b.copy()
                st.dataframe(display_df_b, use_container_width=True)
            else:
                st.info("No data available for Twin B")

def main():
    """Main application entry point."""
    # Check authentication first (for cloud deployment)
    if not check_password():
        st.stop()  # Don't run the rest of the app
    
    # Handle OAuth callback if present
    handle_oauth_callback()
    
    # Render sidebar
    render_sidebar()
    
    # Inject dark mode CSS if enabled
    inject_dark_mode_css()
    
    # Render main content
    render_main_content()
    
    # Footer
    st.markdown("---")
    st.caption("Twin Physiology Study • Oura Ring Gen 4 • Rate Limit: 5000 req/5 min")

if __name__ == "__main__":
    main()
