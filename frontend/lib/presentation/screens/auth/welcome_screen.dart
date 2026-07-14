import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/config/app_config.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Welcome Screen - Matches PDF mockup design
class WelcomeScreen extends StatelessWidget {
  const WelcomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: AppTheme.background,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            children: [
              // Header with logo and language selector
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  // Logo and brand
                  Row(
                    children: [
                      Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          color: AppTheme.primaryDark,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(
                          Icons.shield_outlined,
                          color: Colors.white,
                          size: 22,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Text(
                        l10n.appName,
                        style: const TextStyle(
                          fontFamily: 'Inter',
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                    ],
                  ),
                  // Language selector
                  IconButton(
                    onPressed: () {
                      // Show language selector
                      _showLanguageSelector(context);
                    },
                    icon: const Icon(
                      Icons.language,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),

              // Spacer
              const Spacer(flex: 2),

              // Center content
              Column(
                children: [
                  // Main logo icon
                  Container(
                    width: 120,
                    height: 120,
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(28),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.08),
                          blurRadius: 40,
                          offset: const Offset(0, 10),
                        ),
                      ],
                    ),
                    child: const Icon(
                      Icons.analytics_outlined,
                      size: 56,
                      color: AppTheme.primaryDark,
                    ),
                  ),
                  const SizedBox(height: 40),

                  // Welcome text
                  Text(
                    l10n.welcomeBack,
                    style: const TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 28,
                      fontWeight: FontWeight.w400,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  Text(
                    l10n.appName,
                    style: const TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 32,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.primaryDark,
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Tagline
                  Text(
                    AppConfig.appTagline,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 16,
                      fontWeight: FontWeight.w400,
                      color: AppTheme.textSecondary,
                      height: 1.5,
                    ),
                  ),
                ],
              ),

              // Spacer
              const Spacer(flex: 3),

              // Buttons
              Column(
                children: [
                  // Login button
                  SizedBox(
                    width: double.infinity,
                    height: 56,
                    child: ElevatedButton(
                      key: const Key('welcomeLoginButton'),
                      onPressed: () => context.push('/login'),
                      child: Text(l10n.login),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Create account button
                  SizedBox(
                    width: double.infinity,
                    height: 56,
                    child: OutlinedButton(
                      onPressed: () => context.push('/register'),
                      child: Text(l10n.createAccount),
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 32),

              // Version and links
              Column(
                children: [
                  Text(
                    'ENTERPRISE EDITION V${AppConfig.appVersion}',
                    style: TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: AppTheme.textHint,
                      letterSpacing: 1.5,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      TextButton(
                        onPressed: () {
                          // Show terms
                        },
                        child: Text(
                          l10n.termsOfService,
                          style: const TextStyle(
                            fontFamily: 'Inter',
                            fontSize: 13,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ),
                      const SizedBox(width: 16),
                      TextButton(
                        onPressed: () {
                          // Show privacy
                        },
                        child: Text(
                          l10n.privacyPolicy,
                          style: const TextStyle(
                            fontFamily: 'Inter',
                            fontSize: 13,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'v5.0.0 - Deployed: 2026-02-02',
                    style: TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 11,
                      color: AppTheme.textHint,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  void _showLanguageSelector(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return Container(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                l10n.language,
                style: const TextStyle(
                  fontFamily: 'Inter',
                  fontSize: 20,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 16),
              ...AppConfig.supportedLanguages.map((lang) {
                return ListTile(
                  leading: Text(
                    lang['flag']!,
                    style: const TextStyle(fontSize: 24),
                  ),
                  title: Text(lang['name']!),
                  onTap: () {
                    Navigator.pop(context);
                    // TODO: Change language
                  },
                );
              }),
            ],
          ),
        );
      },
    );
  }
}
