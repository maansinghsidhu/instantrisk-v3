import 'package:flutter_test/flutter_test.dart';
import 'package:patrol/patrol.dart';
import 'package:instantrisk_app/main.dart' as app;

void main() {
  patrolTest(
    'Full E2E Test with Screenshots',
    ($) async {
      // Launch the app
      app.main();
      await $.pumpAndSettle();

      // Take initial screenshot
      await $.takeScreenshot(name: '01_welcome_page');

      // Find and tap Login button
      await $(#loginButton).tap();
      await $.pumpAndSettle();
      await $.takeScreenshot(name: '02_login_form');

      // Enter email
      await $(#emailField).enterText('e2e_test@instantrisk.com');
      await $.pumpAndSettle();
      await $.takeScreenshot(name: '03_email_entered');

      // Enter password
      await $(#passwordField).enterText('TestUser123!!');
      await $.pumpAndSettle();
      await $.takeScreenshot(name: '04_password_entered');

      // Tap Sign In button
      await $(#signInButton).tap();
      await $.pumpAndSettle(duration: Duration(seconds: 5));
      await $.takeScreenshot(name: '05_after_login');

      // Navigate to Dashboard
      await $(#dashboardTab).tap();
      await $.pumpAndSettle();
      await $.takeScreenshot(name: '06_dashboard');

      // Navigate to Assessments
      await $(#assessmentsTab).tap();
      await $.pumpAndSettle();
      await $.takeScreenshot(name: '07_assessments');

      // Navigate to New Assessment
      await $(#newAssessmentButton).tap();
      await $.pumpAndSettle();
      await $.takeScreenshot(name: '08_new_assessment');

      // Go back
      await $.native.pressBack();
      await $.pumpAndSettle();

      // Navigate to Documents
      await $(#documentsTab).tap();
      await $.pumpAndSettle();
      await $.takeScreenshot(name: '09_documents');

      // Navigate to Chat
      await $(#chatTab).tap();
      await $.pumpAndSettle();
      await $.takeScreenshot(name: '10_chat');

      // Navigate to Settings
      await $(#settingsTab).tap();
      await $.pumpAndSettle();
      await $.takeScreenshot(name: '11_settings');
    },
  );
}
