import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/theme_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Appearance Screen - Theme and display settings
class AppearanceScreen extends ConsumerWidget {
  const AppearanceScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeState = ref.watch(themeProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: Icon(
            Icons.arrow_back_ios,
            color: isDark ? Colors.white : AppTheme.text1(context),
          ),
          onPressed: () => context.go('/settings'),
        ),
        title: Text(
          AppLocalizations.of(context).appearance,
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: isDark ? Colors.white : AppTheme.text1(context),
            fontFamily: 'Inter',
          ),
        ),
        centerTitle: true,
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'Theme',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: isDark ? Colors.white70 : AppTheme.text2(context),
              fontFamily: 'Inter',
            ),
          ),
          const SizedBox(height: 12),
          _buildThemeOption(
            context,
            ref,
            icon: Icons.light_mode_outlined,
            title: 'Light',
            subtitle: 'Always use light theme',
            value: 'light',
            selected: themeState.themeModeString,
            isDark: isDark,
          ),
          _buildThemeOption(
            context,
            ref,
            icon: Icons.dark_mode_outlined,
            title: 'Dark',
            subtitle: 'Always use dark theme',
            value: 'dark',
            selected: themeState.themeModeString,
            isDark: isDark,
          ),
          _buildThemeOption(
            context,
            ref,
            icon: Icons.settings_brightness_outlined,
            title: 'System',
            subtitle: 'Follow system setting',
            value: 'system',
            selected: themeState.themeModeString,
            isDark: isDark,
          ),
        ],
      ),
    );
  }

  Widget _buildThemeOption(
    BuildContext context,
    WidgetRef ref, {
    required IconData icon,
    required String title,
    required String subtitle,
    required String value,
    required String selected,
    required bool isDark,
  }) {
    final isSelected = value == selected;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isSelected
              ? AppTheme.primaryDark
              : (isDark ? Colors.white12 : AppTheme.borderOf(context)),
          width: isSelected ? 2 : 1,
        ),
      ),
      child: ListTile(
        leading: Icon(
          icon,
          color: isSelected
              ? AppTheme.primaryDark
              : (isDark ? Colors.white54 : AppTheme.text2(context)),
        ),
        title: Text(
          title,
          style: TextStyle(
            fontSize: 16,
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
            color: isDark ? Colors.white : AppTheme.text1(context),
            fontFamily: 'Inter',
          ),
        ),
        subtitle: Text(
          subtitle,
          style: TextStyle(
            fontSize: 13,
            color: isDark ? Colors.white54 : AppTheme.text2(context),
            fontFamily: 'Inter',
          ),
        ),
        trailing: isSelected
            ? const Icon(Icons.check_circle, color: AppTheme.primaryDark)
            : null,
        onTap: () {
          ref.read(themeProvider.notifier).setThemeMode(value);
        },
      ),
    );
  }
}
