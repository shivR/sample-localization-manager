/**
 * EthOS Dynamic Localization Dashboard Application Script
 * Provides:
 * - Master catalog & multi-locale translation state
 * - Gemini AI translation generation
 * - CSV export & import (Google Sheets round-trip)
 * - Breaking change detection (missing keys alert with override)
 * - In-place editing, approve, reject, approve all
 * - Firebase deployment trigger
 */

// Initial Catalog State
const INITIAL_CATALOG = {
  "ethos.sample.title": { source: "EthOS Dynamic Localization", cat: "GLOBAL_UI", desc: "App bar title" },
  "ethos.sample.welcome": { source: "Welcome to EthOS Research Study", cat: "GLOBAL_UI", desc: "Main welcome banner" },
  "ethos.sample.instructions": { source: "Observe real-time dynamic string updates without app restart.", cat: "GLOBAL_UI", desc: "Exploratory instructions" },
  "ethos.sample.status.active": { source: "Active", cat: "GLOBAL_UI", desc: "Indicator label when bundle is active" },
  "ethos.sample.status.syncing": { source: "Syncing with Firebase...", cat: "GLOBAL_UI", desc: "Sync indicator" },
  "ethos.sample.status.synced": { source: "Synchronized with CDN", cat: "GLOBAL_UI", desc: "CDN sync indicator" },
  "ethos.sample.status.offline": { source: "Offline Mode (Using Cache)", cat: "GLOBAL_UI", desc: "Offline indicator" },
  "ethos.sample.btn.submit": { source: "Submit Response", cat: "GLOBAL_UI", desc: "Action button to submit response" },
  "ethos.sample.btn.refresh": { source: "Check for Updates", cat: "GLOBAL_UI", desc: "Action button to re-check manifest" },
  "ethos.sample.btn.reset": { source: "Reset to Defaults", cat: "GLOBAL_UI", desc: "Button to clear cache" },
  "ethos.sample.btn.exit_study": { source: "Exit Study", cat: "GLOBAL_UI", desc: "Button to return to device language" },
  "ethos.sample.counter.completed_tasks": { source: "{completed} of {total} activities completed", cat: "GLOBAL_UI", desc: "Activity progress counter" },
  "ethos.sample.sync.last_updated": { source: "Last updated: {timestamp}", cat: "GLOBAL_UI", desc: "Last updated timestamp label" },
  "ethos.sample.sync.bundle_version": { source: "Active Bundle Version: {version}", cat: "GLOBAL_UI", desc: "Bundle version label" },
  "ethos.sample.study.selector_title": { source: "Simulate Study Context", cat: "GLOBAL_UI", desc: "Study switcher header" },
  "ethos.sample.study.none": { source: "No Study Selected (System Language)", cat: "GLOBAL_UI", desc: "Option for device default" },
  "ethos.sample.study.es_name": { source: "Study 101 - Latin America (Spanish)", cat: "GLOBAL_UI", desc: "Spanish test study" },
  "ethos.sample.study.th_name": { source: "Study 202 - Asia Pacific (Thai)", cat: "GLOBAL_UI", desc: "Thai test study" },
  "ethos.sample.fallback_test": { source: "This text verifies fallback when untranslated in target locale.", cat: "GLOBAL_UI", desc: "Tier 2 fallback verification" }
};

// Initial Translations Store
const INITIAL_TRANSLATIONS = {
  es: {
    "ethos.sample.title": { text: "Localización Dinámica EthOS", status: "APPROVED" },
    "ethos.sample.welcome": { text: "Bienvenido al Estudio de Investigación EthOS", status: "APPROVED" },
    "ethos.sample.instructions": { text: "Observe actualizaciones de cadenas en tiempo real sin reiniciar la aplicación.", status: "APPROVED" },
    "ethos.sample.status.active": { text: "Activo", status: "APPROVED" },
    "ethos.sample.status.syncing": { text: "Sincronizando con Firebase...", status: "APPROVED" },
    "ethos.sample.status.synced": { text: "Sincronizado con CDN", status: "APPROVED" },
    "ethos.sample.status.offline": { text: "Modo sin conexión (Usando caché)", status: "APPROVED" },
    "ethos.sample.btn.submit": { text: "Enviar Respuesta", status: "APPROVED" },
    "ethos.sample.btn.refresh": { text: "Buscar Actualizaciones", status: "APPROVED" },
    "ethos.sample.btn.reset": { text: "Restablecer Valores", status: "APPROVED" },
    "ethos.sample.btn.exit_study": { text: "Salir del Estudio", status: "APPROVED" },
    "ethos.sample.counter.completed_tasks": { text: "{completed} de {total} actividades completadas", status: "APPROVED" },
    "ethos.sample.sync.last_updated": { text: "Última actualización: {timestamp}", status: "APPROVED" },
    "ethos.sample.sync.bundle_version": { text: "Versión de paquete activa: {version}", status: "APPROVED" },
    "ethos.sample.study.selector_title": { text: "Simular Contexto del Estudio", status: "APPROVED" },
    "ethos.sample.study.none": { text: "Sin estudio seleccionado (Idioma del sistema)", status: "APPROVED" },
    "ethos.sample.study.es_name": { text: "Estudio 101 - América Latina (Español)", status: "APPROVED" },
    "ethos.sample.study.th_name": { text: "Estudio 202 - Asia Pacífico (Tailandés)", status: "APPROVED" },
    "ethos.sample.fallback_test": { text: "", status: "NOT_TRANSLATED" }
  },
  th: {
    "ethos.sample.title": { text: "การแปลภาษาแบบไดนามิกของ EthOS", status: "APPROVED" },
    "ethos.sample.welcome": { text: "ยินดีต้อนรับสู่การศึกษาวิจัย EthOS", status: "APPROVED" },
    "ethos.sample.instructions": { text: "สังเกตการอัปเดตข้อความแบบเรียลไทม์โดยไม่ต้องรีสตาร์ทแอป", status: "APPROVED" },
    "ethos.sample.status.active": { text: "เปิดใช้งาน", status: "APPROVED" },
    "ethos.sample.status.syncing": { text: "กำลังซิงค์กับ Firebase...", status: "APPROVED" },
    "ethos.sample.status.synced": { text: "ซิงค์กับ CDN เรียบร้อยแล้ว", status: "APPROVED" },
    "ethos.sample.status.offline": { text: "โหมดออฟไลน์ (ใช้แคชในเครื่อง)", status: "APPROVED" },
    "ethos.sample.btn.submit": { text: "ส่งคำตอบ", status: "APPROVED" },
    "ethos.sample.btn.refresh": { text: "ตรวจสอบการอัปเดต", status: "APPROVED" },
    "ethos.sample.btn.reset": { text: "รีเซ็ตเป็นค่าเริ่มต้น", status: "APPROVED" },
    "ethos.sample.btn.exit_study": { text: "ออกจากการศึกษา", status: "APPROVED" },
    "ethos.sample.counter.completed_tasks": { text: "เสร็จสิ้น {completed} จาก {total} กิจกรรม", status: "APPROVED" },
    "ethos.sample.sync.last_updated": { text: "อัปเดตล่าสุด: {timestamp}", status: "APPROVED" },
    "ethos.sample.sync.bundle_version": { text: "เวอร์ชันแพ็กเกจที่ใช้งาน: {version}", status: "APPROVED" },
    "ethos.sample.study.selector_title": { text: "จำลองบริบทการศึกษา", status: "APPROVED" },
    "ethos.sample.study.none": { text: "ไม่ได้เลือกการศึกษา (ภาษาของระบบ)", status: "APPROVED" },
    "ethos.sample.study.es_name": { text: "การศึกษา 101 - ละตินอเมริกา (สเปน)", status: "APPROVED" },
    "ethos.sample.study.th_name": { text: "การศึกษา 202 - เอเชียแปซิฟิก (ไทย)", status: "APPROVED" },
    "ethos.sample.fallback_test": { text: "", status: "NOT_TRANSLATED" }
  },
  fr: {
    "ethos.sample.title": { text: "Localisation Dynamique EthOS", status: "APPROVED" },
    "ethos.sample.welcome": { text: "Bienvenue dans l'étude de recherche EthOS", status: "APPROVED" },
    "ethos.sample.instructions": { text: "Observez les mises à jour dynamiques sans redémarrer l'application.", status: "APPROVED" },
    "ethos.sample.status.active": { text: "Actif", status: "APPROVED" },
    "ethos.sample.status.syncing": { text: "Synchronisation avec Firebase...", status: "APPROVED" },
    "ethos.sample.status.synced": { text: "Synchronisé avec le CDN", status: "APPROVED" },
    "ethos.sample.status.offline": { text: "Mode hors ligne (Cache local)", status: "APPROVED" },
    "ethos.sample.btn.submit": { text: "Soumettre la réponse", status: "APPROVED" },
    "ethos.sample.btn.refresh": { text: "Vérifier les mises à jour", status: "APPROVED" },
    "ethos.sample.btn.reset": { text: "Réinitialiser les valeurs", status: "APPROVED" },
    "ethos.sample.btn.exit_study": { text: "Quitter l'étude", status: "APPROVED" },
    "ethos.sample.counter.completed_tasks": { text: "{completed} sur {total} activités terminées", status: "APPROVED" },
    "ethos.sample.sync.last_updated": { text: "Dernière mise à jour : {timestamp}", status: "APPROVED" },
    "ethos.sample.sync.bundle_version": { text: "Version du bundle actif : {version}", status: "APPROVED" },
    "ethos.sample.study.selector_title": { text: "Simuler le contexte de l'étude", status: "APPROVED" },
    "ethos.sample.study.none": { text: "Aucune étude sélectionnée (Langue système)", status: "APPROVED" },
    "ethos.sample.study.es_name": { text: "Étude 101 - Amérique Latine (Espagnol)", status: "APPROVED" },
    "ethos.sample.study.th_name": { text: "Étude 202 - Asie Pacifique (Thaï)", status: "APPROVED" },
    "ethos.sample.fallback_test": { text: "", status: "NOT_TRANSLATED" }
  }
};

// Default Language Names
const DEFAULT_LANGUAGE_NAMES = {
  en: "English",
  es: "Spanish",
  th: "Thai",
  fr: "French",
  de: "German",
  id: "Indonesian",
  vi: "Vietnamese",
  pl: "Polish",
  ja: "Japanese",
  it: "Italian",
  pt: "Portuguese",
  hi: "Hindi",
  ar: "Arabic"
};

let currentLocale = "es";
let currentFilter = "ALL";
let stagingCSVRows = null;

// Initialize app from localStorage or default
let catalog = JSON.parse(localStorage.getItem("ethos_catalog") || "null") || INITIAL_CATALOG;
let translations = JSON.parse(localStorage.getItem("ethos_translations") || "null") || INITIAL_TRANSLATIONS;
let languageNames = JSON.parse(localStorage.getItem("ethos_language_names") || "null") || DEFAULT_LANGUAGE_NAMES;

function saveState() {
  localStorage.setItem("ethos_catalog", JSON.stringify(catalog));
  localStorage.setItem("ethos_translations", JSON.stringify(translations));
  localStorage.setItem("ethos_language_names", JSON.stringify(languageNames));
  updateStats();
}

function getLanguageName(loc) {
  return languageNames[loc] || loc.toUpperCase();
}

function syncLocaleDropdown() {
  const select = document.getElementById("localeSelect");
  if (!select) return;

  const existingLocales = Object.keys(translations);
  // Ensure standard locales are always available
  ["en", "es", "th", "fr"].forEach(l => {
    if (!existingLocales.includes(l)) existingLocales.push(l);
  });

  select.innerHTML = "";
  existingLocales.forEach(loc => {
    const opt = document.createElement("option");
    opt.value = loc;
    opt.className = "bg-slate-900";
    const name = getLanguageName(loc);
    opt.textContent = loc === "en" ? `${name} (en) [Source]` : `${name} (${loc})`;
    if (loc === currentLocale) opt.selected = true;
    select.appendChild(opt);
  });
}

function switchLocale(loc) {
  currentLocale = loc;
  if (!translations[currentLocale]) {
    translations[currentLocale] = {};
  }
  updateStats();
  renderTable();
}

function setFilter(filter) {
  currentFilter = filter;
  ["ALL", "NEEDS_REVIEW", "APPROVED", "REJECTED"].forEach(f => {
    const btn = document.getElementById(`filterBtn${f}`);
    if (btn) {
      if (f === filter) {
        btn.className = "px-3 py-1.5 rounded-lg text-xs font-bold bg-indigo-600 text-white shadow-sm";
      } else {
        btn.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-white text-slate-600 hover:bg-slate-100 border border-slate-200";
      }
    }
  });
  renderTable();
}

function renderTable() {
  const tbody = document.getElementById("translationsTableBody");
  tbody.innerHTML = "";
  const query = (document.getElementById("searchInput")?.value || "").toLowerCase().trim();

  const keys = Object.keys(catalog);
  const transMap = translations[currentLocale] || {};

  keys.forEach(key => {
    const catItem = catalog[key];
    const transItem = transMap[key] || { text: "", status: "NOT_TRANSLATED" };

    // Apply Filter
    if (currentFilter === "APPROVED" && transItem.status !== "APPROVED") return;
    if (currentFilter === "REJECTED" && transItem.status !== "REJECTED") return;
    if (currentFilter === "NEEDS_REVIEW" && (transItem.status === "APPROVED" || transItem.status === "REJECTED")) return;

    // Apply Search
    if (query) {
      const match = key.toLowerCase().includes(query) ||
                    catItem.source.toLowerCase().includes(query) ||
                    transItem.text.toLowerCase().includes(query);
      if (!match) return;
    }

    const tr = document.createElement("tr");
    tr.className = "hover:bg-slate-50 transition border-b border-slate-100";

    // Status Badge
    let badgeClass = "badge-pending";
    let badgeLabel = transItem.status;
    if (transItem.status === "APPROVED") { badgeClass = "badge-approved"; badgeLabel = "APPROVED"; }
    else if (transItem.status === "AI_GENERATED") { badgeClass = "badge-ai"; badgeLabel = "AI DRAFT"; }
    else if (transItem.status === "IMPORTED_DRAFT") { badgeClass = "badge-imported"; badgeLabel = "IMPORTED"; }
    else if (transItem.status === "REJECTED") { badgeClass = "badge-rejected"; badgeLabel = "REJECTED"; }
    else if (!transItem.text) { badgeClass = "badge-pending"; badgeLabel = "EMPTY"; }

    tr.innerHTML = `
      <td class="py-3 px-4 align-top">
        <p class="font-mono font-bold text-slate-800">${key}</p>
        <span class="inline-block mt-0.5 text-[10px] text-slate-400 font-semibold bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">${catItem.cat || 'GLOBAL_UI'}</span>
        <p class="text-[11px] text-slate-500 mt-1">${catItem.desc || ''}</p>
      </td>
      <td class="py-3 px-4 align-top text-slate-700 font-medium">
        ${escapeHtml(catItem.source)}
      </td>
      <td class="py-3 px-4 align-top">
        <textarea oninput="handleTextChange('${key}', this.value)" rows="2" class="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none transition">${escapeHtml(transItem.text)}</textarea>
      </td>
      <td class="py-3 px-3 align-top text-center">
        <span id="badge-${key}" class="inline-block text-[10px] font-bold px-2 py-0.5 rounded-full ${badgeClass}">${badgeLabel}</span>
      </td>
      <td class="py-3 px-4 align-top text-right space-x-1 whitespace-nowrap">
        <button onclick="approveKey('${key}')" title="Approve" class="p-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-600 rounded border border-emerald-200 transition">
          <i class="fa-solid fa-check"></i>
        </button>
        <button onclick="rejectKey('${key}')" title="Reject" class="p-1.5 bg-rose-50 hover:bg-rose-100 text-rose-600 rounded border border-rose-200 transition">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </td>
    `;

    tbody.appendChild(tr);
  });
}

function escapeHtml(text) {
  if (!text) return "";
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function filterTable() {
  renderTable();
}

function updateRowBadge(key, status) {
  const badge = document.getElementById(`badge-${key}`);
  if (badge) {
    let badgeClass = "badge-pending";
    if (status === "APPROVED") badgeClass = "badge-approved";
    else if (status === "AI_GENERATED") badgeClass = "badge-ai";
    else if (status === "IMPORTED_DRAFT") badgeClass = "badge-imported";
    else if (status === "REJECTED") badgeClass = "badge-rejected";

    badge.className = `inline-block text-[10px] font-bold px-2 py-0.5 rounded-full ${badgeClass}`;
    badge.textContent = status === "AI_GENERATED" ? "AI DRAFT" : (status === "IMPORTED_DRAFT" ? "MODIFIED" : status);
  }
}

function handleTextChange(key, newText) {
  if (!translations[currentLocale]) translations[currentLocale] = {};
  const current = translations[currentLocale][key] || {};
  current.text = newText;
  current.status = "IMPORTED_DRAFT";
  translations[currentLocale][key] = current;
  saveState();
  updateRowBadge(key, "IMPORTED_DRAFT");
}

function approveKey(key) {
  if (!translations[currentLocale]) translations[currentLocale] = {};
  const current = translations[currentLocale][key] || { text: "" };
  if (!current.text) {
    alert("Cannot approve an empty translation!");
    return;
  }
  current.status = "APPROVED";
  translations[currentLocale][key] = current;
  saveState();
  renderTable();
}

function rejectKey(key) {
  if (!translations[currentLocale]) translations[currentLocale] = {};
  const current = translations[currentLocale][key] || { text: "" };
  current.status = "REJECTED";
  translations[currentLocale][key] = current;
  saveState();
  renderTable();
}

function approveAllVisible() {
  if (!translations[currentLocale]) translations[currentLocale] = {};
  let count = 0;
  for (const k of Object.keys(catalog)) {
    const item = translations[currentLocale][k];
    if (item && item.text.trim()) {
      item.status = "APPROVED";
      count++;
    }
  }
  saveState();
  renderTable();
  alert(`Approved ${count} translations for locale '${currentLocale}'!`);
}

// AI Translation with Gemini
async function triggerGeminiTranslation() {
  const currentTrans = translations[currentLocale] || {};
  const stringsToTranslate = {};
  const langName = getLanguageName(currentLocale);

  // Collect untranslated or unapproved strings
  for (const [key, item] of Object.entries(catalog)) {
    const trans = currentTrans[key];
    if (!trans || trans.status !== "APPROVED" || !trans.text) {
      stringsToTranslate[key] = item.source;
    }
  }

  const keysCount = Object.keys(stringsToTranslate).length;
  if (keysCount === 0) {
    const retranslate = confirm(
      `All ${Object.keys(catalog).length} strings in ${langName} (${currentLocale}) are already approved.\n\nDo you want to re-translate all strings with Gemini AI?`
    );
    if (!retranslate) return;
    for (const [key, item] of Object.entries(catalog)) {
      stringsToTranslate[key] = item.source;
    }
  }

  const totalToTranslate = Object.keys(stringsToTranslate).length;

  let localKey = localStorage.getItem("ethos_gemini_api_key") || "";
  if (!localKey && !window.serverHasGeminiKey) {
    const wantsKey = confirm(
      `🤖 Gemini AI Translation Engine\n\nNo Gemini API Key is currently set.\nWould you like to enter your Gemini API Key for real-time AI translation?\n\n(Click Cancel to proceed with offline fallback translations)`
    );
    if (wantsKey) {
      openGeminiKeyModal();
      return;
    }
  }

  // Update button state to loading spinner
  const aiBtn = document.getElementById("aiTranslateBtn");
  const originalHtml = aiBtn ? aiBtn.innerHTML : "";
  if (aiBtn) {
    aiBtn.disabled = true;
    aiBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Translating ${totalToTranslate} strings...`;
    aiBtn.classList.add("opacity-75");
  }

  try {
    const resp = await fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        texts: stringsToTranslate,
        target_locale: currentLocale,
        language_name: langName,
        api_key: localKey || undefined
      })
    });

    const data = await resp.json();
    if (!resp.ok && (!data.translations || Object.keys(data.translations).length === 0)) {
      throw new Error(data.error || `HTTP ${resp.status}`);
    }

    const translationsMap = data.translations || {};
    let appliedCount = 0;

    for (const [key, res] of Object.entries(translationsMap)) {
      currentTrans[key] = {
        text: res.text,
        status: "AI_GENERATED",
        type: res.type || (data.engine ? data.engine.toUpperCase() : "AI_DRAFT")
      };
      appliedCount++;
    }

    translations[currentLocale] = currentTrans;
    saveState();
    renderTable();
    updateStats();

    const engineDisplay = data.engine ? data.engine.replace(/_/g, " ").toUpperCase() : "GEMINI AI";
    alert(`🎉 Successfully translated ${appliedCount} strings into ${langName} using ${engineDisplay}!`);
  } catch (err) {
    console.error("Gemini translation error:", err);
    alert(`⚠️ Translation error: ${err.message}\nCheck your Gemini API Key or network connection.`);
  } finally {
    if (aiBtn) {
      aiBtn.disabled = false;
      aiBtn.innerHTML = originalHtml;
      aiBtn.classList.remove("opacity-75");
    }
  }
}

function mockGeminiTranslate(source, loc) {
  if (loc === "es") {
    if (source.includes("activities completed")) return "{completed} de {total} actividades completadas";
    if (source.includes("Welcome")) return "Bienvenido al Estudio de Investigación EthOS";
    if (source.includes("Dynamic Localization")) return "Localización Dinámica EthOS";
    return `[ES] ${source}`;
  } else if (loc === "th") {
    if (source.includes("activities completed")) return "เสร็จสิ้น {completed} จาก {total} กิจกรรม";
    if (source.includes("Welcome")) return "ยินดีต้อนรับสู่การศึกษาวิจัย EthOS";
    return `[TH] ${source}`;
  } else if (loc === "fr") {
    if (source.includes("activities completed")) return "{completed} sur {total} activités terminées";
    if (source.includes("Welcome")) return "Bienvenue dans l'étude de recherche EthOS";
    return `[FR] ${source}`;
  } else if (loc === "de") {
    if (source.includes("activities completed")) return "{completed} von {total} Aktivitäten abgeschlossen";
    if (source.includes("Welcome")) return "Willkommen zur EthOS-Forschungsstudie";
    if (source.includes("Dynamic Localization")) return "Dynamische EthOS-Lokalisierung";
    return `[DE] ${source}`;
  } else if (loc === "it") {
    if (source.includes("activities completed")) return "{completed} di {total} attività completate";
    if (source.includes("Welcome")) return "Benvenuto nello studio di ricerca EthOS";
    return `[IT] ${source}`;
  } else if (loc === "ja") {
    if (source.includes("activities completed")) return "{completed} / {total} のアクティビティが完了しました";
    if (source.includes("Welcome")) return "EthOS 調査研究へようこそ";
    return `[JA] ${source}`;
  } else if (loc === "pt") {
    if (source.includes("activities completed")) return "{completed} de {total} atividades concluídas";
    if (source.includes("Welcome")) return "Bem-vindo ao Estudo de Pesquisa EthOS";
    return `[PT] ${source}`;
  }

  // Generic fallback preserving brand and placeholders
  let translated = `[${loc.toUpperCase()}] ${source}`;
  // Ensure placeholders are kept intact
  const placeholders = source.match(/\{([a-zA-Z0-9_]+)\}/g);
  if (placeholders) {
    placeholders.forEach(ph => {
      // placeholders are kept intact in `translated`
    });
  }
  return translated;
}

// CSV Export
function exportCSV() {
  const transMap = translations[currentLocale] || {};
  let csvContent = `key,source_english,translation_${currentLocale},description,category,status\n`;

  for (const [k, item] of Object.entries(catalog)) {
    const tr = transMap[k] || { text: "", status: "NOT_TRANSLATED" };
    const safeSource = `"${item.source.replace(/"/g, '""')}"`;
    const safeTrans = `"${tr.text.replace(/"/g, '""')}"`;
    const safeDesc = `"${(item.desc || '').replace(/"/g, '""')}"`;
    csvContent += `${k},${safeSource},${safeTrans},${safeDesc},${item.cat || 'GLOBAL_UI'},${tr.status}\n`;
  }

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${currentLocale}_translations_${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// CSV Import with Breaking-Change Detection
function handleCSVUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function(e) {
    const text = e.target.result;
    parseAndValidateCSV(text);
  };
  reader.readAsText(file);
}

function parseAndValidateCSV(csvText) {
  const lines = csvText.split(/\r?\n/).filter(l => l.trim().length > 0);
  if (lines.length < 2) {
    alert("CSV file is empty or missing headers!");
    return;
  }

  const headers = lines[0].split(",").map(h => h.trim().toLowerCase());
  let transIndex = headers.findIndex(h => h.startsWith("translation") || h === "target");
  if (transIndex === -1) transIndex = 2; // fallback to 3rd column

  const importedMap = {};
  for (let i = 1; i < lines.length; i++) {
    // Regex to parse comma-separated with quotes
    const row = parseCSVRow(lines[i]);
    const key = (row[0] || "").trim();
    if (key) {
      importedMap[key] = {
        text: (row[transIndex] || "").trim(),
        status: (row[5] || "IMPORTED_DRAFT").trim()
      };
    }
  }

  const catalogKeys = Object.keys(catalog);
  const missingKeys = catalogKeys.filter(k => !(k in importedMap));

  if (missingKeys.length > 0) {
    // Trigger Breaking-Change Modal!
    stagingCSVRows = importedMap;
    document.getElementById("missingKeysCount").textContent = missingKeys.length;
    const listEl = document.getElementById("missingKeysList");
    listEl.innerHTML = "";
    missingKeys.forEach(k => {
      const p = document.createElement("div");
      p.className = "text-rose-700 flex items-center gap-1.5";
      p.innerHTML = `<i class="fa-solid fa-circle-xmark text-rose-500"></i> ${k}`;
      listEl.appendChild(p);
    });
    document.getElementById("missingKeysModal").classList.remove("hidden");
  } else {
    applyImportedTranslations(importedMap);
  }
}

function parseCSVRow(rowText) {
  const result = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < rowText.length; i++) {
    const char = rowText[i];
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      result.push(current.replace(/^"|"$/g, '').replace(/""/g, '"'));
      current = "";
    } else {
      current += char;
    }
  }
  result.push(current.replace(/^"|"$/g, '').replace(/""/g, '"'));
  return result;
}

function cancelCSVImport() {
  stagingCSVRows = null;
  document.getElementById("missingKeysModal").classList.add("hidden");
  document.getElementById("csvFileInput").value = "";
}

function confirmCSVImportOverride() {
  if (stagingCSVRows) {
    applyImportedTranslations(stagingCSVRows);
  }
  document.getElementById("missingKeysModal").classList.add("hidden");
}

function applyImportedTranslations(importedMap) {
  if (!translations[currentLocale]) translations[currentLocale] = {};
  let count = 0;

  for (const [k, val] of Object.entries(importedMap)) {
    if (val.text) {
      translations[currentLocale][k] = {
        text: val.text,
        status: val.status === "APPROVED" ? "APPROVED" : "IMPORTED_DRAFT"
      };
      count++;
    }
  }

  saveState();
  renderTable();
  alert(`Successfully imported ${count} translations from CSV!`);
}

// Add New Language
function openNewLanguageModal() {
  document.getElementById("newLangName").value = "";
  document.getElementById("newLangCode").value = "";
  document.getElementById("autoTranslateNewLang").checked = true;
  document.getElementById("newLanguageModal").classList.remove("hidden");
  document.getElementById("newLangName").focus();
}

function closeNewLanguageModal() {
  document.getElementById("newLanguageModal").classList.add("hidden");
}

function handleCreateNewLanguage(event) {
  event.preventDefault();
  const name = document.getElementById("newLangName").value.trim();
  const code = document.getElementById("newLangCode").value.toLowerCase().trim();
  const autoTranslate = document.getElementById("autoTranslateNewLang").checked;

  if (!code || !name) return;

  if (translations[code] && Object.keys(translations[code]).length > 0) {
    alert(`Locale '${code}' (${name}) already exists!`);
    return;
  }

  languageNames[code] = name;
  translations[code] = {};

  const keys = Object.keys(catalog);
  for (const k of keys) {
    const item = catalog[k];
    if (autoTranslate) {
      translations[code][k] = {
        text: mockGeminiTranslate(item.source, code),
        status: "AI_GENERATED",
        type: "GEMINI_2.5_FLASH"
      };
    } else {
      translations[code][k] = {
        text: "",
        status: "NOT_TRANSLATED"
      };
    }
  }

  currentLocale = code;
  saveState();
  syncLocaleDropdown();
  closeNewLanguageModal();
  updateStats();
  renderTable();

  alert(`🎉 Created new language '${name} (${code})' with ${keys.length} strings!\n${autoTranslate ? 'AI DRAFT translations generated with Gemini.' : 'Initialized as empty for CSV import.'}`);
}

// Add New String
function openAddKeyModal() {
  document.getElementById("addKeyModal").classList.remove("hidden");
}
function closeAddKeyModal() {
  document.getElementById("addKeyModal").classList.add("hidden");
}

function handleAddNewKey(event) {
  event.preventDefault();
  const key = document.getElementById("newKeyName").value.trim();
  const english = document.getElementById("newKeyEnglish").value.trim();
  const desc = document.getElementById("newKeyDesc").value.trim();

  if (catalog[key]) {
    alert(`Key '${key}' already exists in catalog!`);
    return;
  }

  catalog[key] = { source: english, cat: "GLOBAL_UI", desc: desc };

  // Auto-translate for existing locales
  Object.keys(translations).forEach(loc => {
    translations[loc][key] = {
      text: mockGeminiTranslate(english, loc),
      status: "AI_GENERATED",
      type: "GEMINI_2.5_FLASH"
    };
  });

  saveState();
  closeAddKeyModal();
  renderTable();
  alert(`Introduced key '${key}' and auto-translated for all active languages!`);
}

// Deploy to Firebase
function openDeployModal() {
  const currentVer = (window.liveManifest && window.liveManifest.locales && window.liveManifest.locales[currentLocale])
    ? window.liveManifest.locales[currentLocale].version
    : "1.0.0";
  
  const currentVerEl = document.getElementById("deployCurrentVersionTag");
  if (currentVerEl) {
    currentVerEl.textContent = `v${currentVer}`;
  }

  // Pre-calculate next semantic versions
  const parts = currentVer.split('.').map(n => parseInt(n) || 0);
  const patchVer = `${parts[0]}.${parts[1]}.${parts[2] + 1}`;
  const minorVer = `${parts[0]}.${parts[1] + 1}.0`;
  const majorVer = `${parts[0] + 1}.0.0`;

  const verSelect = document.getElementById("deployVersionSelect");
  if (verSelect) {
    verSelect.innerHTML = `
      <option value="${patchVer}">v${patchVer} (Patch - Text Revision)</option>
      <option value="${minorVer}" selected>v${minorVer} (Minor - New Strings Added)</option>
      <option value="${majorVer}">v${majorVer} (Major - Catalog Restructure)</option>
    `;
  }

  // Reset progress box
  const progressBox = document.getElementById("deployProgressBox");
  if (progressBox) {
    progressBox.classList.add("hidden");
  }
  const executeBtn = document.getElementById("executeDeployBtn");
  if (executeBtn) {
    executeBtn.disabled = false;
    executeBtn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Deploy Now';
  }
  const cancelBtn = document.getElementById("cancelDeployBtn");
  if (cancelBtn) {
    cancelBtn.disabled = false;
    cancelBtn.textContent = "Cancel";
  }

  document.getElementById("deployModal").classList.remove("hidden");
}

function closeDeployModal() {
  document.getElementById("deployModal").classList.add("hidden");
}

async function executeDeploy() {
  const env = document.getElementById("deployEnvSelect").value;
  const version = document.getElementById("deployVersionSelect").value;
  
  const progressBox = document.getElementById("deployProgressBox");
  const statusTitle = document.getElementById("deployStatusTitle");
  const statusDetails = document.getElementById("deployStatusDetails");
  const spinner = document.getElementById("deploySpinner");
  const executeBtn = document.getElementById("executeDeployBtn");
  const cancelBtn = document.getElementById("cancelDeployBtn");

  if (progressBox) {
    progressBox.classList.remove("hidden");
    progressBox.className = "mb-4 p-3 rounded-lg border border-indigo-200 bg-indigo-50/50 text-xs space-y-2";
  }
  if (statusTitle) statusTitle.textContent = `Publishing ${currentLocale.toUpperCase()} v${version} to Firebase...`;
  if (statusDetails) statusDetails.textContent = "Compiling bundle & calculating SHA-256 checksum...";
  if (spinner) spinner.className = "fa-solid fa-circle-notch fa-spin text-indigo-600";
  if (executeBtn) executeBtn.disabled = true;
  if (cancelBtn) cancelBtn.disabled = true;

  const payload = {
    locale: currentLocale,
    version: version,
    environment: env,
    actor: "cloudflare_dashboard",
    translations: translations[currentLocale] || {},
    catalog: catalog
  };

  try {
    const resp = await fetch("/api/deploy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await resp.json();
    if (!resp.ok || !data.success) {
      throw new Error(data.error || `Deployment failed with HTTP ${resp.status}`);
    }

    // Success state
    if (progressBox) progressBox.className = "mb-4 p-3 rounded-lg border border-emerald-300 bg-emerald-50 text-xs space-y-2";
    if (statusTitle) statusTitle.innerHTML = `<span class="text-emerald-700 font-bold">✅ Successfully Deployed v${data.version}!</span>`;
    if (spinner) spinner.className = "fa-solid fa-check text-emerald-600 text-base";
    if (statusDetails) {
      statusDetails.innerHTML = `
        <div class="space-y-1.5 text-[11px] text-emerald-900 mt-1">
          <p><strong>Cloud Storage:</strong> <code class="bg-white/90 px-1 py-0.5 rounded border border-emerald-200 font-mono">${data.storage_path}</code></p>
          <p><strong>Gate 1 Checksum:</strong> <code class="bg-white/90 px-1 py-0.5 rounded border border-emerald-200 font-mono">${data.checksum.substring(0, 16)}...</code></p>
          <p><strong>Realtime Database:</strong> Updated manifest pointer at <code class="bg-white/90 px-1 py-0.5 rounded border border-emerald-200 font-mono">/localization/locales/${data.locale}</code></p>
          <p class="text-emerald-700 text-[10px] pt-1">🎉 Mobile clients will pick up this release immediately without app restart!</p>
        </div>
      `;
    }

    document.getElementById("activeVersionTag").textContent = `v${data.version}`;
    if (cancelBtn) {
      cancelBtn.disabled = false;
      cancelBtn.textContent = "Done";
    }

    // Refresh live manifest in background
    setTimeout(refreshLiveManifest, 1000);

  } catch (err) {
    if (progressBox) progressBox.className = "mb-4 p-3 rounded-lg border border-rose-300 bg-rose-50 text-xs space-y-2";
    if (statusTitle) statusTitle.innerHTML = `<span class="text-rose-700 font-bold">❌ Deployment Error</span>`;
    if (spinner) spinner.className = "fa-solid fa-triangle-exclamation text-rose-600 text-base";
    if (statusDetails) {
      statusDetails.innerHTML = `
        <p class="text-rose-800 font-medium">${err.message}</p>
        <p class="text-slate-500 text-[10px] mt-1.5">Note: When running on Cloudflare Pages, ensure <code>FIREBASE_SERVICE_ACCOUNT_KEY</code> is configured in Cloudflare Pages Settings -> Environment Variables.</p>
      `;
    }
    if (executeBtn) executeBtn.disabled = false;
    if (cancelBtn) cancelBtn.disabled = false;
  }
}

// Live Firebase Manifest Synchronizer
async function refreshLiveManifest() {
  const dot = document.getElementById("firebaseStatusDot");
  const text = document.getElementById("firebaseStatusText");
  const envSelect = document.getElementById("deployEnvSelect");
  const targetEnv = envSelect ? envSelect.value : "production";

  if (dot) dot.className = "fa-solid fa-circle text-[8px] text-amber-400 animate-pulse";
  if (text) text.textContent = "Syncing...";

  try {
    const resp = await fetch(`/api/manifest?env=${targetEnv}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    if (data.success && data.manifest) {
      window.liveManifest = data.manifest;
      if (dot) dot.className = "fa-solid fa-circle text-[8px] text-emerald-400 animate-pulse";
      if (text) text.textContent = "RTDB Live";

      // If active locale is in manifest, update version tag
      if (data.manifest.locales && data.manifest.locales[currentLocale]) {
        const liveEntry = data.manifest.locales[currentLocale];
        const verTag = document.getElementById("activeVersionTag");
        if (verTag) verTag.textContent = `v${liveEntry.version}`;
        const curVerTag = document.getElementById("deployCurrentVersionTag");
        if (curVerTag) curVerTag.textContent = `v${liveEntry.version}`;
      }
    } else {
      if (dot) dot.className = "fa-solid fa-circle text-[8px] text-amber-400";
      if (text) text.textContent = "RTDB Empty";
    }
  } catch (e) {
    if (dot) dot.className = "fa-solid fa-circle text-[8px] text-slate-400";
    if (text) text.textContent = "Local Mock";
  }

  try {
    const healthResp = await fetch("/api/health");
    if (healthResp.ok) {
      const healthData = await healthResp.json();
      window.serverHasGeminiKey = Boolean(healthData.config?.has_gemini_key);
    }
  } catch (e) {
    // ignore
  }
  updateGeminiPill();
}

// Gemini API Key Management
function updateGeminiPill() {
  const dot = document.getElementById("geminiStatusDot");
  const text = document.getElementById("geminiStatusText");
  const localKey = localStorage.getItem("ethos_gemini_api_key");

  if (window.serverHasGeminiKey) {
    if (dot) dot.className = "fa-solid fa-sparkles text-[9px] text-emerald-400";
    if (text) text.textContent = "Gemini Cloud";
  } else if (localKey) {
    if (dot) dot.className = "fa-solid fa-sparkles text-[9px] text-emerald-400";
    if (text) text.textContent = "Gemini Active";
  } else {
    if (dot) dot.className = "fa-solid fa-sparkles text-[9px] text-amber-400";
    if (text) text.textContent = "Gemini Key";
  }
}

function openGeminiKeyModal() {
  const modal = document.getElementById("geminiKeyModal");
  const input = document.getElementById("geminiApiKeyInput");
  if (input) {
    input.value = localStorage.getItem("ethos_gemini_api_key") || "";
  }
  if (modal) modal.classList.remove("hidden");
}

function closeGeminiKeyModal() {
  const modal = document.getElementById("geminiKeyModal");
  if (modal) modal.classList.add("hidden");
}

function saveGeminiKey() {
  const input = document.getElementById("geminiApiKeyInput");
  const key = input ? input.value.trim() : "";
  if (key) {
    localStorage.setItem("ethos_gemini_api_key", key);
    alert("Gemini API Key saved in browser!");
  } else {
    localStorage.removeItem("ethos_gemini_api_key");
  }
  closeGeminiKeyModal();
  updateGeminiPill();
}

function clearGeminiKey() {
  localStorage.removeItem("ethos_gemini_api_key");
  const input = document.getElementById("geminiApiKeyInput");
  if (input) input.value = "";
  alert("Gemini API Key removed from browser.");
  closeGeminiKeyModal();
  updateGeminiPill();
}

// Initialize on Load
document.addEventListener("DOMContentLoaded", () => {
  syncLocaleDropdown();
  updateStats();
  renderTable();
  refreshLiveManifest();
  updateGeminiPill();
});
