/**
 * Cloudflare Pages Function: GET /api/health
 * Returns environment health status and configuration availability
 * for Option B: Pure Firebase Authentication (Zero Service Account)
 * and OpenAI Translation Engine.
 */

export async function onRequestGet(context) {
  const env = context.env || {};

  const databaseUrl = env.FIREBASE_DATABASE_URL || "https://sample-localization-management-default-rtdb.firebaseio.com";
  const storageBucket = env.FIREBASE_STORAGE_BUCKET || "sample-localization-management.firebasestorage.app";
  const hasOpenAI = Boolean(env.OPENAI_API_KEY);
  const hasGemini = Boolean(env.GEMINI_API_KEY);

  const hasFirebaseAuth = Boolean(
    env.FIREBASE_API_KEY &&
    env.FIREBASE_PUBLISHER_EMAIL &&
    env.FIREBASE_PUBLISHER_PASSWORD
  );

  const status = {
    status: "ok",
    runtime: "cloudflare_pages",
    version: "v2.1.0-pure-firebase-openai",
    timestamp: new Date().toISOString(),
    config: {
      auth_mode: "pure_firebase_id_token",
      has_firebase_auth: hasFirebaseAuth,
      publisher_email: env.FIREBASE_PUBLISHER_EMAIL || null,
      has_service_account: false,
      database_url: databaseUrl,
      storage_bucket: storageBucket,
      has_openai_key: hasOpenAI,
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
