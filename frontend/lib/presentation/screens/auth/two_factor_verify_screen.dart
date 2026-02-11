import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';

/// Two-Factor Verification Screen for Login
/// Shown when a user with 2FA enabled tries to log in
class TwoFactorVerifyScreen extends StatefulWidget {
  final String email;
  final String password;

  const TwoFactorVerifyScreen({
    super.key,
    required this.email,
    required this.password,
  });

  @override
  State<TwoFactorVerifyScreen> createState() => _TwoFactorVerifyScreenState();
}

class _TwoFactorVerifyScreenState extends State<TwoFactorVerifyScreen> {
  final AuthService _authService = AuthService();
  final TextEditingController _codeController = TextEditingController();
  final FocusNode _focusNode = FocusNode();

  bool _isLoading = false;
  String? _error;
  bool _isBackupCode = false;

  @override
  void initState() {
    super.initState();
    // Auto-focus the code input
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _focusNode.requestFocus();
    });
  }

  Future<void> _verify() async {
    final code = _codeController.text.trim();
    if (code.isEmpty) {
      setState(() => _error = 'Please enter a code');
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final result = await _authService.login(
        widget.email,
        widget.password,
        totpCode: code,
      );

      if (result['success'] == true) {
        if (mounted) {
          context.go('/home');
        }
      } else {
        setState(() {
          _error = result['error'] ?? 'Invalid code';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Connection error';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppTheme.textPrimary),
          onPressed: () => context.pop(),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const SizedBox(height: 40),

              // Icon
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: AppTheme.primaryDark.withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.security,
                  size: 40,
                  color: AppTheme.primaryDark,
                ),
              ),
              const SizedBox(height: 24),

              // Title
              const Text(
                'Two-Factor Authentication',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 12),

              // Subtitle
              Text(
                _isBackupCode
                    ? 'Enter one of your backup codes'
                    : 'Enter the 6-digit code from your authenticator app',
                style: const TextStyle(
                  fontSize: 14,
                  color: AppTheme.textSecondary,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 40),

              // Code input
              TextField(
                controller: _codeController,
                focusNode: _focusNode,
                keyboardType: _isBackupCode ? TextInputType.text : TextInputType.number,
                maxLength: _isBackupCode ? 8 : 6,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 32,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 8,
                  fontFamily: 'Courier',
                ),
                decoration: InputDecoration(
                  counterText: '',
                  hintText: _isBackupCode ? 'XXXXXXXX' : '000000',
                  hintStyle: TextStyle(
                    color: AppTheme.textHint.withOpacity(0.5),
                    letterSpacing: 8,
                  ),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: const BorderSide(color: AppTheme.border, width: 2),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: const BorderSide(color: AppTheme.primaryDark, width: 2),
                  ),
                  contentPadding: const EdgeInsets.symmetric(vertical: 20, horizontal: 16),
                ),
                onChanged: (value) {
                  // Auto-submit when 6 digits entered (for TOTP)
                  if (!_isBackupCode && value.length == 6) {
                    _verify();
                  }
                },
                onSubmitted: (_) => _verify(),
              ),

              // Error message
              if (_error != null) ...[
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.danger.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.error_outline, color: AppTheme.danger, size: 20),
                      const SizedBox(width: 8),
                      Text(
                        _error!,
                        style: const TextStyle(color: AppTheme.danger),
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: 32),

              // Verify button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _isLoading ? null : _verify,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryDark,
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
                      : const Text(
                          'Verify',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                        ),
                ),
              ),
              const SizedBox(height: 24),

              // Toggle backup code mode
              TextButton(
                onPressed: () {
                  setState(() {
                    _isBackupCode = !_isBackupCode;
                    _codeController.clear();
                    _error = null;
                  });
                },
                child: Text(
                  _isBackupCode
                      ? 'Use authenticator app code'
                      : 'Use a backup code instead',
                  style: const TextStyle(
                    color: AppTheme.primaryDark,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Help text
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.border),
                ),
                child: Column(
                  children: [
                    const Icon(Icons.help_outline, color: AppTheme.textSecondary),
                    const SizedBox(height: 8),
                    const Text(
                      'Open your authenticator app (Google Authenticator, Microsoft Authenticator, etc.) and enter the code shown for InstantRisk.',
                      style: TextStyle(
                        fontSize: 13,
                        color: AppTheme.textSecondary,
                        height: 1.4,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _codeController.dispose();
    _focusNode.dispose();
    super.dispose();
  }
}
