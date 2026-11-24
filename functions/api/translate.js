/**
 * Cloudflare Pages Function: POST /api/translate
 * Secure Edge Proxy for OpenAI Translation Engine
 * Supports GPT-4o-mini with robust fallback chain (gpt-4o, gpt-3.5-turbo)
 * and dual authentication (Cloudflare Secret OPENAI_API_KEY or Client Request Key).
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

  const apiKey = clientApiKey || env.OPENAI_API_KEY || env.GEMINI_API_KEY;

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
      note: "No OpenAI API key provided. Configure OPENAI_API_KEY in Cloudflare Pages Settings or enter key in dashboard.",
      translations: results
    }), {
      headers: { "Content-Type": "application/json" }
    });
  }

  // Use OpenAI API with active model fallback chain
  const candidateModels = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-3.5-turbo"
  ];

  let lastError = null;
  let successfulModel = null;
  let transMap = null;

  const systemPrompt = `You are an expert mobile localization engine for the EthOS research platform.
Translate the following English UI strings into ${language_name} (${target_locale}).

Strict Rules:
1. Preserve all ICU format string placeholders exactly as they appear (e.g. {count}, {completed}, {total}, {timestamp}, {version}, %1$s, %@).
2. Do NOT translate proper nouns and brand names: 'EthOS'.
3. Keep translations concise, natural, and accurate for mobile UI buttons, banners, and labels.
4. Return ONLY a valid JSON object matching this schema:
{
  "translations": {
    "<key>": "<translated_text>"
  }
}`;

  for (const model of candidateModels) {
    try {
      const resp = await fetch("https://api.openai.com/v1/chat/completions", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${apiKey}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: model,
          messages: [
            { role: "system", content: systemPrompt },
            { role: "user", content: `Strings to translate:\n${JSON.stringify(texts, null, 2)}` }
          ],
          response_format: { type: "json_object" },
          temperature: 0.1
        })
      });

      if (!resp.ok) {
        const errBody = await resp.text();
        lastError = new Error(`${model} returned HTTP ${resp.status}: ${errBody}`);
        // If 404 (model not found) or 429 (rate limit), try next candidate model
        if (resp.status === 404 || resp.status === 429) {
          continue;
        }
        // For fatal errors (401 Unauthorized - invalid key), fail fast
        if (resp.status === 401) {
          throw lastError;
        }
        throw lastError;
      }

      const data = await resp.json();
      const content = data.choices?.[0]?.message?.content;
      if (!content) {
        throw new Error(`Empty content returned by ${model}`);
      }

      let cleaned = content.trim();
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
      if (lastError.message.includes("401") || lastError.message.includes("Incorrect API key")) {
        break; // Stop immediately if key is invalid
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
  console.warn("All OpenAI models failed, falling back to offline generator:", lastError?.message);
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
