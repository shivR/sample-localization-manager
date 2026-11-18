/**
 * Cloudflare Pages Function: POST /api/translate
 * Secure Edge Proxy for Google Gemini 2.5 Flash translation engine
 */

export async function onRequestPost(context) {
  const env = context.env || {};
  const apiKey = env.GEMINI_API_KEY;

  let body;
  try {
    body = await context.request.json();
  } catch (e) {
    return new Response(JSON.stringify({ success: false, error: "Invalid JSON request" }), {
      status: 400,
      headers: { "Content-Type": "application/json" }
    });
  }

  const { texts = {}, target_locale = "es", language_name = "Spanish" } = body;
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
      translations: results
    }), {
      headers: { "Content-Type": "application/json" }
    });
  }

  // Use Gemini API
  try {
    const prompt = `You are an expert mobile localization engine. Translate the following English UI strings into ${language_name} (${target_locale}).

Strict Rules:
1. Preserve all ICU placeholders exactly as they appear (e.g. {count}, {completed}, {total}, {timestamp}, {version}).
2. Do NOT translate proper nouns and brand names: 'EthOS'.
3. Keep translations concise and natural for mobile UI buttons, banners, and labels.
4. Return ONLY valid JSON in format:
{
  "translations": {
    "<key>": "<translated_text>"
  }
}

Strings to translate:
${JSON.stringify(texts, null, 2)}`;

    const geminiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`;
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
      throw new Error(`Gemini API returned HTTP ${resp.status}`);
    }

    const data = await resp.json();
    const candidateText = data.candidates?.[0]?.content?.parts?.[0]?.text;
    const parsed = JSON.parse(candidateText);
    const transMap = parsed.translations || parsed;

    for (const [k, text] of entries) {
      results[k] = {
        text: transMap[k] || `[${target_locale.toUpperCase()}] ${text}`,
        status: "AI_GENERATED",
        type: "GEMINI_2.5_FLASH"
      };
    }

    return new Response(JSON.stringify({
      success: true,
      locale: target_locale,
      language: language_name,
      engine: "GEMINI_2.5_FLASH",
      translations: results
    }), {
      headers: { "Content-Type": "application/json" }
    });

  } catch (err) {
    console.warn("Gemini API call failed; falling back to offline generator:", err);
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
      error_note: err.message,
      translations: results
    }), {
      headers: { "Content-Type": "application/json" }
    });
  }
}
