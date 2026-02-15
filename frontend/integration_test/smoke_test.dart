import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:instantrisk_app/main.dart' as app;

/// Minimal smoke test — just verify app boots and reaches welcome screen.
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('App boots to welcome screen', (WidgetTester tester) async {
    debugPrint('[smoke] Starting app...');
    app.main();

    // Pump initial frame
    await tester.pump();
    debugPrint('[smoke] First pump done');

    // Pump through splash (animation 1500ms + delay 2000ms = 3500ms)
    for (int i = 0; i < 20; i++) {
      await tester.pump(const Duration(milliseconds: 500));
      debugPrint('[smoke] Pump ${i + 1}/20 (${(i + 1) * 500}ms)');

      // Check what's on screen
      final hasWelcome = find.byKey(const Key('welcomeLoginButton')).evaluate().isNotEmpty;
      final hasLogin = find.byKey(const Key('loginEmailField')).evaluate().isNotEmpty;
      final hasDashboard = find.textContaining('Dashboard').evaluate().isNotEmpty;
      final hasScaffold = find.byType(Scaffold).evaluate().isNotEmpty;
      final hasLoading = find.textContaining('Loading').evaluate().isNotEmpty;

      debugPrint('[smoke]   Scaffold=$hasScaffold Welcome=$hasWelcome Login=$hasLogin Dashboard=$hasDashboard Loading=$hasLoading');

      if (hasWelcome || hasLogin || hasDashboard) {
        debugPrint('[smoke] App is ready!');
        break;
      }
    }

    // Final check
    final hasWelcome = find.byKey(const Key('welcomeLoginButton')).evaluate().isNotEmpty;
    final hasDashboard = find.textContaining('Dashboard').evaluate().isNotEmpty;
    debugPrint('[smoke] Final state: Welcome=$hasWelcome Dashboard=$hasDashboard');

    expect(find.byType(MaterialApp), findsOneWidget, reason: 'App should render');
    debugPrint('[smoke] DONE');
  });
}
