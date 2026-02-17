import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/documents_prefetch_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Login Screen - User authentication
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;
  bool _isLoading = false;
  String? _errorMessage;

  // Build timestamp - updated on each deployment
  static const String _buildDate = '2026-02-03';
  static const String _buildTime = '15:30';
  static const String _buildVersion = 'v5.0.0+50';

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _showTermsDialog(String title) {
    final l10n = AppLocalizations.of(context);
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (title == l10n.termsOfService) ...[
                const Text(
                  '1. Acceptance of Terms\n\n'
                  'By accessing and using InstantRisk, you agree to be bound by these Terms of Service and all applicable laws and regulations.\n\n'
                  '2. Use of Service\n\n'
                  'InstantRisk provides insurance underwriting assessment tools powered by the InstantRisk Engine. You agree to use the service only for lawful purposes and in accordance with these terms.\n\n'
                  '3. Data and Privacy\n\n'
                  'Your use of InstantRisk is also governed by our Privacy Policy. You consent to the collection and use of information as described therein.\n\n'
                  '4. Intellectual Property\n\n'
                  'The service and its original content, features, and functionality are owned by InstantRisk and are protected by international copyright, trademark, and other intellectual property laws.\n\n'
                  '5. Limitation of Liability\n\n'
                  'InstantRisk shall not be liable for any indirect, incidental, special, consequential, or punitive damages resulting from your use of the service.\n\n'
                  '6. Changes to Terms\n\n'
                  'We reserve the right to modify these terms at any time. Continued use of the service constitutes acceptance of modified terms.',
                  style: TextStyle(fontSize: 13, height: 1.5),
                ),
              ] else ...[
                const Text(
                  '1. Information Collection\n\n'
                  'We collect information you provide directly, including account details, uploaded documents, and usage data.\n\n'
                  '2. Use of Information\n\n'
                  'We use collected information to provide, maintain, and improve our services, and to communicate with you about updates and offers.\n\n'
                  '3. Data Security\n\n'
                  'We implement appropriate security measures to protect your personal information against unauthorized access, alteration, or disclosure.\n\n'
                  '4. Data Sharing\n\n'
                  'We do not sell your personal information. We may share data with service providers who assist in operating our services.\n\n'
                  '5. Your Rights\n\n'
                  'You have the right to access, correct, or delete your personal information. Contact us to exercise these rights.\n\n'
                  '6. Contact\n\n'
                  'For privacy-related inquiries, contact privacy@instantrisk.com',
                  style: TextStyle(fontSize: 13, height: 1.5),
                ),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(AppLocalizations.of(context).close),
          ),
        ],
      ),
    );
  }

  Future<void> _handleLogin() async {
    if (_formKey.currentState!.validate()) {
      setState(() {
        _isLoading = true;
        _errorMessage = null;
      });

      final result = await authService.login(
        _emailController.text.trim(),
        _passwordController.text,
      );

      setState(() => _isLoading = false);

      if (result['success'] == true) {
        // Pre-fetch documents data in background for instant loading
        documentsPrefetchService.prefetch();

        if (mounted) {
          context.go('/home');
        }
      } else if (result['requires_2fa'] == true) {
        // 2FA is required - redirect to 2FA verification screen
        if (mounted) {
          context.go('/2fa-verify', extra: {
            'email': _emailController.text.trim(),
            'password': _passwordController.text,
          });
        }
      } else {
        // Handle specific error cases
        String errorMsg = result['error'] ?? 'Login failed';

        // Check for rate limiting
        if (errorMsg.contains('429') || errorMsg.toLowerCase().contains('too many')) {
          errorMsg = 'Too many login attempts. Please wait a minute and try again.';
        }
        // Check for account locked
        else if (errorMsg.toLowerCase().contains('blocked') || errorMsg.toLowerCase().contains('banned')) {
          errorMsg = 'Account temporarily locked. Please contact support.';
        }

        setState(() {
          _errorMessage = errorMsg;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_ios, color: AppTheme.text1(context)),
          onPressed: () => context.go('/welcome'),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Brand logo
                Center(
                  child: Container(
                    width: 80,
                    height: 80,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(20),
                      boxShadow: [
                        BoxShadow(
                          color: const Color(0xFF6B00CC).withOpacity(0.2),
                          blurRadius: 20,
                          offset: const Offset(0, 6),
                        ),
                      ],
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(20),
                      child: Image.asset('assets/images/logo-icon.png', fit: BoxFit.contain),
                    ),
                  ),
                ),
                const SizedBox(height: 24),

                // Header
                Text(
                  l10n.welcomeBack,
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.text1(context),
                    fontFamily: 'Inter',
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Sign in to continue',
                  style: TextStyle(
                    fontSize: 15,
                    color: AppTheme.text2(context),
                    fontFamily: 'Inter',
                  ),
                ),
                const SizedBox(height: 24),

                // Error message
                if (_errorMessage != null)
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    margin: const EdgeInsets.only(bottom: 16),
                    decoration: BoxDecoration(
                      color: AppTheme.danger.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppTheme.danger.withOpacity(0.3)),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.error_outline, color: AppTheme.danger, size: 20),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            _errorMessage!,
                            style: TextStyle(color: AppTheme.danger, fontSize: 14),
                          ),
                        ),
                      ],
                    ),
                  ),

                // Email field
                Text(
                  l10n.email,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.text1(context),
                  ),
                ),
                const SizedBox(height: 8),
                TextFormField(
                  key: const Key('loginEmailField'),
                  controller: _emailController,
                  keyboardType: TextInputType.emailAddress,
                  decoration: InputDecoration(
                    hintText: l10n.email,
                    prefixIcon: Icon(Icons.email_outlined, color: AppTheme.textH(context)),
                    filled: true,
                    fillColor: AppTheme.surfaceOf(context),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(color: AppTheme.borderOf(context)),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(color: AppTheme.borderOf(context)),
                    ),
                  ),
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return l10n.email;
                    }
                    if (!value.contains('@')) {
                      return l10n.email;
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 24),

                // Password field
                Text(
                  l10n.password,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.text1(context),
                  ),
                ),
                const SizedBox(height: 8),
                TextFormField(
                  key: const Key('loginPasswordField'),
                  controller: _passwordController,
                  obscureText: _obscurePassword,
                  textInputAction: TextInputAction.done,
                  onFieldSubmitted: (_) => _handleLogin(),
                  decoration: InputDecoration(
                    hintText: l10n.password,
                    prefixIcon: Icon(Icons.lock_outlined, color: AppTheme.textH(context)),
                    suffixIcon: IconButton(
                      icon: Icon(
                        _obscurePassword ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                        color: AppTheme.textH(context),
                      ),
                      onPressed: () {
                        setState(() => _obscurePassword = !_obscurePassword);
                      },
                    ),
                    filled: true,
                    fillColor: AppTheme.surfaceOf(context),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(color: AppTheme.borderOf(context)),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(color: AppTheme.borderOf(context)),
                    ),
                  ),
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return l10n.password;
                    }
                    if (value.length < 6) {
                      return l10n.password;
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),

                // Forgot password
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: () => context.go('/forgot-password'),
                    child: Text(
                      l10n.forgotPassword,
                      style: const TextStyle(
                        color: AppTheme.primaryDark,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 32),

                // Login button
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    key: const Key('loginSubmitButton'),
                    onPressed: _isLoading ? null : _handleLogin,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primaryDark,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: _isLoading
                        ? const SizedBox(
                            width: 24,
                            height: 24,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 2,
                            ),
                          )
                        : Text(
                            l10n.login,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                  ),
                ),
                const SizedBox(height: 24),

                // Terms of Service
                Center(
                  child: Wrap(
                    alignment: WrapAlignment.center,
                    children: [
                      Text(
                        '${l10n.login} - ',
                        style: TextStyle(
                          fontSize: 12,
                          color: AppTheme.text2(context),
                        ),
                      ),
                      GestureDetector(
                        onTap: () => _showTermsDialog(l10n.termsOfService),
                        child: Text(
                          l10n.termsOfService,
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppTheme.primaryDark,
                            fontWeight: FontWeight.w600,
                            decoration: TextDecoration.underline,
                          ),
                        ),
                      ),
                      Text(
                        ' & ',
                        style: TextStyle(
                          fontSize: 12,
                          color: AppTheme.text2(context),
                        ),
                      ),
                      GestureDetector(
                        onTap: () => _showTermsDialog(l10n.privacyPolicy),
                        child: Text(
                          l10n.privacyPolicy,
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppTheme.primaryDark,
                            fontWeight: FontWeight.w600,
                            decoration: TextDecoration.underline,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 32),

                // Register link
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      '${l10n.createAccount}? ',
                      style: TextStyle(color: AppTheme.text2(context)),
                    ),
                    TextButton(
                      onPressed: () => context.go('/register'),
                      child: Text(
                        l10n.register,
                        style: const TextStyle(
                          color: AppTheme.primaryDark,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),

                // Logo at bottom
                Center(
                  child: Image.asset('assets/images/logo-icon.png', height: 32),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
