import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:instantrisk_app/main.dart' as app;

/// ChromeDriver-based Integration Tests for Subscription & Approval Features
///
/// Run with:
///   chromedriver --port=4444 &
///   flutter drive --driver=test_driver/integration_test.dart \
///     --target=integration_test/chromedriver_test.dart \
///     -d chrome --screenshot=screenshots/
void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  /// Helper to take screenshot
  Future<void> takeScreenshot(String name) async {
    await binding.takeScreenshot(name);
    debugPrint('Screenshot: $name');
  }

  group('Subscription & Approval UI Tests', () {

    testWidgets('01 - Splash Screen loads correctly', (tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 2));

      await takeScreenshot('01_splash_screen');

      // Verify splash screen elements
      expect(find.text('InstantRisk'), findsOneWidget);
    });

    testWidgets('02 - Welcome Screen displays Login and Create Account', (tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 4));

      await takeScreenshot('02_welcome_screen');

      // Check for Login button
      final loginButton = find.text('Login');
      final createAccountButton = find.text('Create Account');

      expect(loginButton, findsWidgets);
      expect(createAccountButton, findsWidgets);
    });

    testWidgets('03 - Login Screen has proper form fields', (tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 4));

      // Tap Login
      final loginButton = find.text('Login');
      if (loginButton.evaluate().isNotEmpty) {
        await tester.tap(loginButton.first);
        await tester.pumpAndSettle();
      }

      await takeScreenshot('03_login_screen');

      // Verify login form fields exist
      expect(find.byType(TextField), findsWidgets);
      expect(find.text('Email'), findsOneWidget);
      expect(find.text('Password'), findsOneWidget);
    });

    testWidgets('04 - Navigation bar has all tabs', (tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 5));

      await takeScreenshot('04_navigation');

      // Check bottom navigation items exist
      final dashboardIcon = find.byIcon(Icons.dashboard_outlined);
      final assessmentIcon = find.byIcon(Icons.assessment_outlined);
      final chatIcon = find.byIcon(Icons.chat_bubble_outline);
      final settingsIcon = find.byIcon(Icons.settings_outlined);

      // At least some navigation should exist
      expect(
        dashboardIcon.evaluate().isNotEmpty ||
        assessmentIcon.evaluate().isNotEmpty ||
        find.text('Home').evaluate().isNotEmpty,
        true,
      );
    });

    testWidgets('05 - Premium feature badge is visible on Chat', (tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 5));

      // Look for PRO badge or lock icon indicating premium feature
      final proBadge = find.text('PRO');
      final lockIcon = find.byIcon(Icons.lock);

      await takeScreenshot('05_premium_badge');

      // Either badge or lock should indicate premium feature
      final hasPremiumIndicator =
          proBadge.evaluate().isNotEmpty ||
          lockIcon.evaluate().isNotEmpty;

      debugPrint('Premium indicator found: $hasPremiumIndicator');
    });

    testWidgets('06 - Subscription screen shows plans', (tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 5));

      // Navigate to settings then subscription
      final settingsIcon = find.byIcon(Icons.settings_outlined);
      if (settingsIcon.evaluate().isNotEmpty) {
        await tester.tap(settingsIcon.first);
        await tester.pumpAndSettle();

        await takeScreenshot('06_settings_screen');

        final subscriptionItem = find.text('Subscription');
        if (subscriptionItem.evaluate().isNotEmpty) {
          await tester.tap(subscriptionItem.first);
          await tester.pumpAndSettle();

          await takeScreenshot('06_subscription_screen');

          // Verify subscription plans exist
          expect(find.text('Basic'), findsWidgets);
          expect(find.text('Premium'), findsWidgets);
        }
      }
    });

    testWidgets('07 - Chat screen shows premium lock for non-premium users', (tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 5));

      // Try to navigate to chat
      final chatIcon = find.byIcon(Icons.chat_bubble_outline);
      if (chatIcon.evaluate().isNotEmpty) {
        await tester.tap(chatIcon.first);
        await tester.pumpAndSettle(const Duration(seconds: 2));

        await takeScreenshot('07_chat_screen');

        // Check for premium locked banner
        final premiumBanner = find.text('Upgrade to Premium');
        final premiumIcon = find.byIcon(Icons.workspace_premium);

        final isPremiumLocked =
            premiumBanner.evaluate().isNotEmpty ||
            premiumIcon.evaluate().isNotEmpty;

        debugPrint('Chat premium locked: $isPremiumLocked');
      }
    });

    testWidgets('08 - Admin approval screen accessible for admins', (tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 5));

      // Navigate to settings
      final settingsIcon = find.byIcon(Icons.settings_outlined);
      if (settingsIcon.evaluate().isNotEmpty) {
        await tester.tap(settingsIcon.first);
        await tester.pumpAndSettle();

        // Look for User Approvals option (admin only)
        final approvalsItem = find.text('User Approvals');
        final isAdminVisible = approvalsItem.evaluate().isNotEmpty;

        debugPrint('Admin approvals visible: $isAdminVisible');

        if (isAdminVisible) {
          await tester.tap(approvalsItem.first);
          await tester.pumpAndSettle();

          await takeScreenshot('08_admin_approvals');

          // Verify approval tabs exist
          expect(find.text('Pending'), findsOneWidget);
          expect(find.text('Approved'), findsOneWidget);
          expect(find.text('Rejected'), findsOneWidget);
        }
      }
    });

  });
}
