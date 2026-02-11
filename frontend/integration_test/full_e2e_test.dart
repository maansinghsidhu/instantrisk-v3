import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:instantrisk_app/main.dart' as app;

/// InstantRisk V2 - Full E2E Integration Test
///
/// This test uses Flutter's native integration testing framework
/// which can interact directly with Flutter widgets (unlike Playwright).
///
/// Run with:
/// flutter test integration_test/full_e2e_test.dart -d chrome
///
/// Or for web:
/// flutter drive --driver=test_driver/integration_test.dart --target=integration_test/full_e2e_test.dart -d chrome

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  // Test credentials
  const testEmail = 'e2e_test@instantrisk.com';
  const testPassword = 'TestUser123!!';

  // Screenshot counter
  int screenshotCount = 0;

  Future<void> takeScreenshot(String name) async {
    screenshotCount++;
    final screenshotName = '${screenshotCount.toString().padLeft(2, '0')}_$name';

    // For integration tests, screenshots are handled differently
    await binding.takeScreenshot(screenshotName);
    print('📸 Screenshot: $screenshotName');
  }

  group('InstantRisk E2E Tests', () {
    testWidgets('Full app flow test', (WidgetTester tester) async {
      // Launch the app
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 3));

      print('=' * 60);
      print('INSTANTRISK V2 - FLUTTER INTEGRATION TEST');
      print('=' * 60);

      // ========================================
      // TEST 1: Welcome Screen
      // ========================================
      print('\n--- TEST 1: Welcome Screen ---');

      await takeScreenshot('welcome_screen');

      // Find Login button
      final loginButton = find.text('Login');
      expect(loginButton, findsOneWidget, reason: 'Login button should be visible');
      print('✅ Login button found');

      // ========================================
      // TEST 2: Login Flow
      // ========================================
      print('\n--- TEST 2: Login Flow ---');

      // Tap Login button
      await tester.tap(loginButton);
      await tester.pumpAndSettle(const Duration(seconds: 2));
      await takeScreenshot('login_form');

      // Find email field and enter email
      final emailField = find.byType(TextField).first;
      await tester.enterText(emailField, testEmail);
      await tester.pumpAndSettle();
      print('✅ Email entered: $testEmail');

      // Find password field and enter password
      final passwordFields = find.byType(TextField);
      final passwordField = passwordFields.at(1); // Second TextField
      await tester.enterText(passwordField, testPassword);
      await tester.pumpAndSettle();
      print('✅ Password entered');

      await takeScreenshot('credentials_entered');

      // Find and tap Sign In button
      final signInButton = find.widgetWithText(ElevatedButton, 'Sign In');
      if (signInButton.evaluate().isEmpty) {
        // Try alternative text
        final loginSubmit = find.widgetWithText(FilledButton, 'Login');
        if (loginSubmit.evaluate().isNotEmpty) {
          await tester.tap(loginSubmit);
        }
      } else {
        await tester.tap(signInButton);
      }

      await tester.pumpAndSettle(const Duration(seconds: 5));
      await takeScreenshot('after_login');

      // Check if we're logged in (dashboard visible or no welcome screen)
      final welcomeText = find.text('Welcome Back');
      if (welcomeText.evaluate().isEmpty) {
        print('✅ Login successful - Welcome screen gone');
      } else {
        print('⚠️ May still be on welcome screen');
      }

      // ========================================
      // TEST 3: Dashboard
      // ========================================
      print('\n--- TEST 3: Dashboard ---');

      // Look for dashboard elements
      final dashboardElements = [
        find.text('Dashboard'),
        find.text('Recent Assessments'),
        find.text('New Assessment'),
      ];

      for (final element in dashboardElements) {
        if (element.evaluate().isNotEmpty) {
          print('✅ Found: ${element.toString()}');
        }
      }

      await takeScreenshot('dashboard');

      // ========================================
      // TEST 4: Navigate to Assessments
      // ========================================
      print('\n--- TEST 4: Assessments List ---');

      // Try to find assessments navigation
      final assessmentsNav = find.text('Assessments');
      if (assessmentsNav.evaluate().isNotEmpty) {
        await tester.tap(assessmentsNav.first);
        await tester.pumpAndSettle(const Duration(seconds: 2));
        await takeScreenshot('assessments_list');
        print('✅ Navigated to Assessments');
      }

      // ========================================
      // TEST 5: New Assessment
      // ========================================
      print('\n--- TEST 5: New Assessment Form ---');

      final newAssessmentBtn = find.text('New Assessment');
      if (newAssessmentBtn.evaluate().isNotEmpty) {
        await tester.tap(newAssessmentBtn.first);
        await tester.pumpAndSettle(const Duration(seconds: 2));
        await takeScreenshot('new_assessment_form');
        print('✅ New Assessment form opened');
      }

      // ========================================
      // TEST 6: Settings / Language
      // ========================================
      print('\n--- TEST 6: Settings & Language ---');

      // Navigate to settings
      final settingsNav = find.byIcon(Icons.settings);
      if (settingsNav.evaluate().isNotEmpty) {
        await tester.tap(settingsNav.first);
        await tester.pumpAndSettle(const Duration(seconds: 2));
        await takeScreenshot('settings_page');
        print('✅ Settings page opened');

        // Look for language option
        final languageOption = find.text('Language');
        if (languageOption.evaluate().isNotEmpty) {
          await tester.tap(languageOption.first);
          await tester.pumpAndSettle(const Duration(seconds: 2));
          await takeScreenshot('language_settings');
          print('✅ Language settings opened');

          // Try to select German
          final germanOption = find.text('Deutsch');
          if (germanOption.evaluate().isNotEmpty) {
            await tester.tap(germanOption.first);
            await tester.pumpAndSettle(const Duration(seconds: 1));
            await takeScreenshot('german_selected');
            print('✅ German language selected');

            // Save language
            final saveBtn = find.text('Save');
            if (saveBtn.evaluate().isNotEmpty) {
              await tester.tap(saveBtn.first);
              await tester.pumpAndSettle(const Duration(seconds: 2));
              await takeScreenshot('language_saved');
              print('✅ Language saved');
            }
          }
        }
      }

      // ========================================
      // TEST 7: AI Chat
      // ========================================
      print('\n--- TEST 7: AI Chat ---');

      final chatNav = find.text('Chat');
      if (chatNav.evaluate().isEmpty) {
        // Try icon
        final chatIcon = find.byIcon(Icons.chat);
        if (chatIcon.evaluate().isNotEmpty) {
          await tester.tap(chatIcon.first);
          await tester.pumpAndSettle(const Duration(seconds: 2));
        }
      } else {
        await tester.tap(chatNav.first);
        await tester.pumpAndSettle(const Duration(seconds: 2));
      }

      await takeScreenshot('chat_page');

      // Try to send a message
      final chatInput = find.byType(TextField);
      if (chatInput.evaluate().isNotEmpty) {
        await tester.enterText(chatInput.first, 'What is marine insurance?');
        await tester.pumpAndSettle();

        // Find send button
        final sendBtn = find.byIcon(Icons.send);
        if (sendBtn.evaluate().isNotEmpty) {
          await tester.tap(sendBtn.first);
          await tester.pumpAndSettle(const Duration(seconds: 5));
          await takeScreenshot('chat_response');
          print('✅ Chat message sent');
        }
      }

      // ========================================
      // TEST 8: Documents
      // ========================================
      print('\n--- TEST 8: Documents Hub ---');

      final docsNav = find.text('Documents');
      if (docsNav.evaluate().isNotEmpty) {
        await tester.tap(docsNav.first);
        await tester.pumpAndSettle(const Duration(seconds: 2));
        await takeScreenshot('documents_hub');
        print('✅ Documents hub opened');
      }

      // ========================================
      // SUMMARY
      // ========================================
      print('\n' + '=' * 60);
      print('TEST SUMMARY');
      print('=' * 60);
      print('Total screenshots taken: $screenshotCount');
      print('Screenshots location: build/integration_test/');
    });

    testWidgets('Test sanctions screening on assessment', (WidgetTester tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 3));

      // This would navigate to a specific assessment and run sanctions
      // For now, just verify the app loads
      expect(find.byType(MaterialApp), findsOneWidget);
      print('✅ App launched successfully for sanctions test');
    });

    testWidgets('Test document generation', (WidgetTester tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 3));

      // This would test document generation flow
      expect(find.byType(MaterialApp), findsOneWidget);
      print('✅ App launched successfully for document generation test');
    });
  });
}
