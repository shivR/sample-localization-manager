/**
 * Cloudflare Pages Function: POST /api/translate
 * Secure Edge Proxy for Google Gemini translation engine
 * Supports Gemini 2.5 Flash with fallback chain (2.0 Flash, 1.5 Flash)
 * and dual authentication (Cloudflare Secret GEMINI_API_KEY or Client Request Key)
 */

export async function onRequestPost(context) {
  const env = context.env || {};

  let body;
  try {
    body = await context.request.json();
  } catch (e) {
    return new Response(JSON.stringify({ success: false, error: "Invalid JSON request" }), {
      status: 400,
      headers: { "Content-Type": "application/json" }
    });
  }

  const {
    texts = {},
    target_locale = "es",
    language_name = "Spanish",
    api_key: clientApiKey
  } = body;

  const apiKey = clientApiKey || env.GEMINI_API_KEY;

  const entries = Object.entries(texts);
  if (entries.length === 0) {
    return new Response(JSON.stringify({ success: true, translations: {} }), {
      headers: { "Content-Type": "application/json" }
    });
  }

  const results = {};

  if (!apiKey) {
    // Offline deterministic mock fallback preserving brand & placeholders
    for (const [k, text] of entries) {
      results[k] = {
        text: `[${target_locale.toUpperCase()}] ${text}`,
        status: "AI_GENERATED",
        type: "OFFLINE_FALLBACK"
      };
    }

    return new Response(JSON.stringify({
      success: true,
      locale: target_locale,
      language: language_name,
      engine: "OFFLINE_FALLBACK",
      note: "No Gemini API key provided. Configure GEMINI_API_KEY in Cloudflare Pages Settings or enter key in dashboard.",
      translations: results
    }), {
      headers: { "Content-Type": "application/json" }
    });
  }

  // Use Gemini API with candidate model fallback chain
  const candidateModels = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"];
  let lastError = null;
  let successfulModel = null;
  let transMap = null;

  const prompt = `You are an expert mobile localization engine. Translate the following English UI strings into ${language_name} (${target_locale}).

Strict Rules:
1. Preserve all ICU placeholders exactly as they appear (e.g. {count}, {completed}, {total}, {timestamp}, {version}).
2. Do NOT translate proper nouns and brand names: 'EthOS'.
3. Keep translations concise, natural, and accurate for mobile UI buttons, banners, and labels.
4. Return ONLY a valid JSON object matching this schema:
{
  "translations": {
    "<key>": "<translated_text>"
  }
}

Strings to translate:
${JSON.stringify(texts, null, 2)}`;

  for (const model of candidateModels) {
    try {
      const geminiUrl = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(apiKey)}`;
      const resp = await fetch(geminiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: {
            temperature: 0.1,
            responseMimeType: "application/json"
          }
        })
      });

      if (!resp.ok) {
        const errBody = await resp.text();
        lastError = new Error(`${model} returned HTTP ${resp.status}: ${errBody}`);
        // If 404 (model not found/available on this project), try next candidate
        if (resp.status === 404) {
          continue;
        }
        // For fatal errors (400, 403 API key invalid), stop and fail
        throw lastError;
      }

      const data = await resp.json();
      const candidateText = data.candidates?.[0]?.content?.parts?.[0]?.text;
      if (!candidateText) {
        throw new Error(`Empty content returned by ${model}`);
      }

      let cleaned = candidateText.trim();
      if (cleaned.startsWith("```")) {
        cleaned = cleaned.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "").trim();
      }

      const parsed = JSON.parse(cleaned);
      transMap = parsed.translations || parsed;
      successfulModel = model;
      break;
    } catch (e) {
      lastError = e;
      console.warn(`Translation attempt with ${model} failed:`, e.message);
      if (lastError.message.includes("403") || lastError.message.includes("API key not valid")) {
        break; // Invalid API key won't work on other models
      }
    }
  }

  if (transMap && successfulModel) {
    for (const [k, text] of entries) {
      results[k] = {
        text: transMap[k] || `[${target_locale.toUpperCase()}] ${text}`,
        status: "AI_GENERATED",
        type: successfulModel.toUpperCase().replace(/[-.]/g, "_")
      };
    }

    return new Response(JSON.stringify({
      success: true,
      locale: target_locale,
      language: language_name,
      engine: successfulModel,
      translations: results
    }), {
      headers: { "Content-Type": "application/json" }
    });
  }

  // Fallback to offline generator if all failed
  console.warn("All Gemini models failed, falling back to offline generator:", lastError?.message);
  for (const [k, text] of entries) {
    results[k] = {
      text: `[${target_locale.toUpperCase()}] ${text}`,
      status: "AI_GENERATED",
      type: "OFFLINE_FALLBACK"
    };
  }

  return new Response(JSON.stringify({
    success: false,
    error: lastError ? lastError.message : "Translation service unavailable",
    engine: "OFFLINE_FALLBACK",
    locale: target_locale,
    translations: results
  }), {
    status: 502,
    headers: { "Content-Type": "application/json" }
  });
}
