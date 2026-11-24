# Cloudflare Pages & Firebase Localization Deployment Manual

**Version:** 2.0.0 (Pure Firebase Authentication - Zero Service Account)  
**Target Project:** `sample-localization-manager` & EthOS Production Infrastructure  
**Audience:** DevOps / System Administrators / Lead Engineers  

This manual provides complete, step-by-step, copy-pasteable instructions to obtain all required credentials, configure Firebase Authentication, deploy Security Rules, and configure **Cloudflare Pages** for zero-restart dynamic localization deployments without using GCP Service Account private keys.

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
│   │  • OpenAI Trans.   │───────>│  POST /api/translate (AI Proxy)  │   │
│   └────────────────────┘        └─────────────────┬────────────────┘   │
└───────────────────────────────────────────────────┼────────────────────┘
                                                    │
      Pure Firebase ID Token Auth (Zero Service Account)
                                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     FIREBASE CLOUD INFRASTRUCTURE                      │
│                                                                        │
│   Firebase Cloud Storage REST API    Firebase Realtime Database        │
│   (storage.rules enforced)           (database.rules.json enforced)    │
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

## Phase 1: Step-by-Step Manual Setup in Firebase Console

Follow these steps to obtain all configuration values and credentials from the Firebase Console.

### Step 1.1: Enable Email/Password Sign-In Method
*(Firebase Authentication must permit email/password authentication for the publisher identity)*
1. Open the [Firebase Console](https://console.firebase.google.com/).
2. Select your project:
   - For Sample/Staging: **`sample-localization-management`** (or `ethos-chat`)
   - For Production: **`ethosapp-11363`**
3. In the left sidebar, expand **Build** &rarr; click **Authentication**.
4. Click on the **Sign-in method** tab.
5. In the providers list, click on **Email/Password**.
6. Toggle **Enable** to ON (leave "Email link (passwordless sign-in)" disabled).
7. Click **Save**.

### Step 1.2: Create the Dedicated Publisher User
*(This identity acts as the authorized publisher for both Cloud Storage and Realtime Database)*
1. In the same **Authentication** section, click on the **Users** tab.
2. Click the **Add user** button in the top right.
3. In the dialog:
   - **Email**: `localization-publisher@ethosapp.com` (or your chosen service email)
   - **Password**: Generate a strong random password (32+ characters, e.g. using `openssl rand -base64 24` or a password manager).
4. Click **Add user**.
5. Locate the newly created user in the Users table.
6. In the **User UID** column, copy the unique alphanumeric string (e.g. `8S7uHiRiViXeuvjz8RgBiJc5TCy2` for sample).
   - Save this UID; you will paste it into `database.rules.json` and `storage.rules`.

### Step 1.3: Retrieve the Firebase Web API Key (`FIREBASE_API_KEY`)
*(Used by Cloudflare Edge Functions to communicate with the Firebase Identity Toolkit REST API)*
1. In the Firebase Console, click the **Gear icon (Project settings)** next to "Project Overview" in the top-left corner.
2. Under the **General** tab, scroll down to the **Your project** card.
3. Locate **Web API Key**.
4. Copy the key (it starts with `AIzaSy...`).
   - *Note: The Web API key identifies your Firebase project in public REST calls and does not grant administrative privileges by itself.*

### Step 1.4: Retrieve the Realtime Database URL (`FIREBASE_DATABASE_URL`)
1. In the left sidebar, expand **Build** &rarr; click **Realtime Database**.
2. At the top of the **Data** tab, copy the root database URL.
   - Example: `https://sample-localization-management-default-rtdb.firebaseio.com`

### Step 1.5: Retrieve the Cloud Storage Bucket Name (`FIREBASE_STORAGE_BUCKET`)
1. In the left sidebar, expand **Build** &rarr; click **Storage**.
2. At the top of the **Files** tab, locate the bucket name (above the file browser).
   - Example: `sample-localization-management.firebasestorage.app` (or `sample-localization-management.appspot.com`)
   - *Note: Do not include `gs://` prefix when copying the bucket name.*

---

## Phase 2: Deploy Firebase Security Rules

Deploy declarative rules so only the authenticated publisher UID can write to `/localization` and storage paths.

### Step 2.1: Deploy Realtime Database Rules (`database.rules.json`)
1. In Firebase Console, go to **Build** &rarr; **Realtime Database** &rarr; **Rules** tab.
2. Paste the rules from `database.rules.json`:
   *(Replace `'PUBLISHER_UID'` with your actual User UID from Step 1.2)*
```json
{
  "rules": {
    "localization": {
      ".read": true,
      ".write": "auth != null && (auth.uid === '8S7uHiRiViXeuvjz8RgBiJc5TCy2' || auth.token.email === 'localization-publisher@ethosapp.com')",
      ".validate": "newData.hasChildren(['schema_version', 'environment', 'default_locale', 'updated_at', 'source_catalog_sha256', 'locales'])",
      "schema_version": {
        ".validate": "newData.isString() && newData.val().matches(/^[0-9]+\\.[0-9]+\\.[0-9]+$/)"
      },
      "environment": {
        ".validate": "newData.isString() && (newData.val() === 'development' || newData.val() === 'staging' || newData.val() === 'production')"
      },
      "default_locale": {
        ".validate": "newData.isString() && newData.val() === 'en'"
      },
      "updated_at": {
        ".validate": "newData.isString()"
      },
      "source_catalog_version": {
        ".validate": "newData.isString()"
      },
      "source_catalog_sha256": {
        ".validate": "newData.isString() && newData.val().matches(/^[0-9a-fA-F]{64}$/)"
      },
      "locales": {
        "$locale": {
          ".validate": "newData.hasChildren(['locale', 'version', 'path', 'checksum', 'status', 'coverage_percent', 'approved_keys_count', 'total_catalog_keys', 'published_at', 'publisher_id', 'rollback_metadata']) && $locale.matches(/^[a-z]{2}(-[A-Z]{2}|-[A-Za-z0-9]+)?$/)",
          "locale": {
            ".validate": "newData.isString() && newData.val() === $locale"
          },
          "version": {
            ".validate": "newData.isString() && newData.val().matches(/^[0-9]+\\.[0-9]+\\.[0-9]+$/)"
          },
          "path": {
            ".validate": "newData.isString() && newData.val().matches(/^localization\\/locales\\/[a-z]{2}(-[A-Z]{2}|-[A-Za-z0-9]+)?\\/[0-9]+\\.[0-9]+\\.[0-9]+\\/bundle\\.json$/)"
          },
          "checksum": {
            ".validate": "newData.isString() && newData.val().matches(/^[0-9a-fA-F]{64}$/)"
          },
          "payload_hash": {
            ".validate": "newData.isString() && newData.val().matches(/^[0-9a-fA-F]{64}$/)"
          },
          "status": {
            ".validate": "newData.isString() && (newData.val() === 'ACTIVE' || newData.val() === 'ROLLED_BACK' || newData.val() === 'DEPRECATED' || newData.val() === 'PENDING')"
          },
          "coverage_percent": {
            ".validate": "newData.isNumber() && newData.val() >= 0 && newData.val() <= 100"
          },
          "approved_keys_count": {
            ".validate": "newData.isNumber() && newData.val() >= 0"
          },
          "total_catalog_keys": {
            ".validate": "newData.isNumber() && newData.val() >= 0"
          },
          "published_at": {
            ".validate": "newData.isString()"
          },
          "publisher_id": {
            ".validate": "newData.isString()"
          },
          "rollback_metadata": {
            ".validate": "newData.hasChildren(['is_rollback'])"
          }
        }
      }
    },
    "$other": {
      ".read": false,
      ".write": false
    }
  }
}
```
3. Click **Publish**.

### Step 2.2: Deploy Cloud Storage Rules (`storage.rules`)
1. In Firebase Console, go to **Build** &rarr; **Storage** &rarr; **Rules** tab.
2. Paste the rules from `storage.rules`:
   *(Replace `'PUBLISHER_UID'` with your actual User UID from Step 1.2)*
```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    
    function isAuthenticated() {
      return request.auth != null;
    }
    
    function isPublisher() {
      return isAuthenticated() && 
        (request.auth.uid == '8S7uHiRiViXeuvjz8RgBiJc5TCy2' || request.auth.token.email == 'localization-publisher@ethosapp.com');
    }
    
    function isValidLocale(loc) {
      return loc.matches('^[a-z]{2}(-[A-Z]{2}|-[A-Za-z0-9]+)?$');
    }
    
    function isValidVersion(ver) {
      return ver.matches('^[0-9]+\\.[0-9]+\\.[0-9]+$');
    }
    
    match /localization/locales/{locale}/{version}/{filename} {
      allow read: if isValidLocale(locale) &&
                     isValidVersion(version) &&
                     filename == 'bundle.json';
      
      allow create: if isPublisher() &&
                       resource == null &&
                       isValidLocale(locale) &&
                       isValidVersion(version) &&
                       filename == 'bundle.json' &&
                       request.resource.size < 5 * 1024 * 1024 &&
                       request.resource.contentType.matches('application/json.*');
      
      allow update: if false;
      allow delete: if false;
    }
    
    match /{allPaths=**} {
      allow read: if false;
      allow write: if false;
    }
  }
}
```
3. Click **Publish**.

---

## Phase 3: Obtain OpenAI Translation Key (`OPENAI_API_KEY`)

The dashboard includes a one-click AI translation assistant powered by OpenAI (`gpt-4o-mini`).
1. Visit [OpenAI API Keys](https://platform.openai.com/api-keys).
2. Log in with your OpenAI account.
3. Click **Create new secret key**.
4. Name the key (e.g. `ethos-localization-publisher`).
5. Copy the generated key (starts with `sk-...` or `sk-proj-...`).
*(Note: Legacy `GEMINI_API_KEY` is also supported as a fallback during migration).*

---

## Phase 4: Configure Cloudflare Pages Environment Variables

1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. Navigate to **Compute (Workers & Pages)** &rarr; click your project: **`sample-localization-manager`** (or `ethos-localization`).
3. Click on **Settings** &rarr; **Environment variables**.
4. Click **Add variables** and configure the following variables for **both Production and Preview**:

| Variable Name | Type | How to Get / Value | Example Value |
|---|---|---|---|
| `FIREBASE_API_KEY` | Plaintext / Secret | From Step 1.3 (Firebase Console Project Settings) | `AIzaSy...` |
| `FIREBASE_PUBLISHER_EMAIL` | Plaintext | From Step 1.2 (User email created in Firebase Auth) | `localization-publisher@ethosapp.com` |
| `FIREBASE_PUBLISHER_PASSWORD` | **Secret** (Encrypted) | From Step 1.2 (User password created in Firebase Auth) | `YourSecureRandomPassword32!` |
| `FIREBASE_DATABASE_URL` | Plaintext | From Step 1.4 (Firebase Realtime Database URL) | `https://sample-localization-management-default-rtdb.firebaseio.com` |
| `FIREBASE_STORAGE_BUCKET` | Plaintext | From Step 1.5 (Firebase Cloud Storage bucket name) | `sample-localization-management.firebasestorage.app` |
| `OPENAI_API_KEY` | **Secret** (Encrypted) | From Phase 3 (OpenAI Platform API key) | `sk-proj-...` |

5. Click **Save**.
6. Navigate to **Deployments** &rarr; click **Retry deployment** (or trigger a new commit) to mount the new environment variables into the live edge runtime.

---

## Phase 5: Cloud Storage CORS Configuration

Because web browsers and mobile apps download JSON bundles directly from Firebase Cloud Storage, Cloud Storage must allow cross-origin requests.

### Step 5.1: Create `cors.json`
Verify `cors.json` exists in your workspace:
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

### Step 5.2: Apply CORS via Google Cloud SDK
Run the following command in terminal:
```bash
gcloud storage buckets update gs://sample-localization-management.firebasestorage.app --cors-file=cors.json
```
*(Replace bucket name with your production bucket if deploying to production).*

---

## Phase 6: Revoke Legacy GCP Service Account IAM Permissions

Under Option B, Service Account credentials are no longer needed for publishing or manifest updates.

If your project previously provisioned a service account (`ethos-localization-cf-publisher`):
1. Open [Google Cloud Console IAM](https://console.cloud.google.com/iam-admin/iam).
2. Locate the service account `ethos-localization-cf-publisher@...`.
3. Revoke **Firebase Realtime Database Admin** (`roles/firebasedatabase.admin`).
4. Revoke **Storage Object Admin** (`roles/storage.objectAdmin`).
5. In **IAM & Admin** &rarr; **Service Accounts**, click on `ethos-localization-cf-publisher` &rarr; **Keys** tab &rarr; delete any active JSON keys that were previously stored in `FIREBASE_SERVICE_ACCOUNT_KEY`.

---

## Phase 7: Verification and Health Check

### Step 7.1: Verify Health Endpoint
Open the health check endpoint in your browser or with curl:
```bash
curl https://sample-localization-manager.pages.dev/api/health
```
Expected JSON Response:
```json
{
  "status": "ok",
  "runtime": "cloudflare_pages",
  "version": "v2.0.0-pure-firebase-auth",
  "config": {
    "auth_mode": "pure_firebase_id_token",
    "has_firebase_auth": true,
    "publisher_email": "localization-publisher@ethosapp.com",
    "has_service_account": false,
    "database_url": "https://sample-localization-management-default-rtdb.firebaseio.com",
    "storage_bucket": "sample-localization-management.firebasestorage.app",
    "has_gemini_key": true
  }
}
```

### Step 7.2: Verify Deploy Flow from UI
1. Open the dashboard in your browser (`https://sample-localization-manager.pages.dev`).
2. Verify the top navigation indicators:
   - **RTDB Live**: Green pulse indicator.
   - **OpenAI Cloud**: Green sparkles indicator.
3. Select a locale (e.g. `es`), make an edit or approve strings.
4. Click **Publish to Firebase**.
5. Observe the deployment progress:
   - Bundle compilation & SHA-256 calculation.
   - Immutable bundle upload to Cloud Storage via REST API using Firebase ID token.
   - Read-back verification against SHA-256 checksum.
   - Atomic Realtime Database manifest update via REST API using Firebase ID token.
6. Open your iOS or Android sample application to verify zero-restart string updates!

---

## Troubleshooting Guide

| Issue | Root Cause | Solution |
|---|---|---|
| **Health endpoint reports `has_firebase_auth: false`** | `FIREBASE_API_KEY`, `FIREBASE_PUBLISHER_EMAIL`, or `FIREBASE_PUBLISHER_PASSWORD` not configured. | Add all three variables in Cloudflare Pages Settings &rarr; Environment variables. |
| **`Firebase publisher authentication failed: HTTP 400 (OPERATION_NOT_ALLOWED)`** | Email/Password provider is disabled in Firebase. | Follow Step 1.1: Firebase Console &rarr; Authentication &rarr; Sign-in method &rarr; Enable Email/Password. |
| **`Firebase publisher authentication failed: HTTP 400 (INVALID_LOGIN_CREDENTIALS)`** | Password or email does not match user in Firebase Auth. | Follow Step 1.2: Check user in Authentication &rarr; Users tab, or reset password. |
| **`Firebase Cloud Storage upload failed: HTTP 403`** | Storage Security Rules rejecting write. | Deploy `storage.rules` (Step 2.2) ensuring `request.auth.uid == 'PUBLISHER_UID'` or email matches. |
| **`Manifest write failed: HTTP 401`** | Realtime Database Rules rejecting write. | Deploy `database.rules.json` (Step 2.1) ensuring `auth.uid === 'PUBLISHER_UID'` or email matches. |
| **CORS error when downloading bundle on mobile web** | Cloud Storage bucket missing CORS headers. | Apply `cors.json` using `gcloud storage buckets update gs://<bucket> --cors-file=cors.json`. |
