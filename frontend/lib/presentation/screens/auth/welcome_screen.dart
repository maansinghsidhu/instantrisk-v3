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
      backgroundColor: AppTheme.bg(context),
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
                      ClipRRect(
                        borderRadius: BorderRadius.circular(10),
                        child: Image.asset('assets/images/logo-icon.png', width: 40, height: 40, fit: BoxFit.contain),
                      ),
                      const SizedBox(width: 12),
                      Text(
                        l10n.appName,
                        style: TextStyle(
                          fontFamily: 'Inter',
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.text1(context),
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
                    icon: Icon(
                      Icons.language,
                      color: AppTheme.text2(context),
                    ),
                  ),
                ],
              ),

              // Spacer
              const Spacer(flex: 2),

              // Center content
              Column(
                children: [
                  // Main logo
                  Container(
                    width: 140,
                    height: 140,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(28),
                      boxShadow: [
                        BoxShadow(
                          color: const Color(0xFF6B00CC).withOpacity(0.3),
                          blurRadius: 40,
                          offset: const Offset(0, 10),
                        ),
                      ],
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(28),
                      child: Image.asset('assets/images/logo-full.png', fit: BoxFit.contain),
                    ),
                  ),
                  const SizedBox(height: 40),

                  // Welcome text
                  Text(
                    l10n.welcomeBack,
                    style: TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 28,
                      fontWeight: FontWeight.w400,
                      color: AppTheme.text1(context),
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
                    style: TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 16,
                      fontWeight: FontWeight.w400,
                      color: AppTheme.text2(context),
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

              // Footer
              Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      TextButton(
                        onPressed: () {},
                        child: Text(
                          l10n.termsOfService,
                          style: TextStyle(fontFamily: 'Inter', fontSize: 13, color: AppTheme.text2(context)),
                        ),
                      ),
                      const SizedBox(width: 16),
                      TextButton(
                        onPressed: () {},
                        child: Text(
                          l10n.privacyPolicy,
                          style: TextStyle(fontFamily: 'Inter', fontSize: 13, color: AppTheme.text2(context)),
                        ),
                      ),
                    ],
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
