import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

/// Reusable login flow for integration tests.
Future<bool> login(
  WidgetTester tester, {
  String email = 'demo@instantrisk.com',
  String password = 'Demo2026pass',
}) async {
  // Tap Login on welcome screen
  final loginBtn = find.text('Login');
  if (loginBtn.evaluate().isEmpty) {
    // Maybe already on login screen or dashboard
    return false;
  }
  await tester.tap(loginBtn);
  await tester.pumpAndSettle(const Duration(seconds: 2));

  // Enter credentials using Keys
  final emailField = find.byKey(const Key('loginEmailField'));
  if (emailField.evaluate().isNotEmpty) {
    await tester.enterText(emailField, email);
  } else {
    // Fallback: first TextField
    await tester.enterText(find.byType(TextField).first, email);
  }
  await tester.pumpAndSettle();

  final passwordField = find.byKey(const Key('loginPasswordField'));
  if (passwordField.evaluate().isNotEmpty) {
    await tester.enterText(passwordField, password);
  } else {
    await tester.enterText(find.byType(TextField).at(1), password);
  }
  await tester.pumpAndSettle();

  // Tap Sign In
  final submitBtn = find.byKey(const Key('loginSubmitButton'));
  if (submitBtn.evaluate().isNotEmpty) {
    await tester.tap(submitBtn);
  } else {
    // Fallback: find ElevatedButton with Sign In text
    final signIn = find.widgetWithText(ElevatedButton, 'Sign In');
    if (signIn.evaluate().isNotEmpty) {
      await tester.tap(signIn);
    }
  }

  // Wait for login API + navigation
  await tester.pumpAndSettle(const Duration(seconds: 5));
  return true;
}

/// Navigate to a tab by index (0=Home, 1=Assess, 2=Docs, 3=Chat, 4=Settings).
Future<void> navigateToTab(WidgetTester tester, int index) async {
  final tabKey = find.byKey(Key('navTab_$index'));
  if (tabKey.evaluate().isNotEmpty) {
    await tester.tap(tabKey);
  } else {
    // Fallback: find by icon in bottom nav
    final icons = [
      Icons.dashboard_outlined,
      Icons.assessment_outlined,
      Icons.description_outlined,
      Icons.chat_bubble_outline,
      Icons.settings_outlined,
    ];
    if (index < icons.length) {
      final iconFinder = find.byIcon(icons[index]);
      if (iconFinder.evaluate().isNotEmpty) {
        await tester.tap(iconFinder.first);
      }
    }
  }
  await tester.pumpAndSettle(const Duration(seconds: 2));
}

/// Take a numbered screenshot.
int _screenshotCount = 0;
Future<void> takeScreenshot(
  IntegrationTestWidgetsFlutterBinding binding,
  String name,
) async {
  _screenshotCount++;
  final label = '${_screenshotCount.toString().padLeft(2, '0')}_$name';
  await binding.takeScreenshot(label);
  print('Screenshot: $label');
}

/// Wait for network operations with extended pump.
Future<void> waitForNetwork(WidgetTester tester, {int seconds = 3}) async {
  await tester.pumpAndSettle(Duration(seconds: seconds));
}

/// Verify that expected texts exist on screen.
List<String> verifyTextsExist(List<String> texts) {
  final missing = <String>[];
  for (final t in texts) {
    if (find.text(t).evaluate().isEmpty) {
      missing.add(t);
    }
  }
  return missing;
}

/// Safe tap — only taps if finder has at least one match.
Future<bool> safeTap(WidgetTester tester, Finder finder) async {
  if (finder.evaluate().isNotEmpty) {
    await tester.tap(finder.first);
    await tester.pumpAndSettle(const Duration(seconds: 1));
    return true;
  }
  return false;
}
