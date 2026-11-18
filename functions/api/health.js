/**
 * Cloudflare Pages Function: GET /api/health
 * Returns environment health status and configuration availability
 */

import { getServiceAccountConfig } from "./utils/firebase-auth.js";

export async function onRequestGet(context) {
  const env = context.env || {};
  const serviceAccount = getServiceAccountConfig(env);

  const databaseUrl = env.FIREBASE_DATABASE_URL || "https://sample-localization-management-default-rtdb.firebaseio.com";
  const storageBucket = env.FIREBASE_STORAGE_BUCKET || "sample-localization-management.firebasestorage.app";
  const hasGemini = Boolean(env.GEMINI_API_KEY);

  const status = {
    status: "ok",
    runtime: "cloudflare_pages",
    timestamp: new Date().toISOString(),
    config: {
      has_service_account: Boolean(serviceAccount && serviceAccount.client_email),
      service_account_email: serviceAccount ? serviceAccount.client_email : null,
      database_url: databaseUrl,
      storage_bucket: storageBucket,
      has_gemini_key: hasGemini
    }
  };

  return new Response(JSON.stringify(status, null, 2), {
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store, no-cache, must-revalidate"
    }
  });
}
