# EthOS Production Dynamic Localization Implementation Manual

This manual provides the complete, step-by-step instructions to integrate the proven dynamic localization architecture into the three production EthOS repositories:
1. **`ethos-localization`** (Central Governance, Publishing & CDN Distribution)
2. **`iosv2`** (Production iOS Application)
3. **`androidv2`** (Production Android Application)

---

# Table of Contents
1. [Core Architectural Contract & Invariants](#1-core-architectural-contract--invariants)
2. [Project 1: Central Repository (`ethos-localization`)](#2-project-1-central-repository-ethos-localization)
   - [2.1 Catalog & Content Segregation](#21-catalog--content-segregation)
   - [2.2 Exporting Native Fallback Resources](#22-exporting-native-fallback-resources)
   - [2.3 Atomic Publishing Sequence to Firebase](#23-atomic-publishing-sequence-to-firebase)
   - [2.4 Emergency Rollback Execution](#24-emergency-rollback-execution)
   - [2.5 Firebase Security Rules Deployment](#25-firebase-security-rules-deployment)
3. [Project 2: Production iOS Application (`iosv2`)](#3-project-2-production-ios-application-iosv2)
   - [3.1 Native Fallback Strings Placement](#31-native-fallback-strings-placement)
   - [3.2 Adding Core Localization Engine Files](#32-adding-core-localization-engine-files)
   - [3.3 Connecting Startup in AppDelegate](#33-connecting-startup-in-appdelegate)
   - [3.4 Connecting Study / Project Context Switching](#34-connecting-study--project-context-switching)
   - [3.5 Call Site Migration & Bridging](#35-call-site-migration--bridging)
   - [3.6 Live View Refresh via NotificationCenter](#36-live-view-refresh-via-notificationcenter)
   - [3.7 Removing MMLocalization Dependency & Swizzling](#37-removing-mmlocalization-dependency--swizzling)
   - [3.8 iOS Verification Checklist](#38-ios-verification-checklist)
4. [Project 3: Production Android Application (`androidv2`)](#4-project-3-production-android-application-androidv2)
   - [4.1 Native Fallback Strings Placement](#41-native-fallback-strings-placement)
   - [4.2 Adding Core Localization Engine Files](#42-adding-core-localization-engine-files)
   - [4.3 Connecting Startup in EthosApplication](#43-connecting-startup-in-ethosapplication)
   - [4.4 Connecting Study / Project Context Switching](#44-connecting-study--project-context-switching)
   - [4.5 Bridging LocaleHelper & R.string Lookups](#45-bridging-localehelper--rstring-lookups)
   - [4.6 Eliminating Disruptive Activity Recreation](#46-eliminating-disruptive-activity-recreation)
   - [4.7 Android Verification Checklist](#47-android-verification-checklist)
5. [End-to-End Release & Verification Runbook](#5-end-to-end-release--verification-runbook)

---

# 1. Core Architectural Contract & Invariants

Before touching any production code, adhere strictly to these core architectural rules:

1. **Git is the Sole Authoring Authority**:
   - Translations are **never** authored or edited directly in Firebase.
   - All modifications originate in `ethos-localization` via audited human review.
2. **Delivery-Only Firebase**:
   - Firebase Realtime Database (`/localization`) acts strictly as a lightweight version/checksum manifest pointer.
   - Cloud Storage (`localization/locales/{locale}/{version}/bundle.json`) acts as an edge distribution CDN serving immutable JSON bundles.
3. **Mobile Clients are Read-Only Consumers**:
   - Mobile apps receive zero administrative, publishing, or service account credentials.
   - Client access requires `auth != null` (participant session token or App Check).
4. **0ms Cold Boot Guarantee**:
   - Apps must render instantly upon launch using Tier 3 native compile-time strings (`Localizable.strings` / `strings.xml`) or local disk cache. Network requests must **never** block the main/UI thread.
5. **The 3-Tier Fallback Hierarchy**:
   - **Tier 1**: Active remote locale bundle from memory cache.
   - **Tier 2**: Versioned remote English bundle from memory cache.
   - **Tier 3**: Native embedded bundle (`Localizable.strings` / `strings.xml`).
   - **Terminal Fallback**: Canonical English default text. **Raw semantic keys (`auth.btn.sign_in`) must NEVER be shown to end users under any failure condition.**
6. **The Dual-Gate Verification**:
   - **Gate 1 (Checksum)**: Compute SHA-256 over raw downloaded bytes. If it does not match `manifest.checksum`, abort immediately and delete the downloaded file.
   - **Gate 2 (Schema)**: Validate JSON structure against `published-bundle.schema.json`. Only after both gates pass does the client perform an atomic in-memory swap.
7. **Dynamic Language Resolution State Machine**:
   - **Pre-Project / Global Context**: App UI language strictly matches the **device/system language** (falling back to English `en` if unsupported).
   - **Study Context**: Entering a study/project immediately activates the **project's configured UI language** (`project.language`).
   - **Study Exit**: Navigating back to the project list or logging out immediately reverts the UI to the **device/system language**.

---

# 2. Project 1: Central Repository (`ethos-localization`)

All localization management operations are driven from `ethos-localization`.

### 2.1 Catalog & Content Segregation
The master catalog resides at `catalog/master-catalog.json`. EthOS strictly segregates 4 content classifications:
- **`GLOBAL_UI` (509 keys)**: Packaged into dynamic Firebase releases and native fallback bundles.
- **`RESEARCHER_CONTENT` (80 keys)**: Segregated in `translation-store/researcher-content/catalog.json`. Distributed per-study via the Study Survey API. Never packaged into global UI bundles.
- **`RUNTIME_PARAMETER` (11 keys)**: Interpolated dynamically by client code.
- **`TECHNICAL` (4 keys)**: Hardcoded identifiers for developer logging only.

### 2.2 Exporting Native Fallback Resources
Whenever new keys are approved or translations updated, compile-time fallback strings must be exported into the mobile repositories:

```bash
cd /Users/shivvaishnav/Documents/Projects/ethos/ethos-localization

# Export fallback resources to both iOS and Android simultaneously:
python3 scripts/publish/export_native_fallbacks.py --platform all --output-dir exports/native

# Or export directly into production mobile project directories:
python3 scripts/publish/export_native_fallbacks.py --platform ios --output-dir ../iosv2
python3 scripts/publish/export_native_fallbacks.py --platform android --output-dir ../androidv2
```

This updates:
- iOS: `iosv2/EthOS/Resources/{locale}.lproj/Localizable.strings` (`en`, `es`, `th`, `pl`, `id`, `vi`)
- Android: `androidv2/app/src/main/res/values-{qualifier}/strings.xml` (`values`, `values-es`, `values-th`, `values-pl`, `values-id`, `values-vi`)

### 2.3 Atomic Publishing Sequence to Firebase
To publish an updated locale bundle (e.g. `es` version `1.1.0`), run the publisher CLI. It executes the mandatory 10-step atomic publishing protocol:

```bash
cd /Users/shivvaishnav/Documents/Projects/ethos/ethos-localization

# Dry-run check first (validates catalog, schema, placeholders without uploading)
python3 scripts/publish/firebase_publisher.py --locale es --version 1.1.0 --env development --dry-run

# Execute live atomic publication to development:
python3 scripts/publish/firebase_publisher.py --locale es --version 1.1.0 --env development --actor "admin-shiv"

# To publish to staging or production:
python3 scripts/publish/firebase_publisher.py --locale es --version 1.1.0 --env staging --actor "admin-shiv"
python3 scripts/publish/firebase_publisher.py --locale es --version 1.1.0 --env production --actor "admin-shiv"
```

**Publishing Workflow Enforced:**
1. Validates `catalog/master-catalog.json` (SHA-256 and key count).
2. Verifies only `APPROVED` translations are packaged (no AI drafts).
3. Generates deterministic bundle JSON (`bundle-es-v1.1.0`).
4. Validates Draft-07 schema (`schemas/published-bundle.schema.json`).
5. Validates ICU placeholders and printf specifiers against English source text.
6. Computes SHA-256 checksum and payload hash.
7. Uploads immutable bundle to Cloud Storage: `localization/locales/es/1.1.0/bundle.json`.
8. Read-back verification (downloads from Cloud Storage and asserts exact checksum match).
9. Atomically updates Realtime Database manifest at `/localization/locales/es`.
10. Records release metadata to `translation-store/releases/{env}/metadata/` and appends to `releases/history.json`.

### 2.4 Emergency Rollback Execution
If a released version exhibits unexpected linguistic or display defects in production:

```bash
cd /Users/shivvaishnav/Documents/Projects/ethos/ethos-localization

# Roll back locale 'es' from 1.1.0 back to 1.0.0 in production:
python3 scripts/publish/rollback_locale.py \
  --locale es \
  --target-version 1.0.0 \
  --env production \
  --actor "admin-shiv" \
  --reason "Reverting typo in auth screen reported by QA"
```

**Rollback Behavior:**
- Previous storage objects are **never deleted** (immutability preserved).
- The target version bundle (`1.0.0`) is re-verified from Cloud Storage.
- Realtime Database `/localization/locales/es` is atomically updated:
  - `version: "1.0.0"`
  - `checksum: <checksum_of_1.0.0>`
  - `rollback_metadata.is_rollback: true`
  - `rollback_metadata.rolled_back_from: "1.1.0"`
- Connected mobile clients detect the manifest pointer update within seconds and immediately reload `1.0.0` from local disk cache or CDN.

### 2.5 Firebase Security Rules Deployment
Deploy rules to enforce client read-only and publisher-only restrictions:

```bash
cd /Users/shivvaishnav/Documents/Projects/ethos/ethos-localization

# Deploy Realtime Database rules (enforces schema validation on /localization writes)
firebase deploy --only database --project <FIREBASE_PROJECT_ID>

# Deploy Storage rules (enforces immutability: allow create, allow read, allow update: if false, allow delete: if false)
firebase deploy --only storage --project <FIREBASE_PROJECT_ID>
```

---

# 3. Project 2: Production iOS Application (`iosv2`)

Follow these sequential steps in `iosv2`.

### 3.1 Native Fallback Strings Placement
Ensure native fallback `.strings` files exist in the project:
Path: `iosv2/EthOS/Resources/` (or wherever localization files are linked in Xcode)
- `en.lproj/Localizable.strings`
- `es.lproj/Localizable.strings`
- `th.lproj/Localizable.strings`
- `pl.lproj/Localizable.strings`
- `id.lproj/Localizable.strings`
- `vi.lproj/Localizable.strings`

Run `python3 scripts/publish/export_native_fallbacks.py --platform ios --output-dir ../iosv2` to keep them synchronized with the master catalog.

### 3.2 Adding Core Localization Engine Files
Create a new group in Xcode: `EthOS/Core/Localization/` and copy the four verified components:

1. **`EthOSTranslationProvider.swift`**: Defines lookup interface.
2. **`LocalizationModels.swift`**: Codable structs for `LocalizationManifest`, `PublishedBundle`, `ManifestLocaleEntry`, `RollbackMetadata`, and `StudyModel`.
3. **`LanguageResolver.swift`**: Pure static resolver evaluating device locale vs study language context.
4. **`EthOSLocalizationManager.swift`**:
   - Thread-safe singleton using `DispatchQueue(label: "...", attributes: .concurrent)` with barrier writes.
   - Dual-gate validation (`CryptoKit.SHA256` + `PublishedBundle` decoding).
   - Disk caching under `Application Support/EthOSLocalization/`.
   - Manifest listener / background sync querying Firebase Realtime Database at `/localization`.
   - Posts `.ethosLanguageDidChange` notification upon in-memory atomic swap.
5. **`EthOSLocalize.swift`**: Global helper function:
   ```swift
   import Foundation

   public func EthOSLocalize(_ key: String, default defaultText: String? = nil) -> String {
       return EthOSLocalizationManager.shared.string(for: key, default: defaultText)
   }

   public func EthOSLocalize(_ key: String, arguments: [String: Any]) -> String {
       return EthOSLocalizationManager.shared.string(for: key, arguments: arguments)
   }
   ```

### 3.3 Connecting Startup in AppDelegate
Open `iosv2/EthOS/Core/AppDelegate.swift`:

1. Locate `application(_:didFinishLaunchingWithOptions:)`:
   ```swift
   // Replace MMLocalization.start() with:
   EthOSLocalizationManager.shared.loadInitialLocale()
   ```
2. In `applicationDidBecomeActive(_:)` or background sync handler:
   ```swift
   // Trigger non-blocking manifest check against Firebase Realtime Database:
   EthOSLocalizationManager.shared.checkForManifestUpdates()
   ```

### 3.4 Connecting Study / Project Context Switching
Open `iosv2/EthOS/Utilities/EthOSHelper/EthOSHelper.swift`:

1. Locate `loadLanguageFile(for: project)` (around lines 1940-1960):
   ```swift
   // CURRENT LEGACY CODE:
   // MMLocalization.set(type: .custom(tableName: language))

   // REPLACEMENT:
   if let project = project {
       let study = StudyModel(id: project.id ?? "", title: project.name ?? "", languageCode: project.language ?? "en")
       EthOSLocalizationManager.shared.setStudyContext(study)
   } else {
       EthOSLocalizationManager.shared.setStudyContext(nil)
   }
   ```
2. Locate project exit / study deselection / logout methods:
   ```swift
   // When participant leaves a project or logs out:
   EthOSLocalizationManager.shared.setStudyContext(nil)
   ```
   *This immediately reverts the active localization table to the user's operating system device language.*

### 3.5 Call Site Migration & Bridging
To prevent needing to rewrite all 480 call sites at once, add a backwards-compatibility bridge in a global utility file (e.g. `LocalizationHelper.swift`):

```swift
import Foundation

// Backwards-compatible bridge for legacy localString() calls
public func localString(_ key: String) -> String {
    return EthOSLocalizationManager.shared.string(for: key, default: key)
}

// Backwards-compatible bridge for NSLocalizedString
public func EthOSLocalizedString(_ key: String, comment: String = "") -> String {
    return EthOSLocalizationManager.shared.string(for: key, default: key)
}
```

For high-priority views, migrate hardcoded English strings to canonical semantic keys:
```swift
// Old:
titleLabel.text = NSLocalizedString("Login", comment: "")

// New:
titleLabel.text = EthOSLocalize("auth.btn.sign_in", default: "Sign In")
```

### 3.6 Live View Refresh via NotificationCenter
To ensure active ViewControllers update their labels when a hot-update or language change occurs:

In base ViewController (`EthOSBaseViewController.swift`):
```swift
override func viewDidLoad() {
    super.viewDidLoad()
    NotificationCenter.default.addObserver(
        self,
        selector: #selector(handleLanguageDidChange),
        name: .ethosLanguageDidChange,
        object: nil
    )
}

@objc open func handleLanguageDidChange() {
    // Subclasses override to re-bind localized strings:
    // titleLabel.text = EthOSLocalize("dashboard.title")
}
```

### 3.7 Removing MMLocalization Dependency & Swizzling
Once call sites are bridged:
1. Open `iosv2/Podfile`.
2. Remove `pod 'MMLocalization'`.
3. Run `pod install` in `iosv2/`.
4. Delete legacy static files in `EthOS/Files/Localized String File/` (`ILocalizable_EN.strings`, etc.).

### 3.8 iOS Verification Checklist
- [ ] Clean build passes without warnings or missing swizzled methods.
- [ ] App boots offline with 0ms delay showing native fallback strings.
- [ ] Entering a Thai project switches UI to Thai strings immediately.
- [ ] Exiting project reverts UI to system language immediately.
- [ ] Pushing a new version via `firebase_publisher.py` updates in-memory strings without app restart.
- [ ] Triggering a rollback reverts the UI string immediately.
- [ ] Untranslated keys fall back safely to English; raw semantic key is never rendered.

---

# 4. Project 3: Production Android Application (`androidv2`)

Follow these sequential steps in `androidv2`.

### 4.1 Native Fallback Strings Placement
Ensure native fallback XML resources exist in `androidv2/app/src/main/res/`:
- `values/strings.xml` (Canonical English fallback)
- `values-es/strings.xml`
- `values-th/strings.xml`
- `values-pl/strings.xml`
- `values-id/strings.xml`
- `values-vi/strings.xml`

Run `python3 scripts/publish/export_native_fallbacks.py --platform android --output-dir ../androidv2` from `ethos-localization` to generate and update these resources.

### 4.2 Adding Core Localization Engine Files
In `androidv2/app/src/main/java/com/pcg/ethos/localization/`, add the verified Kotlin classes:

1. **`TranslationProvider.kt`**: Interface for string lookup.
2. **`LocalizationModels.kt`**: Data classes for `LocalizationManifest`, `PublishedBundle`, `ManifestLocaleEntry`, `RollbackMetadata`, and `StudyModel`.
3. **`LanguageResolver.kt`**: Resolves device locale (`Locale.getDefault()`) vs study language.
4. **`EthOSLocalizationManager.kt`**:
   - Thread-safe singleton with `AtomicReference<Map<String, String>>` for 0ms lock-free reads.
   - Dual-gate validation (`MessageDigest` SHA-256 + JSON schema check).
   - Disk caching under `context.filesDir/localization/`.
   - Exposes `val state: StateFlow<LocalizationState>` and broadcasts `ETHOS_LANGUAGE_DID_CHANGE`.
5. **`LocalizationExtensions.kt`**:
   ```kotlin
   package com.pcg.ethos.localization

   import android.content.Context
   import androidx.annotation.StringRes

   fun Context.localize(key: String, @StringRes defaultResId: Int = 0): String {
       val fallback = if (defaultResId != 0) getString(defaultResId) else null
       return EthOSLocalizationManager.shared.getString(key, fallback)
   }

   fun Context.localize(key: String, vararg formatArgs: Any): String {
       val base = EthOSLocalizationManager.shared.getString(key)
       return String.format(base, *formatArgs)
   }
   ```

### 4.3 Connecting Startup in EthosApplication
Open `androidv2/app/src/main/java/com/pcg/ethos/EthosApplication.java`:

In `onCreate()`:
```java
@Override
public void onCreate() {
    super.onCreate();
    
    // Initialize EthOS Dynamic Localization Manager
    com.pcg.ethos.localization.EthOSLocalizationManager.Companion.getShared().init(this);
    
    // ... rest of initialization
}
```

### 4.4 Connecting Study / Project Context Switching
Locate where project selection is handled (e.g. `PreferenceService.setSelectedProject` or study launch activities):

When project is selected:
```java
// Create StudyModel and inform localization manager
StudyModel study = new StudyModel(project.getId(), project.getName(), project.getLanguage());
EthOSLocalizationManager.Companion.getShared().setStudyContext(study);
```

When participant exits the project or logs out:
```java
// Revert immediately to system device language
EthOSLocalizationManager.Companion.getShared().setStudyContext(null);
```

### 4.5 Bridging LocaleHelper & R.string Lookups
To avoid breaking the hundreds of existing calls to `com.pcg.ethos.utils.LocaleHelper`, bridge `LocaleHelper.java` internally to query `EthOSLocalizationManager`:

Open `androidv2/app/src/main/java/com/pcg/ethos/utils/LocaleHelper.java`:

```java
// Bridge legacy method to use dynamic remote strings when available:
public static String getStringByProjectLanguage(Context context, String lang, int resId) {
    if (context == null || resId == 0) return "";

    // 1. Resolve resource entry name (e.g., "ethos_auth_btn_sign_in" or "btn_login")
    String entryName = context.getResources().getResourceEntryName(resId);
    
    // 2. Query dynamic manager first
    String dynamicString = EthOSLocalizationManager.Companion.getShared().getString(entryName, null);
    if (dynamicString != null && !dynamicString.isEmpty()) {
        return dynamicString;
    }

    // 3. Fallback to native resources if dynamic bundle misses
    try {
        return context.getString(resId);
    } catch (Exception e) {
        return "";
    }
}
```

### 4.6 Eliminating Disruptive Activity Recreation
Legacy EthOS code called `activity.recreate()` when languages changed. This disrupted long-running video/audio capture pipelines (`CustomCameraActivity`, `HbRecorder`) and cleared unsaved form input.

**New Non-Disruptive Approach:**
1. In `BaseActivity.java`, register a BroadcastReceiver for `ETHOS_LANGUAGE_DID_CHANGE`:
   ```java
   private final BroadcastReceiver languageReceiver = new BroadcastReceiver() {
       @Override
       public void onReceive(Context context, Intent intent) {
           onLanguageChanged();
       }
   };

   @Override
   protected void onStart() {
       super.onStart();
       LocalBroadcastManager.getInstance(this).registerReceiver(
           languageReceiver,
           new IntentFilter(EthOSLocalizationManager.ACTION_LANGUAGE_CHANGED)
       );
   }

   @Override
   protected void onStop() {
       super.onStop();
       LocalBroadcastManager.getInstance(this).unregisterReceiver(languageReceiver);
   }

   protected void onLanguageChanged() {
       // Override in child activities to refresh view labels in-place:
       // titleTextView.setText(this.localize("dashboard.title", R.string.dashboard_title));
   }
   ```
2. Remove all calls to `activity.recreate()` associated with language changes.

### 4.7 Android Verification Checklist
- [ ] `./gradlew assembleDebug` compiles cleanly.
- [ ] App launches instantly offline with 0ms UI delay from native resources.
- [ ] Selecting a study with Thai language immediately swaps UI strings without recreating the Activity.
- [ ] Leaving the study immediately reverts the UI to the device language.
- [ ] Pushing a new version via `firebase_publisher.py` updates visible strings dynamically.
- [ ] Corrupted test bundles are rejected by SHA-256 checksum check and discarded.
- [ ] Untranslated keys fall back safely to English; raw semantic keys are never displayed.

---

# 5. End-to-End Release & Verification Runbook

Follow this runbook to perform a complete manual end-to-end verification cycle across your production apps:

| Step | Action | Command / Tool | Verification Target |
|---|---|---|---|
| **1. Author / Update String** | Update a translation in `translation-store/locales/` | Edit `es/bundle.json` | Set status to `APPROVED` |
| **2. Export Fallbacks** | Update compile-time fallbacks | `python3 scripts/publish/export_native_fallbacks.py --platform all` | Files in `iosv2` and `androidv2` update |
| **3. Publish to Firebase** | Publish new version `1.1.0` | `python3 scripts/publish/firebase_publisher.py --locale es --version 1.1.0 --env production` | Checksum generated, bundle uploaded to Storage, manifest updated in Realtime Database |
| **4. Observe Live Update (iOS)** | Open iOS App with network on | Running `iosv2` | Manifest listener fires, bundle downloads, checksum passes Gate 1, UI updates **without app restart** |
| **5. Observe Live Update (Android)** | Open Android App with network on | Running `androidv2` | Manifest listener fires, bundle downloads, checksum passes Gate 1, UI updates **without activity recreation** |
| **6. Emergency Rollback** | Revert locale to `1.0.0` | `python3 scripts/publish/rollback_locale.py --locale es --target-version 1.0.0 --env production` | Manifest pointer flips to `1.0.0` with `is_rollback: true` |
| **7. Verify Client Rollback** | Check open iOS and Android apps | Both apps | Within seconds, both clients reload `1.0.0` from local disk cache and UI reverts immediately |
| **8. Study Context Exit** | Exit study / return to study list | Tap "Back" / "Exit Study" in app UI | Both apps immediately revert from study language to the participant's device language |
