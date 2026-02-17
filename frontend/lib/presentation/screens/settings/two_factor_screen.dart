import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';

/// Two-Factor Authentication Setup Screen
/// Allows users to enable/disable 2FA using TOTP apps like Google Authenticator
class TwoFactorScreen extends StatefulWidget {
  const TwoFactorScreen({super.key});

  @override
  State<TwoFactorScreen> createState() => _TwoFactorScreenState();
}

class _TwoFactorScreenState extends State<TwoFactorScreen> {
  final AuthService _authService = AuthService();
  final TextEditingController _codeController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  bool _isLoading = true;
  bool _is2FAEnabled = false;
  bool _hasBackupCodes = false;

  // Setup state
  bool _isSettingUp = false;
  String? _qrCodeBase64;
  String? _secretKey;
  List<String>? _backupCodes;

  // Disable state
  bool _isDisabling = false;

  @override
  void initState() {
    super.initState();
    _load2FAStatus();
  }

  Future<void> _load2FAStatus() async {
    setState(() => _isLoading = true);
    try {
      final status = await _authService.get2FAStatus();
      setState(() {
        _is2FAEnabled = status['enabled'] ?? false;
        _hasBackupCodes = status['has_backup_codes'] ?? false;
      });
    } catch (e) {
      debugPrint('Error loading 2FA status: $e');
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _startSetup() async {
    setState(() => _isSettingUp = true);
    try {
      final result = await _authService.setup2FA();
      if (result['success'] == true) {
        setState(() {
          _qrCodeBase64 = result['qr_code'];
          _secretKey = result['secret'];
        });
      } else {
        _showError(result['error'] ?? 'Failed to start 2FA setup');
      }
    } catch (e) {
      _showError('Connection error');
    }
  }

  Future<void> _verifyAndEnable() async {
    if (_codeController.text.length != 6) {
      _showError('Please enter a 6-digit code');
      return;
    }

    setState(() => _isLoading = true);
    try {
      final result = await _authService.verify2FA(_codeController.text);
      if (result['success'] == true) {
        setState(() {
          _is2FAEnabled = true;
          _backupCodes = List<String>.from(result['backup_codes'] ?? []);
          _isSettingUp = false;
          _qrCodeBase64 = null;
          _secretKey = null;
        });
        _showBackupCodesDialog();
      } else {
        _showError(result['error'] ?? 'Invalid code');
      }
    } catch (e) {
      _showError('Connection error');
    } finally {
      setState(() => _isLoading = false);
      _codeController.clear();
    }
  }

  Future<void> _disable2FA() async {
    if (_codeController.text.length != 6) {
      _showError('Please enter your 2FA code');
      return;
    }
    if (_passwordController.text.isEmpty) {
      _showError('Please enter your password');
      return;
    }

    setState(() => _isLoading = true);
    try {
      final result = await _authService.disable2FA(
        _passwordController.text,
        _codeController.text,
      );
      if (result['success'] == true) {
        setState(() {
          _is2FAEnabled = false;
          _isDisabling = false;
        });
        _showSuccess('2FA has been disabled');
      } else {
        _showError(result['error'] ?? 'Failed to disable 2FA');
      }
    } catch (e) {
      _showError('Connection error');
    } finally {
      setState(() => _isLoading = false);
      _codeController.clear();
      _passwordController.clear();
    }
  }

  void _showBackupCodesDialog() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.key, color: AppTheme.warning),
            SizedBox(width: 12),
            Text('Backup Codes'),
          ],
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Save these backup codes in a secure place. Each code can only be used once.',
                style: TextStyle(color: AppTheme.text2(context)),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.bg(context),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppTheme.borderOf(context)),
                ),
                child: Column(
                  children: _backupCodes!.map((code) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Text(
                      code,
                      style: const TextStyle(
                        fontFamily: 'Courier',
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 2,
                      ),
                    ),
                  )).toList(),
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              Clipboard.setData(ClipboardData(text: _backupCodes!.join('\n')));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Backup codes copied to clipboard')),
              );
            },
            child: const Text('Copy All'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              setState(() => _backupCodes = null);
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.primaryDark),
            child: const Text('I\'ve Saved Them', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: AppTheme.danger),
    );
  }

  void _showSuccess(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: AppTheme.success),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceOf(context),
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_ios, color: AppTheme.text1(context)),
          onPressed: () => context.pop(),
        ),
        title: Text(
          'Two-Factor Authentication',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.text1(context),
          ),
        ),
        centerTitle: true,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Status card
                  _buildStatusCard(),
                  const SizedBox(height: 24),

                  // Setup or Disable section
                  if (_isSettingUp && _qrCodeBase64 != null)
                    _buildSetupSection()
                  else if (_isDisabling)
                    _buildDisableSection()
                  else
                    _buildMainSection(),
                ],
              ),
            ),
    );
  }

  Widget _buildStatusCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: _is2FAEnabled ? AppTheme.success.withOpacity(0.3) : AppTheme.borderOf(context),
        ),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: _is2FAEnabled
                  ? AppTheme.success.withOpacity(0.1)
                  : AppTheme.warning.withOpacity(0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(
              _is2FAEnabled ? Icons.verified_user : Icons.shield_outlined,
              color: _is2FAEnabled ? AppTheme.success : AppTheme.warning,
              size: 28,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _is2FAEnabled ? '2FA Enabled' : '2FA Disabled',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: _is2FAEnabled ? AppTheme.success : AppTheme.text1(context),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  _is2FAEnabled
                      ? 'Your account is protected with two-factor authentication'
                      : 'Add an extra layer of security to your account',
                  style: TextStyle(
                    fontSize: 13,
                    color: AppTheme.text2(context),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMainSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'About Two-Factor Authentication',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppTheme.text1(context),
          ),
        ),
        const SizedBox(height: 12),
        Text(
          '2FA adds an extra layer of security by requiring a code from your authenticator app in addition to your password.',
          style: TextStyle(
            fontSize: 14,
            color: AppTheme.text2(context),
            height: 1.5,
          ),
        ),
        const SizedBox(height: 20),

        // Compatible apps
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.primaryDark.withOpacity(0.05),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.primaryDark.withOpacity(0.2)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Compatible Apps',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.primaryDark,
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  _buildAppChip('Google Authenticator'),
                  _buildAppChip('Microsoft Authenticator'),
                  _buildAppChip('Authy'),
                  _buildAppChip('1Password'),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 32),

        // Action button
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            onPressed: _is2FAEnabled
                ? () => setState(() => _isDisabling = true)
                : _startSetup,
            style: ElevatedButton.styleFrom(
              backgroundColor: _is2FAEnabled ? AppTheme.danger : AppTheme.primaryDark,
              padding: const EdgeInsets.symmetric(vertical: 16),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            child: Text(
              _is2FAEnabled ? 'Disable 2FA' : 'Enable 2FA',
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: Colors.white,
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildAppChip(String name) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Text(
        name,
        style: TextStyle(
          fontSize: 12,
          color: AppTheme.text2(context),
        ),
      ),
    );
  }

  Widget _buildSetupSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Step 1: Scan QR Code',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppTheme.text1(context),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Open your authenticator app and scan this QR code:',
          style: TextStyle(fontSize: 14, color: AppTheme.text2(context)),
        ),
        const SizedBox(height: 20),

        // QR Code
        Center(
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppTheme.borderOf(context)),
            ),
            child: Image.memory(
              base64Decode(_qrCodeBase64!),
              width: 200,
              height: 200,
            ),
          ),
        ),
        const SizedBox(height: 20),

        // Manual entry key
        Text(
          'Or enter this code manually:',
          style: TextStyle(fontSize: 14, color: AppTheme.text2(context)),
        ),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppTheme.bg(context),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: AppTheme.borderOf(context)),
          ),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  _secretKey!,
                  style: const TextStyle(
                    fontFamily: 'Courier',
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 2,
                  ),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.copy, size: 20),
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: _secretKey!));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Secret key copied')),
                  );
                },
              ),
            ],
          ),
        ),
        const SizedBox(height: 32),

        // Step 2: Verify
        Text(
          'Step 2: Enter Verification Code',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppTheme.text1(context),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Enter the 6-digit code from your authenticator app:',
          style: TextStyle(fontSize: 14, color: AppTheme.text2(context)),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _codeController,
          keyboardType: TextInputType.number,
          maxLength: 6,
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.bold,
            letterSpacing: 8,
          ),
          decoration: InputDecoration(
            counterText: '',
            hintText: '000000',
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        ),
        const SizedBox(height: 24),

        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: () => setState(() {
                  _isSettingUp = false;
                  _qrCodeBase64 = null;
                  _secretKey = null;
                }),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text('Cancel'),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: ElevatedButton(
                onPressed: _verifyAndEnable,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryDark,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  'Verify & Enable',
                  style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildDisableSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.danger.withOpacity(0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.danger.withOpacity(0.3)),
          ),
          child: const Row(
            children: [
              Icon(Icons.warning_amber_rounded, color: AppTheme.danger),
              SizedBox(width: 12),
              Expanded(
                child: Text(
                  'Disabling 2FA will make your account less secure.',
                  style: TextStyle(color: AppTheme.danger, fontSize: 14),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),

        Text(
          'Enter your password:',
          style: TextStyle(fontSize: 14, color: AppTheme.text2(context)),
        ),
        const SizedBox(height: 8),
        TextField(
          controller: _passwordController,
          obscureText: true,
          decoration: InputDecoration(
            hintText: 'Password',
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        ),
        const SizedBox(height: 20),

        Text(
          'Enter your 2FA code:',
          style: TextStyle(fontSize: 14, color: AppTheme.text2(context)),
        ),
        const SizedBox(height: 8),
        TextField(
          controller: _codeController,
          keyboardType: TextInputType.number,
          maxLength: 6,
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.bold,
            letterSpacing: 8,
          ),
          decoration: InputDecoration(
            counterText: '',
            hintText: '000000',
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        ),
        const SizedBox(height: 24),

        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: () => setState(() => _isDisabling = false),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text('Cancel'),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: ElevatedButton(
                onPressed: _disable2FA,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.danger,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  'Disable 2FA',
                  style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  @override
  void dispose() {
    _codeController.dispose();
    _passwordController.dispose();
    super.dispose();
  }
}
