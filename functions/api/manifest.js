/**
 * Cloudflare Pages Function: GET /api/manifest
 * Fetches the live localization release manifest from Firebase Realtime Database
 * using Option B: Pure Firebase Auth (or public read).
 */

import { getFirebaseIdToken } from "./utils/firebase-auth.js";

export async function onRequestGet(context) {
  const env = context.env || {};
  const url = new URL(context.request.url);
  const targetEnv = url.searchParams.get("env") || "production";

  const databaseUrl = (env.FIREBASE_DATABASE_URL || "https://sample-localization-management-default-rtdb.firebaseio.com").replace(/\/+$/, "");

  let token = null;
  if (env.FIREBASE_API_KEY && env.FIREBASE_PUBLISHER_EMAIL && env.FIREBASE_PUBLISHER_PASSWORD) {
    try {
      token = await getFirebaseIdToken(env);
    } catch (e) {
      // Manifest reading is public by default (.read: true); fallback gracefully
      console.warn("Could not acquire Firebase ID token for read; falling back to unauthenticated read:", e.message);
    }
  }

  // Primary path: /localization/releases/{env}/manifest.json
  // Fallback path: /localization.json / /localization/locales.json
  const manifestUrl = token
    ? `${databaseUrl}/localization/releases/${targetEnv}/manifest.json?auth=${token}`
    : `${databaseUrl}/localization/releases/${targetEnv}/manifest.json`;

  try {
    let resp = await fetch(manifestUrl, {
      headers: { "Accept": "application/json" }
    });

    let manifest = null;
    if (resp.ok) {
      manifest = await resp.json();
    }

    // If environment manifest is null or empty, check root /localization/locales.json
    if (!manifest || Object.keys(manifest).length === 0) {
      const rootUrl = token
        ? `${databaseUrl}/localization/locales.json?auth=${token}`
        : `${databaseUrl}/localization/locales.json`;
      const rootResp = await fetch(rootUrl);
      if (rootResp.ok) {
        const localesData = await rootResp.json();
        if (localesData) {
          manifest = {
            environment: targetEnv,
            schema_version: "1.0.0",
            locales: localesData,
            updated_at: new Date().toISOString()
          };
        }
      }
    }

    return new Response(JSON.stringify({
      success: true,
      environment: targetEnv,
      database_url: databaseUrl,
      manifest: manifest || {
        environment: targetEnv,
        schema_version: "1.0.0",
        locales: {},
        updated_at: null
      },
      fetched_at: new Date().toISOString()
    }), {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store, no-cache, must-revalidate"
      }
    });

  } catch (err) {
    return new Response(JSON.stringify({
      success: false,
      error: `Failed to fetch manifest from Firebase: ${err.message}`,
      environment: targetEnv,
      database_url: databaseUrl
    }), {
      status: 502,
      headers: { "Content-Type": "application/json" }
    });
  }
}
