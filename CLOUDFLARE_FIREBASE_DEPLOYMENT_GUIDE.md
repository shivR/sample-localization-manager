# Cloudflare Pages & Firebase Localization Deployment Manual

**Version:** 1.0.0  
**Target Project:** `sample-localization-manager` & EthOS Production Infrastructure  
**Audience:** DevOps / System Administrators / Lead Engineers  

This manual provides the complete, copy-pasteable, step-by-step instructions to host the Localization Management Dashboard on **Cloudflare Pages** and securely connect it with **Firebase Realtime Database** and **Firebase Cloud Storage** for instant zero-restart dynamic localization deployments.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CLOUDFLARE EDGE NETWORK                         │
│                                                                        │
│   Client Browser                Cloudflare Pages Functions             │
│   (docs/index.html & app.js)    (/functions/api/*)                     │
│                                                                        │
│   ┌────────────────────┐        ┌──────────────────────────────────┐   │
│   │  Translation UI   │───────>│  GET  /api/health (Config Check) │   │
│   │  • Catalog Editor  │───────>│  GET  /api/manifest (Live RTDB)  │   │
│   │  • Deploy Button   │───────>│  POST /api/deploy (Atomic Pub)   │   │
│   │  • Gemini AI Draft │───────>│  POST /api/translate (AI Proxy)  │   │
│   └────────────────────┘        └─────────────────┬────────────────┘   │
└───────────────────────────────────────────────────┼────────────────────┘
                                                    │
                 Google OAuth2 Service Account Auth │ (Zero Secret Leakage)
                                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     FIREBASE CLOUD INFRASTRUCTURE                      │
│                                                                        │
│   Firebase Cloud Storage CDN         Firebase Realtime Database        │
│   (Immutable Bundles)                (Active Manifest Pointer)         │
│   ┌────────────────────────────┐     ┌─────────────────────────────┐   │
│   │ localization/locales/      │     │ /localization/releases/     │   │
│   │   ├── es/1.1.0/bundle.json │     │   └── production/manifest   │   │
│   │   └── th/1.0.0/bundle.json │     │ /localization/locales/{loc} │   │
│   └──────────────┬─────────────┘     └──────────────┬──────────────┘   │
└──────────────────┼──────────────────────────────────┼──────────────────┘
                   │                                  │
                   │  Gate 1 Checksum Verified CDN    │ Live Real-Time
                   │  JSON Bundle Fetch               │ Manifest Listener
                   ▼                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          MOBILE APPLICATIONS                           │
│                                                                        │
│          iOS App (SwiftUI)            Android App (Compose)            │
│          Instant 0ms Dynamic Swapping Without App Restart              │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Google Cloud / Firebase Service Account Provisioning

To enable Cloudflare Pages to securely publish bundles to Firebase Storage and update Realtime Database manifests without exposing credentials in client-side code:

### Step 1.1: Create Service Account in Google Cloud Console
1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Select your Firebase project: `sample-localization-management` (or your production project ID).
3. In the left navigation, go to **IAM & Admin** &rarr; **Service Accounts**.
4. Click **+ Create Service Account**:
   - **Service account name**: `ethos-localization-cf-publisher`
   - **Service account ID**: `ethos-localization-cf-publisher`
   - **Description**: `Cloudflare Pages serverless publisher for EthOS dynamic localization`
5. Click **Create and Continue**.

### Step 1.2: Grant Least-Privilege IAM Roles
Assign the following roles to the service account:
- **Firebase Realtime Database Admin** (`roles/firebasedatabase.admin`): Grants write access to update `/localization/releases/...` and `/localization/locales/...`.
- **Storage Object Admin** (`roles/storage.objectAdmin`): Grants upload and read-back verification access to the Cloud Storage bucket (`sample-localization-management.firebasestorage.app`).
Click **Continue**, then click **Done**.

### Step 1.3: Generate and Download JSON Private Key
1. In the Service Accounts list, click on the newly created `ethos-localization-cf-publisher` service account.
2. Select the **Keys** tab at the top.
3. Click **Add Key** &rarr; **Create new key**.
4. Select **JSON** format and click **Create**.
5. Save the downloaded `.json` key securely to your local machine (e.g. `service-account.json`).
   > [!CAUTION]
   > Never commit this `.json` key file to Git. It will only be added as an encrypted secret in the Cloudflare Pages dashboard.

### Step 1.4: Minify the JSON Key for Cloudflare Environment Variable
Run the following terminal command locally on your machine to convert the JSON key into a clean single-line string:

```bash
# On macOS / Linux:
cat path/to/service-account.json | jq -c . | pbcopy
# Or using python:
python3 -c "import json, sys; print(json.dumps(json.load(open('path/to/service-account.json'))))"
```
*(The single-line string is now in your clipboard ready for Cloudflare).*

---

## Phase 2: Cloudflare Pages Setup

### Step 2.1: Connect Repository to Cloudflare Pages
1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. In the left sidebar, click **Compute (Workers & Pages)** &rarr; **Overview**.
3. Click **Create application** &rarr; select the **Pages** tab.
4. Click **Connect to Git**:
   - Select your GitHub account.
   - Choose the repository: **`shivR/sample-localization-manager`** (or your organization fork).
   - Click **Begin setup**.

### Step 2.2: Configure Build Settings
Fill in the deployment parameters:
- **Project name**: `sample-localization-manager` (or `ethos-localization`)
- **Production branch**: `main`
- **Framework preset**: `None`
- **Build command**: *(Leave blank - pure static frontend + edge functions)*
- **Build output directory**: `docs`

### Step 2.3: Configure Encrypted Environment Variables (Secrets)
Under the **Environment variables** section (or in **Settings > Environment variables** after creation), add the following variables for both **Production** and **Preview**:

| Variable Name | Type | Value / Description | Example Value |
|---|---|---|---|
| `FIREBASE_SERVICE_ACCOUNT_KEY` | **Secret** (Encrypted) | Single-line JSON string from Step 1.4 | `{"type":"service_account","project_id":"sample-localization-management",...}` |
| `FIREBASE_DATABASE_URL` | Plaintext | Firebase Realtime Database URL | `https://sample-localization-management-default-rtdb.firebaseio.com` |
| `FIREBASE_STORAGE_BUCKET` | Plaintext | Firebase Cloud Storage bucket name | `sample-localization-management.firebasestorage.app` |
| `GEMINI_API_KEY` | **Secret** (Encrypted) | Google AI Gemini API Key (from Google AI Studio) | `AIzaSy...` |

Click **Save and Deploy**. Cloudflare Pages will build the static assets from `docs/` and automatically mount `/functions/api/*` edge functions.

---

## Phase 3: Firebase Cloud Storage CORS Configuration

Because web browsers and mobile apps download JSON bundles directly from Firebase Cloud Storage, Cloud Storage must allow cross-origin requests.

### Step 3.1: Create `cors.json`
Create a local file named `cors.json`:
```json
[
  {
    "origin": ["*"],
    "method": ["GET", "HEAD", "OPTIONS"],
    "responseHeader": [
      "Content-Type",
      "Content-Length",
      "ETag",
      "Cache-Control",
      "x-goog-hash",
      "x-goog-generation"
    ],
    "maxAgeSeconds": 3600
  }
]
```

### Step 3.2: Apply CORS via Google Cloud CLI / Shell
Run this command in your local terminal (or inside Google Cloud Shell):

```bash
# Set CORS on the localization storage bucket:
gcloud storage buckets update gs://sample-localization-management.firebasestorage.app --cors-file=cors.json

# Or using legacy gsutil:
gsutil cors set cors.json gs://sample-localization-management.firebasestorage.app
```

Verify that the CORS policy is active:
```bash
gcloud storage buckets describe gs://sample-localization-management.firebasestorage.app --format="default(cors)"
```

---

## Phase 4: Firebase Realtime Database Security Rules Verification

Open the Firebase Console &rarr; **Realtime Database** &rarr; **Rules** tab. Ensure your rules allow public or authenticated reading of `/localization` and restrict direct writes to administrators / service accounts:

```json
{
  "rules": {
    "localization": {
      ".read": true,
      ".write": "auth != null && (auth.token.role === 'publisher' || auth.token.admin === true)",
      "releases": {
        ".read": true,
        ".write": "auth != null && (auth.token.role === 'publisher' || auth.token.admin === true)"
      },
      "locales": {
        ".read": true,
        ".write": "auth != null && (auth.token.role === 'publisher' || auth.token.admin === true)"
      }
    }
  }
}
```
*(Note: Cloudflare Pages Functions authenticate using the Google Service Account via OAuth2, which automatically possesses administrative authorization).*

---

## Phase 5: End-to-End Verification Runbook

### Step 5.1: Verify Health Endpoint
Open in your browser:
```http
https://<your-project>.pages.dev/api/health
```
Expected JSON response:
```json
{
  "status": "ok",
  "runtime": "cloudflare_pages",
  "config": {
    "has_service_account": true,
    "service_account_email": "ethos-localization-cf-publisher@sample-localization-management.iam.gserviceaccount.com",
    "database_url": "https://sample-localization-management-default-rtdb.firebaseio.com",
    "storage_bucket": "sample-localization-management.firebasestorage.app",
    "has_gemini_key": true
  }
}
```

### Step 5.2: Verify Live Realtime Database Manifest Read
Open in your browser:
```http
https://<your-project>.pages.dev/api/manifest?env=production
```
Expected response:
```json
{
  "success": true,
  "environment": "production",
  "database_url": "https://sample-localization-management-default-rtdb.firebaseio.com",
  "manifest": {
    "locales": { ... }
  }
}
```

### Step 5.3: Test Deployment from the Web Dashboard
1. Open your Cloudflare Pages dashboard URL: `https://<your-project>.pages.dev/`.
2. Look at the header status badge:
   - It should display: **`RTDB Live`** with a green pulsing dot.
3. Select locale **Spanish (`es`)**.
4. Click **Deploy to Firebase**:
   - Choose **New Release Version**: e.g., `v1.1.0`.
   - Target Environment: `production`.
   - Click **Deploy Now**.
5. Observe the live stepper:
   - `Publishing ES v1.1.0 to Firebase...`
   - `Compiling bundle & calculating SHA-256 checksum...`
   - `✅ Successfully Deployed v1.1.0!`
6. Verify in the Firebase Console:
   - **Cloud Storage**: Open `sample-localization-management.firebasestorage.app` &rarr; Navigate to `localization/locales/es/1.1.0/bundle.json`. Verify the file exists.
   - **Realtime Database**: Navigate to `/localization/locales/es`. Verify `version` is `"1.1.0"`, `checksum` matches the SHA-256 hash, and `status` is `"ACTIVE"`.
7. **Mobile Client Verification**:
   - Open the iOS or Android sample app while running.
   - Observe visible strings update **instantly in real time without app restart or activity recreation**.

---

## Phase 6: Local Development with Cloudflare Wrangler (Optional)

To test Cloudflare Pages Functions locally before pushing to GitHub:

```bash
cd sample-localization-manager

# Install Wrangler CLI:
npm install -g wrangler

# Run local Pages development server with mock or real environment variables:
npx wrangler pages dev docs \
  --binding FIREBASE_DATABASE_URL="https://sample-localization-management-default-rtdb.firebaseio.com" \
  --binding FIREBASE_STORAGE_BUCKET="sample-localization-management.firebasestorage.app"
```

Open `http://localhost:8788` in your browser.

---

## Troubleshooting Guide

| Issue | Root Cause | Solution |
|---|---|---|
| **Health endpoint reports `has_service_account: false`** | `FIREBASE_SERVICE_ACCOUNT_KEY` environment variable not added or not deployed in Cloudflare. | In Cloudflare Pages, go to **Settings > Environment variables**, add `FIREBASE_SERVICE_ACCOUNT_KEY`, and trigger a new deployment. |
| **`Google OAuth2 token exchange failed: invalid_grant`** | Malformed private key or clock skew between edge and Google. | Ensure the full key including `-----BEGIN PRIVATE KEY-----` and `-----END PRIVATE KEY-----` is present. Re-copy using `cat key.json \| jq -c .`. |
| **`Firebase Cloud Storage upload failed: 403 Forbidden`** | Service account missing Storage permissions. | In Google Cloud IAM, grant the service account `Storage Object Admin` (`roles/storage.objectAdmin`). |
| **`Failed to update RTDB: 401 Unauthorized`** | Service account missing Realtime Database permissions. | In Google Cloud IAM, grant `Firebase Realtime Database Admin` (`roles/firebasedatabase.admin`). |
| **CORS error when downloading bundle on mobile web** | Cloud Storage bucket missing CORS headers. | Apply `cors.json` using `gcloud storage buckets update gs://<bucket> --cors-file=cors.json`. |
