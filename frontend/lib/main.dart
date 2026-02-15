import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:app_links/app_links.dart';
import 'package:flutter_web_plugins/url_strategy.dart';

import 'core/theme/app_theme.dart';
import 'core/config/app_config.dart';
import 'core/services/auth_service.dart';
import 'core/services/language_service.dart';
import 'core/services/theme_service.dart';
import 'presentation/router/app_router.dart';
import 'l10n/generated/app_localizations.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Use path-based URLs on web (no hash)
  usePathUrlStrategy();

  // Initialize Hive for local storage
  await Hive.initFlutter();

  // Initialize language and theme services
  await languageService.init();
  await themeService.init();

  // Initialize auth service
  await authService.init();

  // Initialize router (sets up 401 handler)
  AppRouter.init();

  // Set preferred orientations (skip on web)
  if (!kIsWeb) {
    await SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
    ]);

    // Set system UI overlay style
    SystemChrome.setSystemUIOverlayStyle(
      const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        systemNavigationBarColor: Colors.white,
        systemNavigationBarIconBrightness: Brightness.dark,
      ),
    );
  }

  // Handle initial deep link (only on mobile)
  AppLinks? appLinks;
  String initialRoute = '/';

  if (!kIsWeb) {
    appLinks = AppLinks();
    final initialLink = await appLinks.getInitialLink();
    if (initialLink != null) {
      final path = initialLink.path;
      if (path.startsWith('/upload/')) {
        initialRoute = path;
      }
    }
  }

  runApp(
    ProviderScope(
      child: InstantRiskApp(initialRoute: initialRoute, appLinks: appLinks),
    ),
  );
}

class InstantRiskApp extends ConsumerStatefulWidget {
  final String initialRoute;
  final AppLinks? appLinks;

  const InstantRiskApp({super.key, required this.initialRoute, this.appLinks});

  @override
  ConsumerState<InstantRiskApp> createState() => _InstantRiskAppState();
}

class _InstantRiskAppState extends ConsumerState<InstantRiskApp> {
  @override
  void initState() {
    super.initState();
    // Listen for deep links while app is running (mobile only)
    if (widget.appLinks != null) {
      widget.appLinks!.uriLinkStream.listen((uri) {
        if (uri.path.startsWith('/upload/')) {
          AppRouter.router.go(uri.path);
        }
      });
    }
    // Navigate to initial route if it's a deep link
    if (widget.initialRoute != '/') {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        AppRouter.router.go(widget.initialRoute);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    // Watch language and theme state for reactive changes
    final languageState = ref.watch(languageProvider);
    final themeState = ref.watch(themeProvider);

    return MaterialApp.router(
      title: AppConfig.appName,
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: themeState.themeMode,
      routerConfig: AppRouter.router,
      // Localization support
      locale: languageState.locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      builder: (context, child) {
        return MediaQuery(
          data: MediaQuery.of(context).copyWith(
            textScaler: TextScaler.linear(
              MediaQuery.of(context).textScaler.scale(1.0).clamp(0.8, 1.2),
            ),
          ),
          child: child!,
        );
      },
    );
  }
}
