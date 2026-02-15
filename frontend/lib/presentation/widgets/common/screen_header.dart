import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';

/// Unified corporate screen header — clean, minimal, modern.
class ScreenHeader extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget? leading;
  final List<Widget>? actions;
  final String? badge;
  final Color? badgeColor;
  final Widget? customTitle;

  const ScreenHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.leading,
    this.actions,
    this.badge,
    this.badgeColor,
    this.customTitle,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        border: Border(
          bottom: BorderSide(
            color: AppTheme.borderOf(context).withOpacity(0.5),
            width: 0.5,
          ),
        ),
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  if (leading != null) ...[
                    leading!,
                    const SizedBox(width: 12),
                  ],
                  Expanded(
                    child: customTitle ?? _buildTitle(),
                  ),
                  if (actions != null) ...actions!,
                ],
              ),
              if (badge != null) ...[
                const SizedBox(height: 10),
                _buildBadge(),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTitle() {
    return Builder(builder: (context) => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: AppTheme.text1(context),
            fontFamily: 'Inter',
            letterSpacing: -0.4,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        if (subtitle != null) ...[
          const SizedBox(height: 2),
          Text(
            subtitle!,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w400,
              color: AppTheme.text2(context),
              fontFamily: 'Inter',
            ),
          ),
        ],
      ],
    ));
  }

  Widget _buildBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: (badgeColor ?? AppTheme.success).withOpacity(0.08),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              color: badgeColor ?? AppTheme.success,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 6),
          Text(
            badge!,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w500,
              color: badgeColor ?? AppTheme.success,
              fontFamily: 'Inter',
            ),
          ),
        ],
      ),
    );
  }
}
