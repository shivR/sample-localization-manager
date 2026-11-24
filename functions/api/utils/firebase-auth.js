/**
 * EthOS Firebase Authentication Identity Helper for Cloudflare Workers / Pages Functions
 * Implements Option B (Pure Firebase Auth): exchanges dedicated publisher user credentials
 * for a short-lived Firebase Authentication ID token via Google Identity Toolkit REST API.
 * Eliminates reliance on GCP Service Account keys and RS256 JWT signing.
 */

let cachedIdToken = null;
let idTokenExpiresAt = 0;

/**
 * Resets token cache (useful for testing or forced credential rotation)
 */
export function _resetTokenCache() {
  cachedIdToken = null;
  idTokenExpiresAt = 0;
}

/**
 * Obtains a valid Firebase Authentication ID token using email/password credentials
 * via the Firebase Auth REST API (Identity Toolkit).
 * Caches token in memory for ~55 minutes (standard ID token validity is 60 minutes).
 *
 * @param {Object} env - Cloudflare environment variables
 * @returns {Promise<string>} Firebase ID token
 */
export async function getFirebaseIdToken(env) {
  const now = Math.floor(Date.now() / 1000);

  // Return cached token if valid for at least 5 more minutes
  if (cachedIdToken && idTokenExpiresAt > now + 300) {
    return cachedIdToken;
  }

  const apiKey = env?.FIREBASE_API_KEY;
  const email = env?.FIREBASE_PUBLISHER_EMAIL;
  const password = env?.FIREBASE_PUBLISHER_PASSWORD;

  if (!apiKey || !email || !password) {
    const missing = [];
    if (!apiKey) missing.push("FIREBASE_API_KEY");
    if (!email) missing.push("FIREBASE_PUBLISHER_EMAIL");
    if (!password) missing.push("FIREBASE_PUBLISHER_PASSWORD");
    throw new Error(
      `Missing required Firebase Auth credentials: [${missing.join(", ")}]. ` +
      "Configure them in Cloudflare Pages Settings -> Environment Variables."
    );
  }

  const endpoint =
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=" +
    encodeURIComponent(apiKey);

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: email,
      password: password,
      returnSecureToken: true
    })
  });

  if (!response.ok) {
    let errorDetail = "";
    try {
      const errJson = await response.json();
      errorDetail = errJson.error?.message || JSON.stringify(errJson);
    } catch {
      errorDetail = await response.text();
    }
    throw new Error(`Firebase publisher authentication failed (HTTP ${response.status}): ${errorDetail}`);
  }

  const data = await response.json();
  if (!data.idToken) {
    throw new Error("Missing Firebase ID token in authentication response");
  }

  cachedIdToken = data.idToken;
  // expiresIn is in seconds as a string, e.g. "3600"
  const expiresInSec = parseInt(data.expiresIn, 10) || 3600;
  idTokenExpiresAt = now + expiresInSec;

  return cachedIdToken;
}

/**
 * Parses Service Account config from environment variables (Optional legacy helper)
 */
export function getServiceAccountConfig(env) {
  const rawKey = env?.FIREBASE_SERVICE_ACCOUNT_KEY;
  if (!rawKey) {
    return null;
  }

  try {
    if (typeof rawKey === "object") {
      return rawKey;
    }
    return JSON.parse(rawKey);
  } catch (err) {
    console.error("Failed to parse FIREBASE_SERVICE_ACCOUNT_KEY:", err);
    return null;
  }
}
