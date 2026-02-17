import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';

/// Security Settings Screen - Hub for all security options
/// Password change, active sessions, and 2FA settings
class SecurityScreen extends StatefulWidget {
  const SecurityScreen({super.key});

  @override
  State<SecurityScreen> createState() => _SecurityScreenState();
}

class _SecurityScreenState extends State<SecurityScreen> {
  bool _isLoading = true;
  bool _is2FAEnabled = false;
  int _activeSessions = 1;

  @override
  void initState() {
    super.initState();
    _loadSecurityStatus();
  }

  Future<void> _loadSecurityStatus() async {
    setState(() => _isLoading = true);
    try {
      final status = await authService.get2FAStatus();
      setState(() {
        _is2FAEnabled = status['enabled'] ?? false;
      });
      // TODO: Load active sessions count from API
    } catch (e) {
      debugPrint('Error loading security status: $e');
    } finally {
      setState(() => _isLoading = false);
    }
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
          'Security',
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
                  // Security Overview Card
                  _buildSecurityOverview(),
                  const SizedBox(height: 24),

                  // Security Options
                  Text(
                    'SECURITY OPTIONS',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.text2(context),
                      letterSpacing: 1,
                    ),
                  ),
                  const SizedBox(height: 12),

                  // Password
                  _buildSecurityOption(
                    icon: Icons.lock_outline,
                    title: 'Change Password',
                    subtitle: 'Update your account password',
                    onTap: () => context.push('/settings/security/password'),
                  ),
                  const SizedBox(height: 12),

                  // Two-Factor Authentication
                  _buildSecurityOption(
                    icon: Icons.security,
                    title: 'Two-Factor Authentication',
                    subtitle: _is2FAEnabled ? 'Enabled' : 'Not enabled',
                    trailing: _build2FABadge(),
                    onTap: () => context.push('/settings/security/2fa'),
                  ),
                  const SizedBox(height: 12),

                  // Active Sessions
                  _buildSecurityOption(
                    icon: Icons.devices,
                    title: 'Active Sessions',
                    subtitle: '$_activeSessions device${_activeSessions > 1 ? 's' : ''} logged in',
                    onTap: () => context.push('/settings/security/sessions'),
                  ),
                  const SizedBox(height: 32),

                  // Security Tips
                  _buildSecurityTips(),
                ],
              ),
            ),
    );
  }

  Widget _buildSecurityOverview() {
    final bool isSecure = _is2FAEnabled;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: isSecure
              ? [AppTheme.success.withOpacity(0.1), AppTheme.success.withOpacity(0.05)]
              : [AppTheme.warning.withOpacity(0.1), AppTheme.warning.withOpacity(0.05)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isSecure ? AppTheme.success.withOpacity(0.3) : AppTheme.warning.withOpacity(0.3),
        ),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: isSecure ? AppTheme.success.withOpacity(0.2) : AppTheme.warning.withOpacity(0.2),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(
              isSecure ? Icons.verified_user : Icons.shield_outlined,
              color: isSecure ? AppTheme.success : AppTheme.warning,
              size: 32,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  isSecure ? 'Account Secured' : 'Improve Security',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: isSecure ? AppTheme.success : AppTheme.warning,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  isSecure
                      ? 'Your account is protected with 2FA'
                      : 'Enable 2FA to secure your account',
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

  Widget _buildSecurityOption({
    required IconData icon,
    required String title,
    required String subtitle,
    Widget? trailing,
    required VoidCallback onTap,
  }) {
    return Material(
      color: AppTheme.surfaceOf(context),
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.borderOf(context)),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppTheme.primaryDark.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: AppTheme.primaryDark, size: 22),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w500,
                        color: AppTheme.text1(context),
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: TextStyle(
                        fontSize: 13,
                        color: AppTheme.text2(context),
                      ),
                    ),
                  ],
                ),
              ),
              if (trailing != null) ...[
                trailing,
                const SizedBox(width: 8),
              ],
              Icon(
                Icons.arrow_forward_ios,
                color: AppTheme.textH(context),
                size: 16,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _build2FABadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: _is2FAEnabled ? AppTheme.success : AppTheme.warning,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        _is2FAEnabled ? 'ON' : 'OFF',
        style: const TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: Colors.white,
        ),
      ),
    );
  }

  Widget _buildSecurityTips() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.tips_and_updates, color: AppTheme.accent, size: 20),
              SizedBox(width: 8),
              Text(
                'Security Tips',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.text1(context),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildTip('Use a strong, unique password'),
          _buildTip('Enable two-factor authentication'),
          _buildTip('Review active sessions regularly'),
          _buildTip('Never share your login credentials'),
        ],
      ),
    );
  }

  Widget _buildTip(String text) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          const Icon(Icons.check_circle, color: AppTheme.success, size: 16),
          const SizedBox(width: 8),
          Text(
            text,
            style: TextStyle(fontSize: 13, color: AppTheme.text2(context)),
          ),
        ],
      ),
    );
  }
}
