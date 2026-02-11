# InstantRisk V2 Mobile - Deployment Plan

## Current Version: 2.30.0 (Build 30)
**Deployed:** 2026-01-30

---

## Issue Identified

### Problem
After building v2.27.0 locally, the production site (ir.alexandratechlab.com) was still showing v2.26.0.

### Root Cause
The Flutter web build (`flutter build web`) only creates the build artifacts in the local `build/web/` directory. A separate deployment step is required to copy these files to the production server location.

### Fix Applied
Manually copied the build artifacts from the local build directory to the production web server directory.

---

## Deployment Process

### Step 1: Update Version
Edit `pubspec.yaml`:
```yaml
version: 2.27.0+27  # format: major.minor.patch+buildNumber
```

Edit `lib/presentation/screens/auth/login_screen.dart`:
```dart
static const String _buildDate = '2026-01-30';
static const String _buildTime = '14:30';
static const String _buildVersion = 'v2.27.0';
```

### Step 2: Build for Web
```bash
cd /home/maani/instantrisk-v2/mobile
/home/maani/flutter/bin/flutter pub get
/home/maani/flutter/bin/flutter build web --release
```

### Step 3: Run Tests
```bash
/home/maani/flutter/bin/flutter test test/widget_test.dart
```

### Step 4: Deploy to Production
```bash
# Copy build files (excluding uploads directory)
sudo cp -r /home/maani/instantrisk-v2/mobile/build/web/* /var/www/instantrisk-v2/

# Set ownership for web files (but NOT uploads)
sudo chown -R www-data:www-data /var/www/instantrisk-v2/
sudo chown -R maani:www-data /var/www/instantrisk-v2/uploads/
sudo chmod -R 775 /var/www/instantrisk-v2/uploads/
```

**IMPORTANT:** The uploads directory must be owned by `maani:www-data` so the backend can write to it.

### Step 5: Verify Deployment
```bash
curl -s https://ir.alexandratechlab.com/version.json
```

Expected output:
```json
{"app_name":"instantrisk_app","version":"2.27.0","build_number":"27","package_name":"instantrisk_app"}
```

---

## Directory Structure

| Location | Purpose |
|----------|---------|
| `/home/maani/instantrisk-v2/mobile/` | Source code |
| `/home/maani/instantrisk-v2/mobile/build/web/` | Local build output |
| `/var/www/instantrisk-v2/` | Production deployment |

---

## Changes in v2.30.0

### Logout Navigation Fix
**Issue:** `Null check operator used on a null value` when logging out

**Root Cause:** After `Navigator.pop(dialogContext)` was called, the dialog context was no longer valid, but `context.go('/welcome')` was using that invalid context.

**Files Fixed:**
- `lib/presentation/widgets/common/main_shell.dart`
- `lib/presentation/screens/settings/settings_screen.dart`

**Fix Applied:**
1. Captured `GoRouter.of(context)` before showing the dialog
2. Used the captured navigator for navigation after dialog closes
3. Added null-safety checks for localization strings
4. Renamed dialog builder context to `dialogContext` for clarity

```dart
// Before (broken)
Navigator.pop(context);
context.go('/welcome');  // context is invalid!

// After (fixed)
final navigator = GoRouter.of(context);  // Capture before dialog
Navigator.pop(dialogContext);
navigator.go('/welcome');  // Use captured navigator
```

---

## Changes in v2.29.0

### 1. Documents Button Added to Mobile Nav Bar
**File:** `lib/presentation/widgets/common/main_shell.dart`

**Issue:** The Documents/Templates button was only visible on desktop sidebar, not on mobile bottom navigation.

**Fix:** Added "Docs" button to the 5-tab mobile bottom navigation bar:
- Home → Assess → **Docs** → Chat → Settings

### 2. Noto Fonts for Missing Characters
**File:** `web/index.html`

**Issue:** Console warning "Could not find a set of Noto fonts to display all missing characters"

**Fix:** Added Google Fonts CDN links for Noto Sans family:
- Noto Sans (Latin)
- Noto Sans Arabic
- Noto Sans SC (Chinese)
- Noto Sans JP (Japanese)

### 3. Chunked Encoding Backend Fix
**File:** `/etc/nginx/sites-enabled/ir.alexandratechlab.com`

**Issue:** `ERR_INCOMPLETE_CHUNKED_ENCODING` on API responses

**Fix:** Added nginx proxy settings:
```nginx
proxy_buffering off;
chunked_transfer_encoding on;
```

---

## Changes in v2.28.0

### Type Casting Fix (Critical)
**Issue:** `TypeError: type 'int' is not a subtype of type 'String?'`

**Root Cause:** API returns integer IDs but code was casting them directly as `String` using `as String`.

**Files Fixed:**
- `lib/presentation/screens/documents/document_configure_screen.dart`
  - Line 101: `clause['id'] as String` → `clause['id'].toString()`
  - Line 150: `category['id'] as String` → `category['id'].toString()`
  - Line 154: `section['id'] as String` → `section['id'].toString()`
  - Line 761: `clause['id'] as String` → `clause['id'].toString()`
- `lib/presentation/screens/documents/document_generation_screen.dart`
  - Line 111: `clause['id'] as String` → `clause['id'].toString()`
  - Line 177: `data['id'] as String` → `data['id'].toString()`
  - Lines 1570, 1584: `doc['id'] as String?` → `doc['id']?.toString()`
- `lib/presentation/widgets/clause_selector_widget.dart`
  - Line 613: `cat['id'] as String` → `cat['id']?.toString()`
- `lib/presentation/screens/documents/documents_hub_screen.dart`
  - Line 516: `doc['id'] as String?` → `doc['id']?.toString()`

**Best Practice:** Always use `.toString()` instead of `as String` when parsing IDs from API responses.

---

## Changes in v2.27.0

### Document Generation Pipeline Fixes
1. **Fixed missing `mounted` checks in polling loop**
   - File: `lib/presentation/screens/documents/document_generation_screen.dart`
   - Added `mounted` checks before all `setState()` calls
   - Prevents "setState called after dispose" errors

2. **Added polling timeout and error handling**
   - Max poll errors: 15 (30 seconds total)
   - Handles non-200 status codes explicitly
   - Shows user-friendly error messages on failure
   - Handles 401 unauthorized (session expiry)

3. **Implemented file download for document export**
   - File: `lib/presentation/screens/documents/document_preview_screen.dart`
   - Downloads PDF/DOCX files to device
   - Success dialog with Open and Share options
   - Proper error handling

### Documents Pre-loading
- Created `lib/core/services/documents_prefetch_service.dart`
- Pre-fetches document data after login for instant loading
- 5-minute cache with background refresh

---

## Automated Deployment (Future)

Consider adding a deployment script:

```bash
#!/bin/bash
# deploy.sh

set -e

echo "Building Flutter web..."
/home/maani/flutter/bin/flutter build web --release

echo "Running tests..."
/home/maani/flutter/bin/flutter test test/widget_test.dart

echo "Deploying to production..."
sudo cp -r build/web/* /var/www/instantrisk-v2/
sudo chown -R www-data:www-data /var/www/instantrisk-v2/

echo "Verifying deployment..."
curl -s https://ir.alexandratechlab.com/version.json

echo "Deployment complete!"
```

---

## Rollback Procedure

If issues are found after deployment:

1. Keep a backup of the previous build
2. Copy backup to production:
   ```bash
   sudo cp -r /path/to/backup/* /var/www/instantrisk-v2/
   sudo chown -R www-data:www-data /var/www/instantrisk-v2/
   ```

---

## Contact

For deployment issues, check:
- Nginx logs: `/var/log/nginx/error.log`
- Build output: `/home/maani/instantrisk-v2/mobile/build/web/`
