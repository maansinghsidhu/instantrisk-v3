import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:patrol/patrol.dart';
import 'package:instantrisk_app/main.dart' as app;

void main() {
  patrolTest(
    'InstantRisk E2E Test - Login and Navigate',
    ($) async {
      // Launch the app
      app.main();
      await $.pumpAndSettle();

      // Screenshot: Welcome page
      // await $.screenshot(name: '01_welcome');

      // Find Login button by text and tap
      final loginButton = $(find.text('Login'));
      expect(loginButton, findsOneWidget);
      await loginButton.tap();
      await $.pumpAndSettle();

      // Screenshot: Login form
      // await $.screenshot(name: '02_login_form');

      // Find email field and enter text
      final emailField = $(find.byType(TextField)).first;
      await emailField.enterText('e2e_test@instantrisk.com');
      await $.pumpAndSettle();

      // Screenshot: Email entered
      // await $.screenshot(name: '03_email_entered');

      // Find password field and enter text
      final passwordField = $(find.byType(TextField)).at(1);
      await passwordField.enterText('TestUser123!!');
      await $.pumpAndSettle();

      // Screenshot: Password entered
      // await $.screenshot(name: '04_password_entered');

      // Find and tap Sign In / Login button
      final signInButton = $(find.widgetWithText(ElevatedButton, 'Login'));
      if (signInButton.evaluate().isNotEmpty) {
        await signInButton.tap();
      } else {
        // Try finding by "Sign In" text
        final signIn = $(find.text('Sign In'));
        if (signIn.evaluate().isNotEmpty) {
          await signIn.tap();
        }
      }

      // Wait for login to complete
      await $.pump(const Duration(seconds: 5));
      await $.pumpAndSettle();

      // Screenshot: After login
      // await $.screenshot(name: '05_after_login');

      // Verify we're on dashboard or authenticated page
      // This will depend on your app's navigation structure
    },
  );
}
