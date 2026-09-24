# Craigslist Poster & Lead Engine Pro 🚀

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/engine-Playwright%20Stealth-green.svg)](https://playwright.dev/)
[![Database](https://img.shields.io/badge/database-PostgreSQL%20%2F%20Neon-00E599.svg)](https://neon.tech/)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

An enterprise-grade, stealth automated Craigslist posting, lead capture, and campaign engine. Built with **Playwright Stealth**, dynamic multi-city metro routing, instant copy-paste form filling, automated ZIP code verification, recursive spintax variation, EXIF image metadata sanitization, and persistent session state handling.

---

## 📑 Table of Contents
1. [System Overview & Architecture](#-system-overview--architecture)
2. [External Services & What Needs to Be Connected](#-external-services--what-needs-to-be-connected)
3. [Environment Configuration (`.env`)](#-environment-configuration-env)
4. [File & Project Structure](#-file--project-structure)
5. [Quickstart & Execution Guide](#-quickstart--execution-guide)
6. [Multi-City Campaign Management](#-multi-city-campaign-management)
7. [Stealth & Anti-Detection Engineering](#-stealth--anti-detection-engineering)
8. [Troubleshooting & Gotchas](#-troubleshooting--gotchas)

---

## 🏗️ System Overview & Architecture

The engine automates the entire lifecycle of multi-metro ad distribution and lead capture:

```mermaid
graph TD
    A[Campaign Config: campaign_multicity.json] --> B[Spintax & Payload Engine]
    B -->|Generates Unique Ads| C[Craigslist Poster Worker]
    
    D[Account Sessions: data/sessions/] -->|Cookies & LocalStorage| E[Stealth Browser Context]
    F[Residential Proxy Provider] -->|Sticky Metro IPs| E
    E --> C
    
    C -->|Bypass Copy-From-Previous| G[Area Dropdown Selector]
    G -->|Metro Routing: LA, Miami, NYC, etc.| H[Sub-Area & Category Picker]
    H -->|Instant Copy-Paste Form Fill| I[Verified Main Form + ZIP]
    I -->|Advance Past Location Map| J[Preview Screen]
    J -->|Publish Live| K[Published Ad Receipt + Screenshot]
    
    K --> L[(Database: Neon PostgreSQL)]
    M[Inbound Inquiries: Text/Call] --> N[Lead Pipeline: leads.json / leads.csv]
```

---

## 🔌 External Services & What Needs to Be Connected

To take this engine from local testing to a fully autonomous 24/7 cloud operation, connect the following 6 components:

### 1. Database Layer: Neon (Serverless PostgreSQL)
* **Status**: Connectable via `neonctl` and `DATABASE_URL`.
* **Purpose**: Stores campaign runs, published URLs, lead responses, spintax history, and account metrics.
* **How to Connect**:
  1. Retrieve your connection string from the Neon Console (`console.neon.tech`).
  2. Set `DATABASE_URL="postgresql://user:password@ep-xyz.neon.tech/neondb?sslmode=require"` in `.env`.
  3. Install Neon CLI in PowerShell: `npm install -g neonctl && neonctl auth`.

### 2. Craigslist Account & Session State
* **Status**: Ready and pre-configured for `pinnacleaisoulutions@gmail.com`.
* **Purpose**: Bypasses Craigslist guest email verification links and avoids login CAPTCHAs on every run.
* **How to Connect**:
  - Run the visual session generator to log in or refresh your cookies:
    ```bash
    python login.py
    ```
  - State files are automatically encrypted and stored in `data/sessions/default_state.json`.

### 3. Residential / Mobile Proxy Network (Optional for Scale)
* **Status**: Configurable in `config/default_config.yaml`.
* **Purpose**: Prevents IP-level Craigslist rate limits, shadowbans, and geographic mismatch flags when posting across multiple cities in rapid succession.
* **Recommended Providers**: Bright Data, Oxylabs, Smartproxy, or Webshare.
* **Setup**:
  - Use sticky residential sessions pinned to the target city (e.g. Miami IP for `miami`, LA IP for `losangeles`).
  - Add proxy credentials to `.env`:
    ```env
    PROXY_SERVER=http://pr.oxylabs.io:7777
    PROXY_USERNAME=customer-xyz-city-losangeles
    PROXY_PASSWORD=secret
    ```

### 4. SMS / Voice Forwarding & Inbound Relay
* **Status**: Configured in campaign template (`default_contact.phone`).
* **Purpose**: Handles inbound inquiries from creators/leads while protecting your private phone number.
* **Setup**:
  - Use a dedicated virtual business line: **OpenPhone**, **Twilio**, or **Telnyx**.
  - Current campaign route: `(617) 792-8254`.

### 5. Email Forwarding / IMAP Listener (For Guest Posting)
* **Status**: Scaffolded in `workers/email_verifier.py`.
* **Purpose**: If posting without a logged-in Craigslist account, Craigslist emails an activation link. The IMAP worker monitors your inbox, extracts the link, and triggers publication automatically.
* **Setup**:
  - Supply your email IMAP credentials in `.env` (`IMAP_HOST`, `IMAP_USER`, `IMAP_PASS`).

### 6. GitHub Actions / Cloud Run (Scheduled Cron Pacing)
* **Status**: Ready for CI/CD deployment.
* **Purpose**: Automatically cycles through scheduled cities every few hours without needing a local terminal open.

---

## ⚙️ Environment Configuration (`.env`)

Create a `.env` file in the root directory:

```env
# ==========================================
# DATABASE (NEON POSTGRESQL)
# ==========================================
DATABASE_URL=postgresql://user:password@ep-cool-mountain.neon.tech/neondb?sslmode=require
NEON_API_KEY=neon_api_key_xxxxxxxxxxxx

# ==========================================
# PROXY CONFIGURATION (OPTIONAL)
# ==========================================
USE_PROXY=false
PROXY_SERVER=http://residential-proxy.example.com:8000
PROXY_USERNAME=proxy_user
PROXY_PASSWORD=proxy_pass

# ==========================================
# IMAP EMAIL CONFIRMATION (GUEST POSTING)
# ==========================================
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=pinnacleaisoulutions@gmail.com
IMAP_PASS=your_app_password_here

# ==========================================
# BROWSER & PACING SETTINGS
# ==========================================
HEADLESS=true
PACING_COOLDOWN_MINUTES=5
```

---

## 📁 File & Project Structure

```text
craigslistautoposter/
├── config/
│   ├── settings.py             # Pydantic environment configuration loader
│   └── default_config.yaml     # Pacing, rate limits, and browser settings
├── core/
│   ├── browser.py              # Stealth Playwright browser factory
│   ├── session.py              # Cookie and storage_state persistence engine
│   ├── proxy.py                # Residential proxy routing
│   └── rate_limiter.py         # Cooldown enforcement & anti-detection delays
├── payload/
│   ├── models.py               # PostPayload, AccountCredentials, JobResult models
│   ├── spintax.py              # Recursive Spintax generator (unlimited nested levels)
│   └── exif_scrubber.py        # EXIF metadata sanitization and re-encoding
├── workers/
│   ├── poster.py               # Core posting worker: navigation, form fill, ZIP verification
│   └── email_verifier.py       # IMAP automated confirmation link listener
├── data/
│   ├── sessions/               # Saved session tokens (default_state.json)
│   ├── templates/              # Campaign templates (campaign_multicity.json)
│   └── images/                 # Processed and cleaned image assets
├── post_silver_rose.py         # Multi-city command runner (--city-index, --publish)
├── login.py                    # Interactive session generator & cookie saver
├── menu.py                     # Rich terminal interactive dashboard
├── pyproject.toml              # Dependencies & packaging metadata
└── README.md                   # System documentation
```

---

## 🚀 Quickstart & Execution Guide

### 1. Prerequisites & Installation
Ensure you have **Python 3.10+** and **Node.js** installed:

```powershell
# Clone or navigate to the repository
cd C:\Users\futur\gemini_workspace\craigslistautoposter

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies and Playwright Chromium
pip install -r requirements.txt
playwright install chromium
```

### 2. Login & Save Session (One-Time Setup)
```powershell
python login.py
```
* Opens a visual Chromium window.
* Log in to your Craigslist account.
* The script detects successful login and automatically writes session state to `data/sessions/default_state.json`.

### 3. Launch the Interactive Dashboard
```powershell
python menu.py
```
Provides an interactive menu to test campaigns, inspect session states, preview spintax, or trigger live publications.

---

## 🌐 Multi-City Campaign Management

The campaign configuration is defined in [`data/templates/campaign_multicity.json`](data/templates/campaign_multicity.json). Target cities are indexed in priority order:

| Index | Metro Subdomain | City | Sub-Area | Target Postal Code |
| :---: | :--- | :--- | :--- | :---: |
| **0** | `losangeles` | Los Angeles, CA | Central LA | `90012` |
| **1** | `miami` | Miami / South Florida | Miami / Dade County | `33101` |
| **2** | `newyork` | New York City, NY | Manhattan | `10001` |
| **3** | `houston` | Houston, TX | Downtown | `77002` |
| **4** | `chicago` | Chicago, IL | Loop / City of Chicago | `60601` |

### Terminal Commands

#### Dry-Run Preview (Safe Verification)
Generates the spintax ad, navigates the selectors, fills the form, verifies the ZIP code, bypasses the map, and saves a preview snapshot without publishing:
```powershell
# Preview Miami (City #2)
python post_silver_rose.py --city-index 1 --headless

# Preview Los Angeles (City #1)
python post_silver_rose.py --city-index 0 --headless
```

#### Live Publication
Navigates the complete flow and clicks the **Publish** button, saving the live confirmation URL and receipt screenshot:
```powershell
# Publish City 1 (Los Angeles)
python post_silver_rose.py --city-index 0 --publish

# Publish City 2 (Miami)
python post_silver_rose.py --city-index 1 --publish

# Publish City 3 (New York City)
python post_silver_rose.py --city-index 2 --publish

# Publish City 4 (Houston)
python post_silver_rose.py --city-index 3 --publish

# Publish City 5 (Chicago)
python post_silver_rose.py --city-index 4 --publish
```

---

## 🛡️ Stealth & Anti-Detection Engineering

This engine solves the classic pitfalls of Craigslist browser automation:

1. **Copy-Paste Form Filling**:
   - Rather than slow character-by-character typing which triggers field timeouts on long bodies, the engine utilizes atomic `page.fill(...)` with DOM event dispatching (`input`, `change`) for sub-second form completion.
2. **Guaranteed Postal / ZIP Code Verification**:
   - Accurately targets `#postal_code` and `input[name='postal']`, performs an immediate input value read-back check, and applies DOM-level event injection if Craigslist attempts to clear the field.
3. **Automated Area Dropdown Mapping**:
   - Automatically handles the Craigslist `s=area` routing trap where unhandled dropdowns default to Aberdeen, UK. Mapped directly:
     - `miami` &rarr; `south florida`
     - `losangeles` &rarr; `los angeles`
     - `newyork` &rarr; `new york city`
4. **Copy-From-Previous Bypass**:
   - Automatically detects and clicks `[skip]` on the *"Re-use selected data from your previous posting"* screen to ensure each city is posted with fresh, targeted metro criteria.
5. **EXIF Metadata Cleansing**:
   - Every image uploaded passes through Pillow to wipe GPS geolocation, device serial numbers, and camera signatures.

---

## 🔧 Troubleshooting & Gotchas

* **Craigslist Missing ZIP code warning**:
  - Always verify that the target city is correctly mapped in the area dropdown before the form screen. UK/international markets reject standard 5-digit US ZIP codes.
* **Session Expired**:
  - If Craigslist prompts for email verification despite a saved session, rerun `python login.py` to refresh your authentication tokens.
* **Headless vs Visual**:
  - To watch the browser in real-time for debugging, omit `--headless`:
    ```powershell
    python post_silver_rose.py --city-index 1
    ```

---

## ⚖️ License & Disclaimer
This software is provided for educational and business workflow automation purposes. Ensure your usage adheres to the terms of service of the target platform and applicable local regulations.
