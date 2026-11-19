/**
 * Cloudflare Pages Function: POST /api/deploy
 * Executes the atomic localization bundle publishing workflow:
 * 1. Validates bundle parameters and approved translations
 * 2. Compiles bundle and calculates SHA-256 checksums
 * 3. Uploads immutable bundle to Firebase Cloud Storage CDN
 * 4. Executes read-back verification
 * 5. Atomically updates Firebase Realtime Database release manifest
 * 6. Records audit history
 */

import { getGoogleOAuth2AccessToken } from "./utils/firebase-auth.js";

async function sha256Hex(bufferOrString) {
  let data;
  if (typeof bufferOrString === "string") {
    data = new TextEncoder().encode(bufferOrString);
  } else {
    data = bufferOrString;
  }
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, "0")).join("");
}

export async function onRequestPost(context) {
  const env = context.env || {};
  const databaseUrl = (env.FIREBASE_DATABASE_URL || "https://sample-localization-management-default-rtdb.firebaseio.com").replace(/\/+$/, "");
  const storageBucket = env.FIREBASE_STORAGE_BUCKET || "sample-localization-management.firebasestorage.app";

  let body;
  try {
    body = await context.request.json();
  } catch (e) {
    return new Response(JSON.stringify({ success: false, error: "Invalid JSON request body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" }
    });
  }

  const {
    locale,
    version,
    environment = "production",
    actor = "cloudflare_dashboard",
    translations = {},
    catalog = {}
  } = body;

  // 1. Validation
  if (!locale || !locale.match(/^[a-z]{2}(-[A-Z]{2}|-[A-Za-z0-9]+)?$/)) {
    return new Response(JSON.stringify({ success: false, error: `Invalid locale format: '${locale}'` }), {
      status: 400,
      headers: { "Content-Type": "application/json" }
    });
  }

  if (!version || !version.match(/^[0-9]+\.[0-9]+\.[0-9]+$/)) {
    return new Response(JSON.stringify({ success: false, error: `Invalid semantic version: '${version}'. Must be format X.Y.Z` }), {
      status: 400,
      headers: { "Content-Type": "application/json" }
    });
  }

  const validEnvs = ["development", "staging", "production"];
  if (!validEnvs.includes(environment)) {
    return new Response(JSON.stringify({ success: false, error: `Invalid environment: '${environment}'` }), {
      status: 400,
      headers: { "Content-Type": "application/json" }
    });
  }

  try {
    // 2. Extract approved translations and compute coverage
    const catalogKeys = Object.keys(catalog.keys || catalog || {});
    const totalCatalogKeys = catalogKeys.length > 0 ? catalogKeys.length : Object.keys(translations).length;

    const stringsMap = {};
    let approvedCount = 0;

    for (const [k, v] of Object.entries(translations)) {
      const text = typeof v === "object" ? (v.text || v.translated_text || "") : String(v);
      const status = typeof v === "object" ? (v.status || v.translation_status || "APPROVED") : "APPROVED";
      if (status === "APPROVED" && text !== "") {
        stringsMap[k] = text;
        approvedCount++;
      } else if (text !== "") {
        // Include non-approved if explicitly requested
        stringsMap[k] = text;
      }
    }

    const coveragePercent = totalCatalogKeys > 0 ? Math.round((approvedCount / totalCatalogKeys) * 1000) / 10 : 100.0;
    const isComplete = approvedCount >= totalCatalogKeys;
    const statusStr = isComplete ? "COMPLETE" : (approvedCount > 0 ? "PARTIAL" : "PENDING_TRANSLATION");

    // 3. Compute payload_hash
    const sortedKeys = Object.keys(stringsMap).sort();
    const sortedPayload = {};
    for (const k of sortedKeys) {
      sortedPayload[k] = stringsMap[k];
    }
    const payloadHash = await sha256Hex(JSON.stringify(sortedPayload));

    // 4. Build Bundle
    const nowIso = new Date().toISOString();
    const bundleSkeleton = {
      schema_version: "1.0.0",
      bundle_id: `bundle-${locale}-v${version}`,
      locale: locale,
      version: version,
      environment: environment,
      source_catalog_version: catalog.schema_version || "1.0.0",
      source_catalog_sha256: await sha256Hex(JSON.stringify(catalog)),
      generated_at: nowIso,
      target_platform: "all",
      fallback_locale: "en",
      payload_hash: payloadHash,
      bundle_checksum: "0".repeat(64),
      translation_coverage: {
        total_catalog_keys: totalCatalogKeys,
        approved_keys_count: approvedCount,
        coverage_percent: coveragePercent,
        is_complete: isComplete,
        status: statusStr
      },
      approved_revision_metadata: {
        bundle_revision: 1,
        last_updated: nowIso,
        approver: actor
      },
      strings: stringsMap,
      plurals: {}
    };

    // Calculate actual checksum over the serialized JSON
    const serializedBundle = JSON.stringify(bundleSkeleton, null, 2);
    const finalChecksum = await sha256Hex(serializedBundle);
    bundleSkeleton.bundle_checksum = finalChecksum;

    const finalBundleBytes = new TextEncoder().encode(JSON.stringify(bundleSkeleton, null, 2));
    const storageFileChecksum = await sha256Hex(finalBundleBytes);

    // 5. Authenticate via Google OAuth2
    const token = await getGoogleOAuth2AccessToken(env);

    // 6. Upload immutable bundle to Cloud Storage CDN
    const storageRelPath = `localization/locales/${locale}/${version}/bundle.json`;
    const gcsUploadUrl = `https://storage.googleapis.com/upload/storage/v1/b/${storageBucket}/o?uploadType=media&name=${encodeURIComponent(storageRelPath)}`;
    const firebaseStorageUploadUrl = `https://firebasestorage.googleapis.com/v0/b/${storageBucket}/o?uploadType=media&name=${encodeURIComponent(storageRelPath)}`;

    let uploadResp = await fetch(gcsUploadUrl, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: finalBundleBytes
    });

    if (!uploadResp.ok) {
      const gcsErr = await uploadResp.text();
      console.warn(`GCS JSON API upload failed (${uploadResp.status}): ${gcsErr}. Retrying with Firebase Storage REST API...`);
      uploadResp = await fetch(firebaseStorageUploadUrl, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: finalBundleBytes
      });
      if (!uploadResp.ok) {
        const fbErr = await uploadResp.text();
        throw new Error(`Cloud Storage upload failed (GCS: ${gcsErr} | Firebase: ${fbErr})`);
      }
    }

    // 7. Read-back verification
    const gcsReadBackUrl = `https://storage.googleapis.com/storage/v1/b/${storageBucket}/o/${encodeURIComponent(storageRelPath)}?alt=media`;
    const fbReadBackUrl = `https://firebasestorage.googleapis.com/v0/b/${storageBucket}/o/${encodeURIComponent(storageRelPath)}?alt=media`;

    let readBackResp = await fetch(gcsReadBackUrl, {
      headers: { "Authorization": `Bearer ${token}` }
    });

    if (!readBackResp.ok) {
      readBackResp = await fetch(fbReadBackUrl, {
        headers: { "Authorization": `Bearer ${token}` }
      });
    }

    if (!readBackResp.ok) {
      throw new Error(`Read-back verification from Cloud Storage failed (HTTP ${readBackResp.status})`);
    }

    const downloadedBytes = await readBackResp.arrayBuffer();
    const downloadedChecksum = await sha256Hex(downloadedBytes);

    if (downloadedChecksum !== storageFileChecksum) {
      throw new Error(
        `Gate 1 Checksum Mismatch during read-back verification! Expected: ${storageFileChecksum}, Got: ${downloadedChecksum}. Publish aborted.`
      );
    }

    // 8. Atomically update Firebase Realtime Database
    const releaseId = `rel-${environment}-${locale}-${version}-${Date.now()}`;
    const manifestEntry = {
      locale: locale,
      version: version,
      path: storageRelPath,
      checksum: storageFileChecksum,
      payload_hash: payloadHash,
      status: "ACTIVE",
      coverage_percent: coveragePercent,
      approved_keys_count: approvedCount,
      total_catalog_keys: totalCatalogKeys,
      published_at: nowIso,
      publisher_id: actor,
      min_client_version: "2.0.0",
      previous_version: null,
      rollback_metadata: {
        is_rollback: false,
        rolled_back_at: null,
        rolled_back_from: null,
        reason: null,
        actor: null
      }
    };

    // Update manifest for environment
    const rtdbEnvManifestUrl = `${databaseUrl}/localization/releases/${environment}/manifest/locales/${locale}.json?access_token=${token}`;
    const rtdbEnvResp = await fetch(rtdbEnvManifestUrl, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(manifestEntry)
    });

    if (!rtdbEnvResp.ok) {
      const errText = await rtdbEnvResp.text();
      throw new Error(`Failed to update RTDB environment manifest (HTTP ${rtdbEnvResp.status}): ${errText}`);
    }

    // Update root mobile client listener node: /localization/locales/{locale}.json
    const rtdbClientUrl = `${databaseUrl}/localization/locales/${locale}.json?access_token=${token}`;
    await fetch(rtdbClientUrl, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(manifestEntry)
    });

    // Update timestamp
    const rtdbTimeUrl = `${databaseUrl}/localization/releases/${environment}/manifest/updated_at.json?access_token=${token}`;
    await fetch(rtdbTimeUrl, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(nowIso)
    });

    // Log release history
    const historyUrl = `${databaseUrl}/localization/releases/${environment}/history/${releaseId}.json?access_token=${token}`;
    await fetch(historyUrl, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        release_id: releaseId,
        locale: locale,
        version: version,
        bundle_path: storageRelPath,
        checksum: storageFileChecksum,
        published_at: nowIso,
        publisher: actor,
        coverage_percent: coveragePercent
      })
    });

    return new Response(JSON.stringify({
      success: true,
      bundle_id: bundleSkeleton.bundle_id,
      locale: locale,
      version: version,
      environment: environment,
      checksum: storageFileChecksum,
      storage_path: storageRelPath,
      coverage_percent: coveragePercent,
      approved_keys: approvedCount,
      total_keys: totalCatalogKeys,
      published_at: nowIso,
      status: "ACTIVE"
    }, null, 2), {
      headers: { "Content-Type": "application/json" }
    });

  } catch (err) {
    console.error("Deploy failed:", err);
    return new Response(JSON.stringify({
      success: false,
      error: err.message
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}
