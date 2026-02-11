import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _fadeAnimation;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _controller,
        curve: const Interval(0.0, 0.5, curve: Curves.easeOut),
      ),
    );

    _scaleAnimation = Tween<double>(begin: 0.8, end: 1.0).animate(
      CurvedAnimation(
        parent: _controller,
        curve: const Interval(0.0, 0.5, curve: Curves.easeOut),
      ),
    );

    _controller.forward();

    // Navigate based on auth state after animation
    // But only if we're still on the splash screen (not a deep link)
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) {
        final currentLocation = GoRouterState.of(context).uri.toString();
        final currentPath = GoRouterState.of(context).uri.path;

        // Don't redirect if we're on a deep link (e.g., /upload/token)
        final isDeepLink = currentLocation.contains('/upload/') ||
                          currentPath.contains('/upload/') ||
                          currentLocation.contains('/analysis/');

        if (!isDeepLink && (currentLocation == '/' || currentLocation.isEmpty || currentPath == '/')) {
          if (authService.isLoggedIn) {
            context.go('/home');
          } else {
            context.go('/welcome');
          }
        }
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.primaryDark,
      body: Center(
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, child) {
            return FadeTransition(
              opacity: _fadeAnimation,
              child: ScaleTransition(
                scale: _scaleAnimation,
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    // Logo
                    Container(
                      width: 100,
                      height: 100,
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(24),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withOpacity(0.2),
                            blurRadius: 20,
                            offset: const Offset(0, 10),
                          ),
                        ],
                      ),
                      child: const Icon(
                        Icons.analytics_outlined,
                        size: 50,
                        color: AppTheme.primaryDark,
                      ),
                    ),
                    const SizedBox(height: 24),
                    // App Name
                    Builder(
                      builder: (context) {
                        final l10n = AppLocalizations.of(context);
                        return Text(
                          l10n.appName,
                          style: const TextStyle(
                            fontFamily: 'Inter',
                            fontSize: 32,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                        );
                      },
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'ENTERPRISE EDITION V2.0',
                      style: TextStyle(
                        fontFamily: 'Inter',
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        color: Colors.white.withOpacity(0.7),
                        letterSpacing: 2,
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
