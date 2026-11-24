/**
 * Node.js Unit Tests for Option B (Pure Firebase Authentication)
 * Tests:
 * 1. getFirebaseIdToken parameter validation and error reporting
 * 2. getFirebaseIdToken REST API token acquisition and memory caching
 * 3. getFirebaseIdToken error handling for invalid credentials
 * 4. updateManifest locale format validation
 * 5. updateManifest REST URL formatting with ?auth= and PUT method
 * 6. Health check configuration reporting
 */

import test from "node:test";
import assert from "node:assert";
import { getFirebaseIdToken, _resetTokenCache } from "../functions/api/utils/firebase-auth.js";
import { updateManifest } from "../functions/api/deploy.js";
import { onRequestGet as healthOnRequestGet } from "../functions/api/health.js";
import { onRequestPost as translateOnRequestPost } from "../functions/api/translate.js";

test("getFirebaseIdToken - Missing credentials validation", async () => {
  _resetTokenCache();

  // Test empty env
  await assert.rejects(
    async () => {
      await getFirebaseIdToken({});
    },
    {
      message: /Missing required Firebase Auth credentials/
    }
  );

  // Test partial env
  await assert.rejects(
    async () => {
      await getFirebaseIdToken({ FIREBASE_API_KEY: "AIzaTestKey" });
    },
    {
      message: /FIREBASE_PUBLISHER_EMAIL/
    }
  );
});

test("getFirebaseIdToken - Successful token acquisition and caching", async () => {
  _resetTokenCache();

  const originalFetch = globalThis.fetch;
  let fetchCallCount = 0;
  let requestedUrl = "";
  let requestBody = null;

  globalThis.fetch = async (url, options) => {
    fetchCallCount++;
    requestedUrl = url.toString();
    requestBody = JSON.parse(options.body);

    return new Response(
      JSON.stringify({
        idToken: "mock-id-token-abc-123",
        refreshToken: "mock-refresh-token",
        expiresIn: "3600",
        localId: "mock-user-uid"
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  };

  try {
    const env = {
      FIREBASE_API_KEY: "test-api-key",
      FIREBASE_PUBLISHER_EMAIL: "localization-publisher@ethosapp.com",
      FIREBASE_PUBLISHER_PASSWORD: "secret-password"
    };

    // First call: should fetch token
    const token1 = await getFirebaseIdToken(env);
    assert.strictEqual(token1, "mock-id-token-abc-123");
    assert.strictEqual(fetchCallCount, 1);
    assert.ok(requestedUrl.includes("identitytoolkit.googleapis.com"));
    assert.ok(requestedUrl.includes("key=test-api-key"));
    assert.strictEqual(requestBody.email, "localization-publisher@ethosapp.com");
    assert.strictEqual(requestBody.password, "secret-password");
    assert.strictEqual(requestBody.returnSecureToken, true);

    // Second call: should return cached token without additional fetch
    const token2 = await getFirebaseIdToken(env);
    assert.strictEqual(token2, "mock-id-token-abc-123");
    assert.strictEqual(fetchCallCount, 1, "Cached token should not trigger a second fetch call");

  } finally {
    globalThis.fetch = originalFetch;
    _resetTokenCache();
  }
});

test("getFirebaseIdToken - Authentication failure handling", async () => {
  _resetTokenCache();

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    return new Response(
      JSON.stringify({
        error: {
          code: 400,
          message: "EMAIL_NOT_FOUND"
        }
      }),
      { status: 400, headers: { "Content-Type": "application/json" } }
    );
  };

  try {
    const env = {
      FIREBASE_API_KEY: "test-api-key",
      FIREBASE_PUBLISHER_EMAIL: "nonexistent@ethosapp.com",
      FIREBASE_PUBLISHER_PASSWORD: "wrong-password"
    };

    await assert.rejects(
      async () => {
        await getFirebaseIdToken(env);
      },
      {
        message: /Firebase publisher authentication failed \(HTTP 400\): EMAIL_NOT_FOUND/
      }
    );
  } finally {
    globalThis.fetch = originalFetch;
    _resetTokenCache();
  }
});

test("updateManifest - Locale validation", async () => {
  const env = {
    FIREBASE_DATABASE_URL: "https://test-rtdb.firebaseio.com",
    FIREBASE_API_KEY: "test-key",
    FIREBASE_PUBLISHER_EMAIL: "user@test.com",
    FIREBASE_PUBLISHER_PASSWORD: "pwd"
  };

  // Invalid locales
  await assert.rejects(
    async () => {
      await updateManifest(env, "../invalid", {});
    },
    { message: /Invalid locale format/ }
  );

  await assert.rejects(
    async () => {
      await updateManifest(env, "english_123", {});
    },
    { message: /Invalid locale format/ }
  );
});

test("updateManifest - REST PUT with auth query parameter", async () => {
  _resetTokenCache();

  const originalFetch = globalThis.fetch;
  let rtdbPutUrl = "";
  let rtdbMethod = "";
  let rtdbHeaders = {};
  let rtdbBody = null;

  globalThis.fetch = async (url, options) => {
    const urlStr = url.toString();
    if (urlStr.includes("identitytoolkit.googleapis.com")) {
      return new Response(
        JSON.stringify({ idToken: "mock-rtdb-token-xyz", expiresIn: "3600" }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    if (urlStr.includes("test-rtdb.firebaseio.com")) {
      rtdbPutUrl = urlStr;
      rtdbMethod = options.method;
      rtdbHeaders = options.headers;
      rtdbBody = JSON.parse(options.body);

      return new Response(
        JSON.stringify({ success: true, locale: "es" }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    throw new Error(`Unexpected fetch URL: ${urlStr}`);
  };

  try {
    const env = {
      FIREBASE_DATABASE_URL: "https://test-rtdb.firebaseio.com",
      FIREBASE_API_KEY: "test-api-key",
      FIREBASE_PUBLISHER_EMAIL: "publisher@ethosapp.com",
      FIREBASE_PUBLISHER_PASSWORD: "secret-password"
    };

    const manifestEntry = {
      locale: "es",
      version: "1.0.0",
      checksum: "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    };

    const res = await updateManifest(env, "es", manifestEntry);
    assert.strictEqual(res.success, true);
    assert.strictEqual(rtdbMethod, "PUT");
    assert.strictEqual(rtdbHeaders["Content-Type"], "application/json");
    assert.strictEqual(rtdbBody.locale, "es");
    assert.strictEqual(rtdbBody.version, "1.0.0");

    // Verify URL contains /localization/locales/es.json and ?auth=mock-rtdb-token-xyz
    assert.ok(rtdbPutUrl.includes("/localization/locales/es.json"));
    assert.ok(rtdbPutUrl.includes("auth=mock-rtdb-token-xyz"));

  } finally {
    globalThis.fetch = originalFetch;
    _resetTokenCache();
  }
});

test("health endpoint - Configuration reporting for Option B", async () => {
  const envWithAuth = {
    FIREBASE_API_KEY: "AIzaTestKey",
    FIREBASE_PUBLISHER_EMAIL: "publisher@ethosapp.com",
    FIREBASE_PUBLISHER_PASSWORD: "pwd",
    FIREBASE_DATABASE_URL: "https://sample-rtdb.firebaseio.com",
    FIREBASE_STORAGE_BUCKET: "sample-bucket.appspot.com",
    OPENAI_API_KEY: "sk-openai-key",
    GEMINI_API_KEY: "gemini-key"
  };

  const resp = await healthOnRequestGet({ env: envWithAuth });
  const data = await resp.json();

  assert.strictEqual(data.status, "ok");
  assert.strictEqual(data.config.auth_mode, "pure_firebase_id_token");
  assert.strictEqual(data.config.has_firebase_auth, true);
  assert.strictEqual(data.config.publisher_email, "publisher@ethosapp.com");
  assert.strictEqual(data.config.has_service_account, false);
  assert.strictEqual(data.config.has_openai_key, true);
  assert.strictEqual(data.config.has_gemini_key, true);
});

test("translate endpoint - Offline fallback when no key is set", async () => {
  const req = new Request("https://sample.pages.dev/api/translate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      texts: { "btn.save": "Save Changes" },
      target_locale: "es",
      language_name: "Spanish"
    })
  });

  const resp = await translateOnRequestPost({ request: req, env: {} });
  const data = await resp.json();

  assert.strictEqual(resp.status, 200);
  assert.strictEqual(data.success, true);
  assert.strictEqual(data.engine, "OFFLINE_FALLBACK");
  assert.strictEqual(data.translations["btn.save"].text, "[ES] Save Changes");
});

test("translate endpoint - OpenAI API request formatting and JSON response", async () => {
  const originalFetch = globalThis.fetch;
  let capturedUrl = "";
  let capturedHeaders = {};
  let capturedBody = null;

  globalThis.fetch = async (url, options) => {
    capturedUrl = url.toString();
    capturedHeaders = options.headers;
    capturedBody = JSON.parse(options.body);

    return new Response(
      JSON.stringify({
        choices: [
          {
            message: {
              content: JSON.stringify({
                translations: {
                  "btn.save": "Guardar cambios"
                }
              })
            }
          }
        ]
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  };

  try {
    const req = new Request("https://sample.pages.dev/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        texts: { "btn.save": "Save Changes" },
        target_locale: "es",
        language_name: "Spanish"
      })
    });

    const env = { OPENAI_API_KEY: "sk-test-openai-secret" };
    const resp = await translateOnRequestPost({ request: req, env: env });
    const data = await resp.json();

    assert.strictEqual(resp.status, 200);
    assert.strictEqual(data.success, true);
    assert.strictEqual(data.engine, "gpt-4o-mini");
    assert.strictEqual(data.translations["btn.save"].text, "Guardar cambios");
    assert.strictEqual(data.translations["btn.save"].type, "GPT_4O_MINI");

    // Verify OpenAI API call properties
    assert.strictEqual(capturedUrl, "https://api.openai.com/v1/chat/completions");
    assert.strictEqual(capturedHeaders["Authorization"], "Bearer sk-test-openai-secret");
    assert.strictEqual(capturedBody.model, "gpt-4o-mini");
    assert.deepStrictEqual(capturedBody.response_format, { type: "json_object" });

  } finally {
    globalThis.fetch = originalFetch;
  }
});
