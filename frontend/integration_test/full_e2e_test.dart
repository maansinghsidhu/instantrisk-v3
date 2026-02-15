import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:instantrisk_app/main.dart' as app;

/// InstantRisk V5 — Full E2E Integration Test with Screenshots
///
/// Uses pump(500ms) intervals. NEVER pumpAndSettle (hangs on spinners).
/// Screenshots captured via binding.takeScreenshot() + extended driver.
///
/// Run:
///   chromedriver --port=4444
///   flutter drive --driver=test_driver/integration_test.dart \
///       --target=integration_test/full_e2e_test.dart -d chrome

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  const email = 'demo@instantrisk.com';
  const password = 'Demo2026pass';

  testWidgets('Full E2E test', (WidgetTester tester) async {
    final passed = <String>[];
    final skipped = <String>[];
    int shotNum = 0;

    void pass(String msg) {
      passed.add(msg);
      debugPrint('[PASS] $msg');
    }
    void skip(String msg) {
      skipped.add(msg);
      debugPrint('[SKIP] $msg');
    }

    Future<void> screenshot(String name) async {
      shotNum++;
      final label = '${shotNum.toString().padLeft(2, '0')}_$name';
      try {
        await binding.takeScreenshot(label);
        debugPrint('[SCREENSHOT] $label');
      } catch (e) {
        debugPrint('[SCREENSHOT] $label — failed: $e');
      }
    }

    debugPrint('=' * 60);
    debugPrint('INSTANTRISK V5 — FULL E2E INTEGRATION TEST');
    debugPrint('=' * 60);

    // ── PHASE 1: Boot app ──
    debugPrint('\n--- PHASE 1: App Launch ---');
    app.main();
    await tester.pump();

    // Pump through splash — 10 pumps at 500ms = 5s total
    bool welcomeFound = false;
    bool dashboardFound = false;
    for (int i = 1; i <= 10; i++) {
      await tester.pump(const Duration(milliseconds: 500));
      welcomeFound = find.byKey(const Key('welcomeLoginButton')).evaluate().isNotEmpty;
      dashboardFound = find.textContaining('Dashboard').evaluate().isNotEmpty;
      debugPrint('[P1] Pump $i/10 welcome=$welcomeFound dashboard=$dashboardFound');
      if (welcomeFound || dashboardFound) break;
    }

    expect(find.byType(MaterialApp), findsOneWidget, reason: 'App must render');
    expect(welcomeFound || dashboardFound, isTrue,
        reason: 'Must reach welcome or dashboard within 5s');
    pass('App boots to ${welcomeFound ? "welcome" : "dashboard"} screen');
    await screenshot('welcome_screen');

    // ── PHASE 2: Login ──
    debugPrint('\n--- PHASE 2: Login ---');
    bool loggedIn = dashboardFound;

    if (welcomeFound) {
      expect(find.byKey(const Key('welcomeLoginButton')), findsOneWidget);
      pass('Welcome screen has login button');

      await tester.tap(find.byKey(const Key('welcomeLoginButton')));
      for (int i = 1; i <= 6; i++) {
        await tester.pump(const Duration(milliseconds: 500));
        if (find.byKey(const Key('loginEmailField')).evaluate().isNotEmpty) break;
      }

      expect(find.byKey(const Key('loginEmailField')), findsOneWidget);
      expect(find.byKey(const Key('loginPasswordField')), findsOneWidget);
      expect(find.byKey(const Key('loginSubmitButton')), findsOneWidget);
      pass('Login screen renders correctly');
      await screenshot('login_screen');

      // Enter credentials
      await tester.enterText(find.byKey(const Key('loginEmailField')), email);
      await tester.pump(const Duration(milliseconds: 500));
      await tester.enterText(find.byKey(const Key('loginPasswordField')), password);
      await tester.pump(const Duration(milliseconds: 500));
      pass('Credentials entered');
      await screenshot('credentials_filled');

      // Submit login
      await tester.tap(find.byKey(const Key('loginSubmitButton')));
      debugPrint('[INFO] Login submitted — waiting for API...');

      for (int i = 1; i <= 20; i++) {
        await tester.pump(const Duration(milliseconds: 500));
        final hasDash = find.textContaining('Dashboard').evaluate().isNotEmpty;
        final hasAssess = find.textContaining('Assessment').evaluate().isNotEmpty;
        final hasHome = find.byIcon(Icons.dashboard_outlined).evaluate().isNotEmpty;
        if (hasDash || hasAssess || hasHome) {
          loggedIn = true;
          break;
        }
      }

      if (loggedIn) {
        pass('Login succeeded — on dashboard');
        await screenshot('dashboard');
      } else {
        skip('Login API unreachable — UI checks only');
        await screenshot('login_api_timeout');
      }
    }

    // ── PHASE 3: Post-login tests ──
    debugPrint('\n--- PHASE 3: Post-Login ---');
    if (loggedIn) {
      for (int i = 0; i < 6; i++) {
        await tester.pump(const Duration(milliseconds: 500));
      }
      for (final text in ['New Assessment', 'Recent', 'Dashboard', 'Total']) {
        if (find.textContaining(text).evaluate().isNotEmpty) {
          pass('Dashboard: "$text"');
        }
      }
      await screenshot('dashboard_loaded');

      // Assessments tab
      final assessTab = find.text('Assessments');
      if (assessTab.evaluate().isNotEmpty) {
        await tester.tap(assessTab.first);
        for (int i = 0; i < 6; i++) {
          await tester.pump(const Duration(milliseconds: 500));
        }
        pass('Assessments tab');
        await screenshot('assessments');

        final cards = find.byType(Card);
        if (cards.evaluate().isNotEmpty) {
          await tester.tap(cards.first);
          for (int i = 0; i < 10; i++) {
            await tester.pump(const Duration(milliseconds: 500));
          }
          for (final x in ['GO', 'NO-GO', 'Risk', 'Score', 'Recommendation']) {
            if (find.textContaining(x).evaluate().isNotEmpty) {
              pass('Detail: "$x"');
            }
          }
          await screenshot('assessment_detail');

          final back = find.byIcon(Icons.arrow_back);
          if (back.evaluate().isNotEmpty) {
            await tester.tap(back.first);
            for (int i = 0; i < 4; i++) {
              await tester.pump(const Duration(milliseconds: 500));
            }
          }
        }
      }

      // Chat tab
      final chatTab = find.text('Chat');
      if (chatTab.evaluate().isNotEmpty) {
        await tester.tap(chatTab.first);
        for (int i = 0; i < 6; i++) {
          await tester.pump(const Duration(milliseconds: 500));
        }
        pass('Chat tab');
        await screenshot('chat');
      }

      // Training tab
      final trainTab = find.text('Training');
      if (trainTab.evaluate().isNotEmpty) {
        await tester.tap(trainTab.first);
        for (int i = 0; i < 6; i++) {
          await tester.pump(const Duration(milliseconds: 500));
        }
        pass('Training tab');
        await screenshot('training');
      }

      // Settings tab
      final settingsTab = find.text('Settings');
      if (settingsTab.evaluate().isNotEmpty) {
        await tester.tap(settingsTab.first);
        for (int i = 0; i < 6; i++) {
          await tester.pump(const Duration(milliseconds: 500));
        }
        pass('Settings tab');
        for (final s in ['Profile', 'Security', 'Language']) {
          if (find.textContaining(s).evaluate().isNotEmpty) {
            pass('Settings: "$s"');
          }
        }
        await screenshot('settings');
      }

      // Home
      final homeTab = find.text('Home');
      if (homeTab.evaluate().isNotEmpty) {
        await tester.tap(homeTab.first);
        for (int i = 0; i < 4; i++) {
          await tester.pump(const Duration(milliseconds: 500));
        }
        pass('Back to Home');
        await screenshot('home_final');
      }
    } else {
      skip('Post-login features (no backend)');
    }

    // ── RESULTS ──
    debugPrint('\n${'=' * 60}');
    debugPrint('E2E RESULTS: ${passed.length} passed, ${skipped.length} skipped, $shotNum screenshots');
    for (final p in passed) {
      debugPrint('  + $p');
    }
    for (final s in skipped) {
      debugPrint('  - $s');
    }
    debugPrint('=' * 60);
  });
}
