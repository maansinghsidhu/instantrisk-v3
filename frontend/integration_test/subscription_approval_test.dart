import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:instantrisk_app/main.dart' as app;

/// Integration tests for Subscription and Approval features
/// Tests UI/UX for:
/// - Login flow
/// - Dashboard
/// - Subscription screen
/// - Feature gating (Chat, Documents)
/// - Admin approvals
void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  // Screenshot directory
  final screenshotDir = Directory('screenshots/subscription_approval');

  setUpAll(() async {
    // Create screenshot directory if it doesn't exist
    if (!screenshotDir.existsSync()) {
      screenshotDir.createSync(recursive: true);
    }
  });

  /// Helper to take screenshot with timestamp
  Future<void> takeScreenshot(String name) async {
    await binding.convertFlutterSurfaceToImage();
    final bytes = await binding.takeScreenshot(name);
    final file = File('${screenshotDir.path}/$name.png');
    await file.writeAsBytes(bytes);
    debugPrint('Screenshot saved: ${file.path}');
  }

  group('Subscription & Approval UI Tests', () {
    testWidgets('Complete UI Flow Test', (WidgetTester tester) async {
      // Launch the app
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 3));

      // 1. SPLASH SCREEN
      debugPrint('Testing Splash Screen...');
      await takeScreenshot('01_splash_screen');
      await tester.pumpAndSettle(const Duration(seconds: 2));

      // 2. WELCOME/LOGIN SCREEN
      debugPrint('Testing Welcome/Login Screen...');
      await tester.pumpAndSettle(const Duration(seconds: 2));
      await takeScreenshot('02_welcome_screen');

      // Find and tap login button if on welcome screen
      final loginButton = find.text('Login');
      if (loginButton.evaluate().isNotEmpty) {
        await tester.tap(loginButton);
        await tester.pumpAndSettle(const Duration(seconds: 1));
        await takeScreenshot('03_login_screen');
      }

      // Try to find email field
      final emailField = find.byType(TextField).first;
      if (emailField.evaluate().isNotEmpty) {
        // Enter test credentials
        await tester.enterText(emailField, 'test@instantrisk.io');
        await tester.pumpAndSettle();

        final passwordField = find.byType(TextField).at(1);
        if (passwordField.evaluate().isNotEmpty) {
          await tester.enterText(passwordField, 'testpass123');
          await tester.pumpAndSettle();
        }

        await takeScreenshot('04_login_filled');

        // Tap login/sign in button
        final signInButton = find.widgetWithText(ElevatedButton, 'Sign In');
        if (signInButton.evaluate().isNotEmpty) {
          await tester.tap(signInButton);
          await tester.pumpAndSettle(const Duration(seconds: 3));
        }
      }

      // 3. DASHBOARD
      debugPrint('Testing Dashboard...');
      await tester.pumpAndSettle(const Duration(seconds: 2));
      await takeScreenshot('05_dashboard');

      // 4. NAVIGATE TO SETTINGS
      debugPrint('Testing Settings Navigation...');
      final settingsTab = find.byIcon(Icons.settings_outlined);
      if (settingsTab.evaluate().isNotEmpty) {
        await tester.tap(settingsTab.first);
        await tester.pumpAndSettle(const Duration(seconds: 1));
        await takeScreenshot('06_settings_screen');
      }

      // 5. SUBSCRIPTION SCREEN
      debugPrint('Testing Subscription Screen...');
      final subscriptionItem = find.text('Subscription');
      if (subscriptionItem.evaluate().isNotEmpty) {
        await tester.tap(subscriptionItem.first);
        await tester.pumpAndSettle(const Duration(seconds: 2));
        await takeScreenshot('07_subscription_screen');

        // Scroll to see all plans
        await tester.drag(find.byType(SingleChildScrollView).first, const Offset(0, -300));
        await tester.pumpAndSettle();
        await takeScreenshot('08_subscription_plans');

        // Scroll more to see billing
        await tester.drag(find.byType(SingleChildScrollView).first, const Offset(0, -300));
        await tester.pumpAndSettle();
        await takeScreenshot('09_subscription_billing');

        // Go back
        final backButton = find.byIcon(Icons.arrow_back_ios);
        if (backButton.evaluate().isNotEmpty) {
          await tester.tap(backButton.first);
          await tester.pumpAndSettle();
        }
      }

      // 6. CHECK FOR ADMIN APPROVALS (if admin)
      debugPrint('Testing Admin Approvals Link...');
      final approvalsItem = find.text('User Approvals');
      if (approvalsItem.evaluate().isNotEmpty) {
        await tester.tap(approvalsItem.first);
        await tester.pumpAndSettle(const Duration(seconds: 2));
        await takeScreenshot('10_admin_approvals');

        // Check tabs
        final pendingTab = find.text('Pending');
        if (pendingTab.evaluate().isNotEmpty) {
          await tester.tap(pendingTab.first);
          await tester.pumpAndSettle();
          await takeScreenshot('11_approvals_pending');
        }

        final approvedTab = find.text('Approved');
        if (approvedTab.evaluate().isNotEmpty) {
          await tester.tap(approvedTab.first);
          await tester.pumpAndSettle();
          await takeScreenshot('12_approvals_approved');
        }

        final rejectedTab = find.text('Rejected');
        if (rejectedTab.evaluate().isNotEmpty) {
          await tester.tap(rejectedTab.first);
          await tester.pumpAndSettle();
          await takeScreenshot('13_approvals_rejected');
        }

        // Go back
        final backBtn = find.byIcon(Icons.arrow_back);
        if (backBtn.evaluate().isNotEmpty) {
          await tester.tap(backBtn.first);
          await tester.pumpAndSettle();
        }
      }

      // 7. CHAT SCREEN (Premium Feature)
      debugPrint('Testing Chat Screen (Feature Gating)...');
      final chatTab = find.byIcon(Icons.chat_bubble_outline);
      if (chatTab.evaluate().isNotEmpty) {
        await tester.tap(chatTab.first);
        await tester.pumpAndSettle(const Duration(seconds: 2));
        await takeScreenshot('14_chat_screen');

        // Check for premium lock if not premium
        final premiumBanner = find.text('Upgrade to Premium');
        if (premiumBanner.evaluate().isNotEmpty) {
          await takeScreenshot('15_chat_premium_locked');
        }
      }

      // 8. DOCUMENTS/ASSESSMENTS SCREEN
      debugPrint('Testing Documents Screen...');
      final docsTab = find.byIcon(Icons.description_outlined);
      if (docsTab.evaluate().isNotEmpty) {
        await tester.tap(docsTab.first);
        await tester.pumpAndSettle(const Duration(seconds: 2));
        await takeScreenshot('16_documents_screen');
      }

      // 9. NAVIGATE TO ASSESSMENTS
      debugPrint('Testing Assessments Screen...');
      final assessTab = find.byIcon(Icons.assessment_outlined);
      if (assessTab.evaluate().isNotEmpty) {
        await tester.tap(assessTab.first);
        await tester.pumpAndSettle(const Duration(seconds: 2));
        await takeScreenshot('17_assessments_screen');
      }

      // 10. BACK TO DASHBOARD
      debugPrint('Testing Dashboard Final State...');
      final homeTab = find.byIcon(Icons.dashboard_outlined);
      if (homeTab.evaluate().isNotEmpty) {
        await tester.tap(homeTab.first);
        await tester.pumpAndSettle(const Duration(seconds: 1));
        await takeScreenshot('18_dashboard_final');
      }

      debugPrint('All screenshots captured successfully!');
    });
  });

  group('Subscription Plan Selection Tests', () {
    testWidgets('Plan Selection UI', (WidgetTester tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 5));

      // Navigate to subscription (assuming logged in)
      final settingsTab = find.byIcon(Icons.settings_outlined);
      if (settingsTab.evaluate().isNotEmpty) {
        await tester.tap(settingsTab.first);
        await tester.pumpAndSettle(const Duration(seconds: 1));

        final subscriptionItem = find.text('Subscription');
        if (subscriptionItem.evaluate().isNotEmpty) {
          await tester.tap(subscriptionItem.first);
          await tester.pumpAndSettle(const Duration(seconds: 2));

          // Test plan selection
          final basicPlan = find.text('Basic');
          if (basicPlan.evaluate().isNotEmpty) {
            await tester.tap(basicPlan.first);
            await tester.pumpAndSettle();
            await takeScreenshot('plan_basic_selected');
          }

          final premiumPlan = find.text('Premium');
          if (premiumPlan.evaluate().isNotEmpty) {
            await tester.tap(premiumPlan.first);
            await tester.pumpAndSettle();
            await takeScreenshot('plan_premium_selected');
          }

          final enterprisePlan = find.text('Enterprise');
          if (enterprisePlan.evaluate().isNotEmpty) {
            await tester.tap(enterprisePlan.first);
            await tester.pumpAndSettle();
            await takeScreenshot('plan_enterprise_selected');
          }
        }
      }
    });
  });

  group('Feature Gate Verification', () {
    testWidgets('Premium Feature Lock Display', (WidgetTester tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 5));

      // Check chat tab has premium indicator
      final chatTab = find.byIcon(Icons.chat_bubble_outline);
      if (chatTab.evaluate().isNotEmpty) {
        // Look for lock icon or PRO badge near chat
        final lockIcon = find.byIcon(Icons.lock);
        final proBadge = find.text('PRO');

        if (lockIcon.evaluate().isNotEmpty) {
          await takeScreenshot('feature_lock_visible');
        }

        if (proBadge.evaluate().isNotEmpty) {
          await takeScreenshot('pro_badge_visible');
        }

        // Tap chat to see locked screen
        await tester.tap(chatTab.first);
        await tester.pumpAndSettle(const Duration(seconds: 2));

        // Check for premium locked banner
        final workspacePremium = find.byIcon(Icons.workspace_premium);
        if (workspacePremium.evaluate().isNotEmpty) {
          await takeScreenshot('premium_locked_banner');
        }

        // Check for upgrade button
        final upgradeButton = find.text('Upgrade to Premium');
        if (upgradeButton.evaluate().isNotEmpty) {
          await tester.tap(upgradeButton.first);
          await tester.pumpAndSettle(const Duration(seconds: 1));
          await takeScreenshot('upgrade_dialog');

          // Close dialog
          final maybeLater = find.text('Maybe Later');
          if (maybeLater.evaluate().isNotEmpty) {
            await tester.tap(maybeLater.first);
            await tester.pumpAndSettle();
          }
        }
      }
    });
  });
}
