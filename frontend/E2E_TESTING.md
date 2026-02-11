# InstantRisk V2 - E2E Testing Guide

This guide explains how to run comprehensive E2E tests with screenshots for InstantRisk V2.

## Test Credentials

```
Email: e2e_test@instantrisk.com
Password: TestUser123!!
```

## Option 1: Flutter Integration Tests (Recommended)

Flutter's native integration testing framework can interact directly with Flutter widgets.

### Setup

The integration test is already set up in:
- `integration_test/full_e2e_test.dart` - Main test file
- `test_driver/integration_test.dart` - Test driver with screenshot support

### Run on Chrome (Web)

```bash
cd /home/maani/instantrisk-v2/mobile

# Run integration tests on Chrome
flutter drive \
  --driver=test_driver/integration_test.dart \
  --target=integration_test/full_e2e_test.dart \
  -d chrome

# Screenshots saved to: build/integration_test/
```

### Run on Android Emulator

```bash
# Start emulator first
flutter emulators --launch <emulator_id>

# Run tests
flutter drive \
  --driver=test_driver/integration_test.dart \
  --target=integration_test/full_e2e_test.dart \
  -d emulator-5554
```

### Run on iOS Simulator

```bash
flutter drive \
  --driver=test_driver/integration_test.dart \
  --target=integration_test/full_e2e_test.dart \
  -d "iPhone 14"
```

---

## Option 2: Maestro (Mobile-Focused)

Maestro is an open-source mobile UI testing framework that works well with Flutter.

### Install Maestro

```bash
# macOS/Linux
curl -Ls "https://get.maestro.mobile.dev" | bash

# Windows (PowerShell)
iwr "https://get.maestro.mobile.dev" -useb | iex
```

### Run Maestro Tests

```bash
cd /home/maani/instantrisk-v2/mobile

# Run full E2E test
maestro test .maestro/full_e2e_test.yaml

# Screenshots saved to: ~/.maestro/tests/<timestamp>/
```

### Maestro Cloud (Optional)

For parallel testing on real devices:
```bash
maestro cloud .maestro/full_e2e_test.yaml
```

---

## Option 3: API Testing with Screenshots

Since Flutter web uses CanvasKit (canvas-based rendering), browser automation tools
like Playwright have limited interaction capabilities. However, API testing works well.

### Run API Tests

```bash
cd /home/maani/instantrisk-v2

# Run comprehensive API + screenshot test
python3 e2e_final_test.py

# Screenshots saved to: e2e_final_screenshots/
```

---

## What Gets Tested

| Feature | Integration Test | Maestro | API Test |
|---------|------------------|---------|----------|
| Login/Auth | ✅ | ✅ | ✅ |
| Dashboard | ✅ | ✅ | ✅ |
| New Assessment | ✅ | ✅ | ✅ |
| Assessment Results | ✅ | ✅ | ✅ |
| Sanctions Screening | ✅ | ✅ | ✅ |
| Document Generation | ✅ | ✅ | ✅ |
| AI Chat | ✅ | ✅ | ✅ |
| Language Change (DE) | ✅ | ✅ | ⚠️ |
| Language Change (AR) | ✅ | ✅ | ⚠️ |
| Documents Hub | ✅ | ✅ | ✅ |

---

## Test Assessments

Pre-created assessments for testing:

| ID | Scenario | Name | Territory |
|----|----------|------|-----------|
| 166 | GO | Safe Corporation Ltd | United Kingdom |
| 167 | NO-GO | Vladimir Putin Holdings | Russia |

### Direct URLs

```
Results (GO):      https://ir.alexandratechlab.com/assessments/166/results
Sanctions (NO-GO): https://ir.alexandratechlab.com/assessments/167/sanctions
Document Gen:      https://ir.alexandratechlab.com/assessments/166/generate-documents
```

---

## Troubleshooting

### Flutter Integration Tests Not Running

```bash
# Make sure dependencies are installed
flutter pub get

# Check for errors
flutter analyze

# Try running in debug mode
flutter drive --driver=test_driver/integration_test.dart \
  --target=integration_test/full_e2e_test.dart \
  -d chrome --debug
```

### Maestro Tests Failing

```bash
# Check if app is running
maestro hierarchy

# Run with verbose logging
maestro test .maestro/full_e2e_test.yaml --debug-output
```

### API Tests Failing

```bash
# Check API health
curl https://ir.alexandratechlab.com/api/v1/health

# Check auth
curl -X POST https://ir.alexandratechlab.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"e2e_test@instantrisk.com","password":"TestUser123!!"}'
```

---

## Screenshot Locations

| Test Type | Screenshot Location |
|-----------|---------------------|
| Flutter Integration | `build/integration_test/` |
| Maestro | `~/.maestro/tests/<timestamp>/` |
| API Test | `e2e_final_screenshots/` |

---

## Manual Testing Checklist

If automated tests are not possible, manually verify:

- [ ] Login with test credentials
- [ ] View dashboard
- [ ] Create new assessment
- [ ] View assessment 166 results
- [ ] Run sanctions on assessment 167
- [ ] Generate documents for assessment 166
- [ ] Test AI chat with insurance question
- [ ] Change language to German (Deutsch)
- [ ] Verify German translations
- [ ] Change language to Arabic (العربية)
- [ ] Verify RTL layout
- [ ] Download a generated document
