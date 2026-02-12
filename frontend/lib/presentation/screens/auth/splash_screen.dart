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
                          currentLocation.contains('/analysis/') ||
                          currentLocation.contains('/share/');

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
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Color(0xFF0a0618),
              Color(0xFF1a0a2e),
              Color(0xFF120826),
              Color(0xFF0a0618),
            ],
            stops: [0.0, 0.35, 0.7, 1.0],
          ),
        ),
        child: Center(
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
                      // Logo with glow
                      Stack(
                        alignment: Alignment.center,
                        children: [
                          // Glow effect behind
                          Container(
                            width: 180,
                            height: 180,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              boxShadow: [
                                BoxShadow(
                                  color: const Color(0xFF6B00CC).withValues(alpha: 0.3),
                                  blurRadius: 60,
                                  spreadRadius: 20,
                                ),
                                BoxShadow(
                                  color: const Color(0xFFFF0080).withValues(alpha: 0.15),
                                  blurRadius: 80,
                                  spreadRadius: 30,
                                ),
                              ],
                            ),
                          ),
                          // Sharp logo on top
                          Image.asset(
                            'assets/images/logo-full.png',
                            width: 130,
                            height: 130,
                            fit: BoxFit.contain,
                            filterQuality: FilterQuality.high,
                            errorBuilder: (_, __, ___) => Container(
                              width: 130,
                              height: 130,
                              decoration: BoxDecoration(
                                gradient: const LinearGradient(
                                  colors: [Color(0xFFFF0080), Color(0xFF6B00CC), Color(0xFF0066FF)],
                                ),
                                borderRadius: BorderRadius.circular(24),
                              ),
                              child: const Icon(Icons.shield_outlined, size: 60, color: Colors.white),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 32),
                      // App Name
                      Builder(
                        builder: (context) {
                          final l10n = AppLocalizations.of(context);
                          return ShaderMask(
                            shaderCallback: (bounds) => const LinearGradient(
                              colors: [Color(0xFFFF0080), Color(0xFF8B00FF), Color(0xFF0066FF), Color(0xFF00CCFF)],
                            ).createShader(bounds),
                            child: Text(
                              l10n.appName,
                              style: const TextStyle(
                                fontFamily: 'Inter',
                                fontSize: 36,
                                fontWeight: FontWeight.w800,
                                color: Colors.white,
                                letterSpacing: -0.5,
                              ),
                            ),
                          );
                        },
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'AI UNDERWRITING PLATFORM',
                        style: TextStyle(
                          fontFamily: 'Inter',
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                          color: Colors.white.withValues(alpha: 0.5),
                          letterSpacing: 3,
                        ),
                      ),
                      const SizedBox(height: 48),
                      // Loading indicator with text
                      Column(
                        children: [
                          SizedBox(
                            width: 28,
                            height: 28,
                            child: CircularProgressIndicator(
                              strokeWidth: 2.5,
                              valueColor: AlwaysStoppedAnimation<Color>(
                                const Color(0xFF8B00FF).withValues(alpha: 0.6),
                              ),
                            ),
                          ),
                          const SizedBox(height: 16),
                          Text(
                            'Loading...',
                            style: TextStyle(
                              fontFamily: 'Inter',
                              fontSize: 13,
                              color: Colors.white.withValues(alpha: 0.35),
                              letterSpacing: 0.5,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}
