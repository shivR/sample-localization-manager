/**
 * EthOS Firebase Admin OAuth2 Token Authenticator for Cloudflare Workers / Pages Functions
 * Performs zero-dependency RS256 JWT signing using Web Crypto API to exchange
 * a Google Service Account Private Key for a short-lived OAuth2 Access Token.
 */

let cachedToken = null;
let tokenExpiresAt = 0;

/**
 * Base64URL encoder helper
 */
function base64UrlEncode(strOrBuffer) {
  let base64;
  if (typeof strOrBuffer === "string") {
    base64 = btoa(strOrBuffer);
  } else {
    let binary = "";
    const bytes = new Uint8Array(strOrBuffer);
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    base64 = btoa(binary);
  }
  return base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/**
 * Imports PKCS#8 PEM string into a CryptoKey for RS256 signing
 */
async function importPrivateKey(pem) {
  // Clean PEM delimiters and whitespace
  const cleanPem = pem
    .replace(/-----BEGIN PRIVATE KEY-----/g, "")
    .replace(/-----END PRIVATE KEY-----/g, "")
    .replace(/\s+/g, "");

  const binaryString = atob(cleanPem);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }

  return await crypto.subtle.importKey(
    "pkcs8",
    bytes.buffer,
    {
      name: "RSASSA-PKCS1-v1_5",
      hash: "SHA-256"
    },
    false,
    ["sign"]
  );
}

/**
 * Parses Service Account config from environment variables
 */
export function getServiceAccountConfig(env) {
  const rawKey = env.FIREBASE_SERVICE_ACCOUNT_KEY;
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

/**
 * Obtains a valid Google OAuth2 Bearer Access Token using Service Account JWT
 */
export async function getGoogleOAuth2AccessToken(env) {
  const now = Math.floor(Date.now() / 1000);

  // Return cached token if valid for at least 5 more minutes
  if (cachedToken && tokenExpiresAt > now + 300) {
    return cachedToken;
  }

  const serviceAccount = getServiceAccountConfig(env);
  if (!serviceAccount || !serviceAccount.client_email || !serviceAccount.private_key) {
    throw new Error(
      "Missing or invalid FIREBASE_SERVICE_ACCOUNT_KEY in Cloudflare environment. " +
      "Configure it in Cloudflare Pages -> Settings -> Environment Variables."
    );
  }

  const header = {
    alg: "RS256",
    typ: "JWT"
  };

  const scopes = [
    "https://www.googleapis.com/auth/firebase.database",
    "https://www.googleapis.com/auth/devstorage.full_control"
  ].join(" ");

  const claims = {
    iss: serviceAccount.client_email,
    scope: scopes,
    aud: serviceAccount.token_uri || "https://oauth2.googleapis.com/token",
    exp: now + 3600,
    iat: now
  };

  const encodedHeader = base64UrlEncode(JSON.stringify(header));
  const encodedClaims = base64UrlEncode(JSON.stringify(claims));
  const unsignedToken = `${encodedHeader}.${encodedClaims}`;

  // Sign with RSA-SHA256
  const cryptoKey = await importPrivateKey(serviceAccount.private_key);
  const signatureBuffer = await crypto.subtle.sign(
    { name: "RSASSA-PKCS1-v1_5" },
    cryptoKey,
    new TextEncoder().encode(unsignedToken)
  );

  const encodedSignature = base64UrlEncode(signatureBuffer);
  const jwtAssertion = `${unsignedToken}.${encodedSignature}`;

  // Exchange JWT for OAuth2 Token
  const tokenUrl = serviceAccount.token_uri || "https://oauth2.googleapis.com/token";
  const body = new URLSearchParams({
    grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
    assertion: jwtAssertion
  });

  const resp = await fetch(tokenUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body: body.toString()
  });

  if (!resp.ok) {
    const errorText = await resp.text();
    throw new Error(`Google OAuth2 token exchange failed (HTTP ${resp.status}): ${errorText}`);
  }

  const tokenData = await resp.json();
  cachedToken = tokenData.access_token;
  tokenExpiresAt = now + (tokenData.expires_in || 3600);

  return cachedToken;
}
