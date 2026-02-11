# InstantRisk V2 - Store Deployment Guide

## Prerequisites

### Google Play Store (Android)
1. Google Play Console account ($25 one-time fee)
2. Service account with API access
3. Release signing keystore

### Apple App Store (iOS)
1. Apple Developer account ($99/year)
2. App Store Connect API key
3. Code signing certificates (managed via Match)

---

## Setup Instructions

### 1. Android Setup

#### Create Release Keystore
```bash
keytool -genkey -v -keystore fastlane/instantrisk-release.keystore \
  -alias instantrisk -keyalg RSA -keysize 2048 -validity 10000
```

#### Configure Signing
```bash
cp android/key.properties.example android/key.properties
# Edit android/key.properties with your keystore details
```

#### Google Play API Access
1. Go to Google Cloud Console
2. Create service account
3. Grant access in Play Console (Settings > API access)
4. Download JSON key to `fastlane/play-store-credentials.json`

### 2. iOS Setup

#### App Store Connect API Key
1. Go to App Store Connect > Users and Access > Keys
2. Generate API Key with "App Manager" role
3. Download .p8 file
4. Create `fastlane/app-store-connect-api-key.json`:
```json
{
  "key_id": "YOUR_KEY_ID",
  "issuer_id": "YOUR_ISSUER_ID",
  "key_filepath": "fastlane/AuthKey_XXXXX.p8"
}
```

#### Code Signing (Match)
```bash
fastlane match init
fastlane match appstore
```

---

## Deployment Commands

### Build Only
```bash
# Android AAB (for Play Store)
fastlane android build_release

# Android APK (for testing)
fastlane android build_apk

# iOS IPA
fastlane ios build_release
```

### Deploy to Testing
```bash
# Android Internal Testing
fastlane android deploy_internal

# iOS TestFlight
fastlane ios deploy_testflight
```

### Deploy to Production
```bash
# Google Play Production
fastlane android deploy_production

# App Store
fastlane ios deploy_appstore
```

### Deploy Both Platforms
```bash
# Build all
fastlane build_all

# Deploy beta to both stores
fastlane deploy_beta
```

---

## App Store Listing Requirements

### Screenshots Needed
- iPhone 6.7" (1290 x 2796) - 3-5 screenshots
- iPhone 6.5" (1284 x 2778) - 3-5 screenshots
- iPad Pro 12.9" (2048 x 2732) - 3-5 screenshots

### Android Screenshots
- Phone (1080 x 1920) - 2-8 screenshots
- Tablet 7" (1200 x 1920) - optional
- Tablet 10" (1800 x 2560) - optional

### Required Assets
- App Icon: 1024x1024 (no transparency for iOS)
- Feature Graphic (Android): 1024x500

---

## Checklist Before Submission

- [ ] App icons generated (all sizes)
- [ ] Splash screens configured
- [ ] Privacy policy URL added
- [ ] App description written
- [ ] Screenshots captured
- [ ] Release notes prepared
- [ ] Test on real devices
- [ ] Remove debug code
- [ ] Check permissions are minimal
- [ ] Verify API endpoints are production
