import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/services/subscription_service.dart';

/// Widget that gates access to features based on subscription tier
class FeatureGate extends StatelessWidget {
  /// The feature name to check access for
  final String featureName;

  /// The child widget to show if user has access
  final Widget child;

  /// Optional widget to show when feature is locked
  final Widget? lockedWidget;

  /// Whether to show a simple lock icon overlay instead of replacing content
  final bool showOverlay;

  /// Callback when user taps on locked feature
  final VoidCallback? onLockedTap;

  const FeatureGate({
    super.key,
    required this.featureName,
    required this.child,
    this.lockedWidget,
    this.showOverlay = false,
    this.onLockedTap,
  });

  @override
  Widget build(BuildContext context) {
    final hasAccess = subscriptionService.hasFeature(featureName);

    if (hasAccess) {
      return child;
    }

    if (lockedWidget != null) {
      return lockedWidget!;
    }

    if (showOverlay) {
      return Stack(
        children: [
          // Original content with opacity
          Opacity(
            opacity: 0.5,
            child: AbsorbPointer(child: child),
          ),
          // Lock overlay
          Positioned.fill(
            child: GestureDetector(
              onTap: onLockedTap ?? () => _showUpgradeDialog(context),
              child: Container(
                color: Colors.transparent,
                child: Center(
                  child: Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.black54,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.lock, color: Colors.white, size: 20),
                        SizedBox(width: 8),
                        Text(
                          'Premium',
                          style: TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      );
    }

    // Default locked widget
    return PremiumLockedBanner(
      featureName: featureName,
      onUpgrade: () => _showUpgradeDialog(context),
    );
  }

  void _showUpgradeDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => UpgradeDialog(featureName: featureName),
    );
  }
}

/// Banner shown when a feature is locked
class PremiumLockedBanner extends StatelessWidget {
  final String featureName;
  final VoidCallback? onUpgrade;

  const PremiumLockedBanner({
    super.key,
    required this.featureName,
    this.onUpgrade,
  });

  @override
  Widget build(BuildContext context) {
    final featureInfo = subscriptionService.getFeatureInfo(featureName);
    final displayName = featureInfo?.name ?? _formatFeatureName(featureName);

    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Colors.deepPurple.shade400,
            Colors.deepPurple.shade700,
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.deepPurple.withOpacity(0.3),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.workspace_premium,
            color: Colors.amber,
            size: 48,
          ),
          const SizedBox(height: 16),
          Text(
            displayName,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Text(
            featureInfo?.description ?? 'This feature requires a Premium subscription',
            style: const TextStyle(
              color: Colors.white70,
              fontSize: 14,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 20),
          ElevatedButton.icon(
            onPressed: onUpgrade,
            icon: const Icon(Icons.upgrade),
            label: const Text('Upgrade to Premium'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.amber,
              foregroundColor: Colors.black87,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(30),
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _formatFeatureName(String name) {
    return name
        .replaceAll('_', ' ')
        .split(' ')
        .map((word) => word.isNotEmpty
            ? '${word[0].toUpperCase()}${word.substring(1)}'
            : '')
        .join(' ');
  }
}

/// Dialog shown when user tries to access a locked feature
class UpgradeDialog extends StatelessWidget {
  final String featureName;

  const UpgradeDialog({
    super.key,
    required this.featureName,
  });

  @override
  Widget build(BuildContext context) {
    final featureInfo = subscriptionService.getFeatureInfo(featureName);

    return AlertDialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      title: Row(
        children: [
          const Icon(Icons.workspace_premium, color: Colors.amber, size: 28),
          const SizedBox(width: 12),
          const Expanded(
            child: Text('Upgrade to Premium'),
          ),
        ],
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            featureInfo?.description ??
                'This feature is available with a Premium subscription.',
            style: const TextStyle(fontSize: 16),
          ),
          const SizedBox(height: 20),
          const Text(
            'Premium features include:',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          _buildFeatureRow(Icons.chat, 'InstantRisk Engine Chat'),
          _buildFeatureRow(Icons.description, 'Document Generation'),
          _buildFeatureRow(Icons.psychology, 'Deep Analysis Mode'),
          _buildFeatureRow(Icons.insights, 'Advanced Analytics'),
          _buildFeatureRow(Icons.storage, '100 Monthly Assessments'),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Maybe Later'),
        ),
        ElevatedButton(
          onPressed: () {
            Navigator.of(context).pop();
            context.push('/settings/subscription');
          },
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.deepPurple,
            foregroundColor: Colors.white,
          ),
          child: const Text('View Plans'),
        ),
      ],
    );
  }

  Widget _buildFeatureRow(IconData icon, String text) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(icon, size: 18, color: Colors.deepPurple),
          const SizedBox(width: 8),
          Text(text),
        ],
      ),
    );
  }
}

/// Small badge to indicate Premium feature
class PremiumBadge extends StatelessWidget {
  final bool small;

  const PremiumBadge({super.key, this.small = false});

  @override
  Widget build(BuildContext context) {
    if (small) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: BoxDecoration(
          color: Colors.amber,
          borderRadius: BorderRadius.circular(4),
        ),
        child: const Text(
          'PRO',
          style: TextStyle(
            color: Colors.black87,
            fontSize: 10,
            fontWeight: FontWeight.bold,
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Colors.amber, Colors.orange],
        ),
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.workspace_premium, size: 14, color: Colors.white),
          SizedBox(width: 4),
          Text(
            'Premium',
            style: TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}

/// Lock icon to indicate a locked feature
class FeatureLockIcon extends StatelessWidget {
  final String? tooltip;
  final double size;

  const FeatureLockIcon({
    super.key,
    this.tooltip,
    this.size = 16,
  });

  @override
  Widget build(BuildContext context) {
    final icon = Icon(
      Icons.lock,
      size: size,
      color: Colors.grey,
    );

    if (tooltip != null) {
      return Tooltip(
        message: tooltip!,
        child: icon,
      );
    }

    return icon;
  }
}
