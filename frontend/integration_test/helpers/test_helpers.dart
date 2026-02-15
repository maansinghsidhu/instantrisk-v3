import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

/// Default test credentials (underwriter role).
const kTestEmail = 'demo@instantrisk.com';
const kTestPassword = 'Demo2026pass';

/// Reusable login flow for integration tests.
///
/// Navigates from Welcome → Login, enters credentials, submits.
/// Returns true if the login form was found and submitted.
Future<bool> login(
  WidgetTester tester, {
  String email = kTestEmail,
  String password = kTestPassword,
}) async {
  // Tap Login on welcome screen
  final welcomeBtn = find.byKey(const Key('welcomeLoginButton'));
  if (welcomeBtn.evaluate().isNotEmpty) {
    await tester.tap(welcomeBtn);
    await tester.pumpAndSettle(const Duration(seconds: 2));
  } else {
    // Maybe already on login screen?
    if (find.byKey(const Key('loginEmailField')).evaluate().isEmpty) {
      return false; // Not on welcome or login
    }
  }

  // Enter email
  final emailField = find.byKey(const Key('loginEmailField'));
  if (emailField.evaluate().isEmpty) return false;
  await tester.enterText(emailField, email);
  await tester.pumpAndSettle();

  // Enter password
  final passwordField = find.byKey(const Key('loginPasswordField'));
  if (passwordField.evaluate().isEmpty) return false;
  await tester.enterText(passwordField, password);
  await tester.pumpAndSettle();

  // Submit
  final submitBtn = find.byKey(const Key('loginSubmitButton'));
  if (submitBtn.evaluate().isEmpty) return false;
  await tester.tap(submitBtn);

  // Wait for login API + navigation
  await tester.pumpAndSettle(const Duration(seconds: 6));
  return true;
}

/// Check if we're on the dashboard (logged in).
bool isOnDashboard() {
  return find.byKey(const Key('welcomeLoginButton')).evaluate().isEmpty &&
      find.byKey(const Key('loginEmailField')).evaluate().isEmpty;
}

/// Navigate to a tab by trying text first, then icon fallback.
///
/// Tab indices map to sidebar items:
///   0 = Home/Dashboard
///   1 = Assessments/Reports
///   2 = Chat
///   3 = Training
///   4 = Documents
///   5 = Settings
Future<bool> navigateToTab(WidgetTester tester, int index) async {
  // Map index → (text, icon)
  const tabInfo = {
    0: ('Home', Icons.dashboard_outlined),
    1: ('Assessments', Icons.assessment_outlined),
    2: ('Chat', Icons.chat_bubble_outline),
    3: ('Training', Icons.school_outlined),
    4: ('Documents', Icons.description_outlined),
    5: ('Settings', Icons.settings_outlined),
  };

  final info = tabInfo[index];
  if (info == null) return false;

  final (text, icon) = info;

  // Try text first
  final textFinder = find.textContaining(text);
  if (textFinder.evaluate().isNotEmpty) {
    await tester.tap(textFinder.first);
    await tester.pumpAndSettle(const Duration(seconds: 2));
    return true;
  }

  // Fallback to icon
  final iconFinder = find.byIcon(icon);
  if (iconFinder.evaluate().isNotEmpty) {
    await tester.tap(iconFinder.first);
    await tester.pumpAndSettle(const Duration(seconds: 2));
    return true;
  }

  return false;
}

/// Take a numbered screenshot with auto-incrementing counter.
int _screenshotCount = 0;

Future<void> takeScreenshot(
  IntegrationTestWidgetsFlutterBinding binding,
  String name,
) async {
  _screenshotCount++;
  final label = '${_screenshotCount.toString().padLeft(2, '0')}_$name';
  try {
    await binding.takeScreenshot(label);
  } catch (_) {
    // Screenshots may fail on some platforms — non-fatal
  }
  debugPrint('[screenshot] $label');
}

/// Reset screenshot counter (call at start of each test group).
void resetScreenshotCounter() {
  _screenshotCount = 0;
}

/// Wait for network operations with extended pump.
Future<void> waitForNetwork(WidgetTester tester, {int seconds = 3}) async {
  await tester.pumpAndSettle(Duration(seconds: seconds));
}

/// Verify that expected texts exist on screen.
/// Returns list of texts that were NOT found.
List<String> verifyTextsExist(List<String> texts) {
  final missing = <String>[];
  for (final t in texts) {
    if (find.textContaining(t).evaluate().isEmpty) {
      missing.add(t);
    }
  }
  return missing;
}

/// Safe tap — only taps if finder has at least one match.
/// Returns true if tap was performed.
Future<bool> safeTap(WidgetTester tester, Finder finder) async {
  if (finder.evaluate().isNotEmpty) {
    await tester.tap(finder.first);
    await tester.pumpAndSettle(const Duration(seconds: 1));
    return true;
  }
  return false;
}

/// Scroll down to find a widget, then tap it.
Future<bool> scrollAndTap(
  WidgetTester tester,
  Finder target, {
  Finder? scrollable,
  int maxScrolls = 10,
  double delta = -200,
}) async {
  final scroll = scrollable ?? find.byType(Scrollable).first;
  for (var i = 0; i < maxScrolls; i++) {
    if (target.evaluate().isNotEmpty) {
      await tester.tap(target.first);
      await tester.pumpAndSettle();
      return true;
    }
    await tester.drag(scroll, Offset(0, delta));
    await tester.pumpAndSettle();
  }
  return false;
}
