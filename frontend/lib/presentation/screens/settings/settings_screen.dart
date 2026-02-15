import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/documents_prefetch_service.dart';
import '../../../core/services/language_service.dart';
import '../../../core/services/theme_service.dart';
import '../../../core/services/subscription_service.dart';
import '../../../core/models/language_model.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../widgets/common/screen_header.dart';

/// Settings Screen - App settings and account management
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  /// Check if current user is an admin
  bool _isAdmin() {
    final user = authService.user;
    if (user == null) return false;
    final role = user['role']?.toString().toLowerCase();
    return role == 'admin' || role == 'superadmin';
  }

  /// Get current theme mode label
  String _getThemeModeLabel(WidgetRef ref) {
    final mode = ref.watch(themeProvider).themeModeString;
    switch (mode) {
      case 'light':
        return 'Light mode';
      case 'dark':
        return 'Dark mode';
      default:
        return 'System default';
    }
  }

  /// Get badge text for pending approvals (only shown for admins)
  String? _getPendingApprovalsBadge() {
    // In a real implementation, this would check actual pending count
    // For now, just indicate there might be pending items
    return null; // Could return 'NEW' or a count
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final languageState = ref.watch(languageProvider);
    final currentLanguageInfo = getLanguageInfo(languageState.languageCode);

    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              ScreenHeader(
                title: l10n.settings,
                subtitle: 'Account & preferences',
              ),

              // Profile Card
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceOf(context),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.borderOf(context)),
                  ),
                  child: InkWell(
                    onTap: () => context.go('/settings/profile'),
                    borderRadius: BorderRadius.circular(16),
                    child: Row(
                      children: [
                        CircleAvatar(
                          radius: 30,
                          backgroundColor: AppTheme.primaryDark,
                          child: const Text(
                            'JD',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 20,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'John Doe',
                                style: TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.w600,
                                  color: AppTheme.text1(context),
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'john.doe@company.com',
                                style: TextStyle(
                                  fontSize: 14,
                                  color: AppTheme.text2(context),
                                ),
                              ),
                            ],
                          ),
                        ),
                        Icon(
                          Icons.arrow_forward_ios,
                          color: AppTheme.textH(context),
                          size: 18,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Account Section
              _buildSectionTitle(context, l10n.account),
              _buildSettingsGroup(context, [
                _buildSettingsItem(
                  context,
                  icon: Icons.person_outline,
                  title: l10n.profile,
                  subtitle: l10n.profileSubtitle,
                  onTap: () => context.go('/settings/profile'),
                ),
                _buildSettingsItem(
                  context,
                  icon: Icons.workspace_premium_outlined,
                  title: l10n.subscription,
                  subtitle: l10n.subscriptionPlan,
                  badge: 'PRO',
                  onTap: () => context.go('/settings/subscription'),
                ),
                _buildSettingsItem(
                  context,
                  icon: Icons.security_outlined,
                  title: l10n.security,
                  subtitle: 'Password, 2FA & sessions',
                  onTap: () => context.go('/settings/security'),
                ),
              ]),
              const SizedBox(height: 24),

              // Team & Admin Section
              _buildSectionTitle(context, l10n.teamAdmin),
              _buildSettingsGroup(context, [
                _buildSettingsItem(
                  context,
                  icon: Icons.groups_outlined,
                  title: l10n.teamManagement,
                  subtitle: l10n.teamManagementSubtitle,
                  onTap: () => context.go('/settings/teams'),
                ),
                _buildSettingsItem(
                  context,
                  icon: Icons.admin_panel_settings_outlined,
                  title: l10n.rolesPermissions,
                  subtitle: l10n.rolesPermissionsSubtitle,
                  onTap: () => context.go('/settings/teams'),
                ),
                // Admin-only: User Approvals
                if (_isAdmin()) ...[
                  _buildSettingsItem(
                    context,
                    icon: Icons.how_to_reg_outlined,
                    title: 'User Approvals',
                    subtitle: 'Approve or reject new user registrations',
                    badge: _getPendingApprovalsBadge(),
                    onTap: () => context.go('/settings/approvals'),
                  ),
                ],
              ]),
              const SizedBox(height: 24),

              // App Settings Section
              _buildSectionTitle(context, l10n.appSettings),
              _buildSettingsGroup(context, [
                _buildSettingsItem(
                  context,
                  icon: Icons.language_outlined,
                  title: l10n.language,
                  subtitle: currentLanguageInfo.name,
                  onTap: () => context.go('/settings/language'),
                ),
                _buildSettingsItem(
                  context,
                  icon: Icons.notifications_outlined,
                  title: l10n.notifications,
                  subtitle: l10n.notificationsSubtitle,
                  onTap: () {
                    // TODO: Navigate to notification settings
                  },
                ),
                _buildSettingsItem(
                  context,
                  icon: Icons.palette_outlined,
                  title: l10n.appearance,
                  subtitle: _getThemeModeLabel(ref),
                  onTap: () {
                    context.push('/settings/appearance');
                  },
                ),
              ]),
              const SizedBox(height: 24),

              // Support Section
              _buildSectionTitle(context, l10n.support),
              _buildSettingsGroup(context, [
                _buildSettingsItem(
                  context,
                  icon: Icons.help_outline,
                  title: l10n.helpCenter,
                  subtitle: l10n.helpCenterSubtitle,
                  onTap: () {
                    // TODO: Navigate to help center
                  },
                ),
                _buildSettingsItem(
                  context,
                  icon: Icons.chat_bubble_outline,
                  title: l10n.contactSupport,
                  subtitle: l10n.contactSupportSubtitle,
                  onTap: () {
                    // TODO: Navigate to contact support
                  },
                ),
                _buildSettingsItem(
                  context,
                  icon: Icons.bug_report_outlined,
                  title: l10n.reportBug,
                  subtitle: l10n.reportBugSubtitle,
                  onTap: () {
                    // TODO: Navigate to bug report
                  },
                ),
              ]),
              const SizedBox(height: 24),

              // About Section
              _buildSectionTitle(context, l10n.about),
              _buildSettingsGroup(context, [
                _buildSettingsItem(
                  context,
                  icon: Icons.info_outline,
                  title: l10n.aboutInstantRisk,
                  subtitle: 'Version 5.0.0 - Enterprise Security',
                  onTap: () {
                    // TODO: Show about dialog
                  },
                ),
                _buildSettingsItem(
                  context,
                  icon: Icons.description_outlined,
                  title: l10n.termsOfService,
                  onTap: () {
                    // TODO: Show terms
                  },
                ),
                _buildSettingsItem(
                  context,
                  icon: Icons.privacy_tip_outlined,
                  title: l10n.privacyPolicy,
                  onTap: () {
                    // TODO: Show privacy policy
                  },
                ),
              ]),
              const SizedBox(height: 24),

              // Logout Button
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: () {
                      _showLogoutDialog(context, l10n);
                    },
                    icon: const Icon(Icons.logout, color: AppTheme.danger),
                    label: Text(
                      l10n.logOut,
                      style: const TextStyle(color: AppTheme.danger),
                    ),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      side: const BorderSide(color: AppTheme.danger),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 40),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSectionTitle(BuildContext context, String title) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20.0),
      child: Text(
        title,
        style: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: AppTheme.text2(context),
          letterSpacing: 0.5,
        ),
      ),
    );
  }

  Widget _buildSettingsGroup(BuildContext context, List<Widget> children) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
      child: Container(
        decoration: BoxDecoration(
          color: AppTheme.surfaceOf(context),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppTheme.borderOf(context)),
        ),
        child: Column(
          children: children,
        ),
      ),
    );
  }

  Widget _buildSettingsItem(
    BuildContext context, {
    required IconData icon,
    required String title,
    String? subtitle,
    String? badge,
    required VoidCallback onTap,
  }) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: AppTheme.primaryDark.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: AppTheme.primaryDark, size: 20),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          title,
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w500,
                            color: AppTheme.text1(context),
                          ),
                        ),
                        if (badge != null) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: AppTheme.accent,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              badge,
                              style: const TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                                color: Colors.white,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    if (subtitle != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        subtitle,
                        style: TextStyle(
                          fontSize: 13,
                          color: AppTheme.text2(context),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
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

  void _showLogoutDialog(BuildContext context, AppLocalizations l10n) {
    final navigator = GoRouter.of(context);

    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(l10n.logOut),
        content: Text(l10n.logOutConfirmation),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: Text(
              l10n.cancel,
              style: TextStyle(color: AppTheme.text2(context)),
            ),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(dialogContext);
              documentsPrefetchService.clearCache(); // Clear documents cache
              await authService.logout();
              // Navigate using captured navigator
              navigator.go('/welcome');
            },
            child: Text(
              l10n.logOut,
              style: const TextStyle(color: AppTheme.danger),
            ),
          ),
        ],
      ),
    );
  }
}
