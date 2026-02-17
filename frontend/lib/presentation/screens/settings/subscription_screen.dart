import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/subscription_service.dart';
import '../../../l10n/generated/app_localizations.dart';

// Re-export for use in _buildCurrentPlanBanner

/// Subscription Screen - Manage subscription plans
class SubscriptionScreen extends StatefulWidget {
  const SubscriptionScreen({super.key});

  @override
  State<SubscriptionScreen> createState() => _SubscriptionScreenState();
}

class _SubscriptionScreenState extends State<SubscriptionScreen> {
  String _selectedPlan = 'premium';
  bool _isLoading = true;
  int _assessmentsUsed = 0;
  int _assessmentsLimit = 100;
  int _documentsUsed = 0;
  int _documentsLimit = 50;
  int _chatUsed = 0;
  int _chatLimit = 500;

  @override
  void initState() {
    super.initState();
    _loadSubscriptionData();
  }

  Future<void> _loadSubscriptionData() async {
    await subscriptionService.loadSubscription();
    await subscriptionService.loadLimits();
    if (mounted) {
      setState(() {
        _selectedPlan = subscriptionService.currentTier.value;
        _assessmentsUsed = subscriptionService.getRemainingUsage('assessments');
        _assessmentsLimit = 100; // Default, will be from limits
        _isLoading = false;
      });
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
          onPressed: () => context.go('/settings'),
        ),
        title: Text(
          l10n.subscription,
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.text1(context),
            fontFamily: 'Inter',
          ),
        ),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Current Plan Banner
            _buildCurrentPlanBanner(),
            const SizedBox(height: 24),

            // Usage Stats
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.surfaceOf(context),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.borderOf(context)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'This Month\'s Usage',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.text1(context),
                    ),
                  ),
                  const SizedBox(height: 20),
                  _buildUsageItem('Assessments', 45, 100, AppTheme.primaryDark),
                  const SizedBox(height: 16),
                  _buildUsageItem('Contract Generations', 28, 50, AppTheme.accent),
                  const SizedBox(height: 16),
                  _buildUsageItem('Engine Chat Messages', 156, 500, AppTheme.info),
                  const SizedBox(height: 16),
                  _buildUsageItem('Document Storage', 2.4, 10, AppTheme.warning, suffix: 'GB'),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Available Plans
            Text(
              'Available Plans',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: AppTheme.text1(context),
              ),
            ),
            const SizedBox(height: 16),

            // Trial Plan
            _buildPlanCard(
              planId: 'trial',
              name: 'Trial',
              price: 'Free',
              period: '',
              features: [
                'GO/NO-GO Decision only',
                '5 assessments/month',
                'Shareable links (24hr)',
                'Email support',
              ],
              isPopular: false,
              isCurrent: subscriptionService.isTrial,
            ),
            const SizedBox(height: 12),

            // Basic Plan
            _buildPlanCard(
              planId: 'basic',
              name: 'Basic',
              price: '\u20AC49',
              period: '/month',
              features: [
                'GO/NO-GO Decision',
                'Full AI Risk Analysis',
                'Underwriting Percentage',
                'Premium Pricing',
                '50 assessments/month',
                'Shareable links (24hr)',
                'Priority support',
              ],
              isPopular: true,
              isCurrent: subscriptionService.isBasic,
            ),
            const SizedBox(height: 12),

            // Premium Plan
            _buildPlanCard(
              planId: 'premium',
              name: 'Premium',
              price: '\u20AC149',
              period: '/month',
              features: [
                'Everything in Basic',
                'Sanctions Screening',
                'InstantRisk Engine Chat',
                'Document Generation',
                'Deep Analysis Mode',
                'Unlimited assessments',
                'Portfolio Analytics',
                '24/7 dedicated support',
              ],
              isPopular: false,
              isCurrent: subscriptionService.isPremium,
            ),
            const SizedBox(height: 24),

            // Billing History
            Text(
              'Billing History',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: AppTheme.text1(context),
              ),
            ),
            const SizedBox(height: 12),
            Container(
              decoration: BoxDecoration(
                color: AppTheme.surfaceOf(context),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.borderOf(context)),
              ),
              child: Column(
                children: [
                  _buildBillingItem('Jan 23, 2026', 'Professional Plan', '\u20AC79.00'),
                  Divider(height: 1, color: AppTheme.borderOf(context)),
                  _buildBillingItem('Dec 23, 2025', 'Professional Plan', '\u20AC79.00'),
                  Divider(height: 1, color: AppTheme.borderOf(context)),
                  _buildBillingItem('Nov 23, 2025', 'Professional Plan', '\u20AC79.00'),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Payment Method
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.surfaceOf(context),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.borderOf(context)),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryDark.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.credit_card,
                      color: AppTheme.primaryDark,
                      size: 24,
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Visa ending in 4242',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w500,
                            color: AppTheme.text1(context),
                          ),
                        ),
                        SizedBox(height: 2),
                        Text(
                          'Expires 12/2027',
                          style: TextStyle(
                            fontSize: 13,
                            color: AppTheme.text2(context),
                          ),
                        ),
                      ],
                    ),
                  ),
                  TextButton(
                    onPressed: () {
                      // TODO: Update payment method
                    },
                    child: const Text(
                      'Update',
                      style: TextStyle(
                        color: AppTheme.primaryDark,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 40),
          ],
        ),
      ),
    );
  }

  Widget _buildUsageItem(String label, double used, double total, Color color, {String suffix = ''}) {
    final percentage = used / total;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: TextStyle(
                fontSize: 14,
                color: AppTheme.text1(context),
              ),
            ),
            Text(
              '${used.toStringAsFixed(suffix.isNotEmpty ? 1 : 0)}$suffix / ${total.toStringAsFixed(0)}$suffix',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppTheme.text2(context),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: percentage,
            backgroundColor: AppTheme.borderOf(context),
            valueColor: AlwaysStoppedAnimation<Color>(color),
            minHeight: 8,
          ),
        ),
      ],
    );
  }

  Widget _buildPlanCard({
    required String planId,
    required String name,
    required String price,
    required String period,
    required List<String> features,
    required bool isPopular,
    bool isCurrent = false,
  }) {
    final isSelected = _selectedPlan == planId;

    return GestureDetector(
      onTap: () => setState(() => _selectedPlan = planId),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppTheme.surfaceOf(context),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isSelected ? AppTheme.primaryDark : AppTheme.borderOf(context),
            width: isSelected ? 2 : 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Text(
                      name,
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.text1(context),
                      ),
                    ),
                    if (isPopular) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: AppTheme.accent,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text(
                          'POPULAR',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ],
                    if (isCurrent) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: AppTheme.success.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text(
                          'CURRENT',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.success,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                Radio<String>(
                  value: planId,
                  groupValue: _selectedPlan,
                  onChanged: (value) {
                    if (value != null) {
                      setState(() => _selectedPlan = value);
                    }
                  },
                  activeColor: AppTheme.primaryDark,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  price,
                  style: TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.text1(context),
                  ),
                ),
                Text(
                  period,
                  style: TextStyle(
                    fontSize: 14,
                    color: AppTheme.text2(context),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            ...features.map((feature) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.check_circle,
                        color: AppTheme.success,
                        size: 18,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        feature,
                        style: TextStyle(
                          fontSize: 14,
                          color: AppTheme.text2(context),
                        ),
                      ),
                    ],
                  ),
                )),
            if (!isCurrent && isSelected) ...[
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () {
                    // TODO: Upgrade/downgrade plan
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryDark,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  child: Text(planId == 'basic' ? 'Downgrade' : 'Upgrade'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildBillingItem(String date, String description, String amount) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  description,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    color: AppTheme.text1(context),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  date,
                  style: TextStyle(
                    fontSize: 13,
                    color: AppTheme.text2(context),
                  ),
                ),
              ],
            ),
          ),
          Text(
            amount,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: AppTheme.text1(context),
            ),
          ),
          const SizedBox(width: 8),
          const Icon(
            Icons.download_outlined,
            color: AppTheme.primaryDark,
            size: 20,
          ),
        ],
      ),
    );
  }

  Widget _buildCurrentPlanBanner() {
    final tier = subscriptionService.currentTier;
    final isActive = subscriptionService.isActive;
    final expiresAt = subscriptionService.expiresAt;

    String planName;
    Color statusColor;
    String statusText;

    switch (tier) {
      case SubscriptionTier.premium:
        planName = 'Premium Plan';
        break;
      case SubscriptionTier.basic:
        planName = 'Basic Plan';
        break;
      case SubscriptionTier.trial:
      default:
        planName = 'Trial Plan';
    }

    if (isActive) {
      statusColor = AppTheme.success;
      statusText = 'ACTIVE';
    } else {
      statusColor = AppTheme.warning;
      statusText = 'PENDING';
    }

    String expiryText = 'No expiration set';
    if (expiresAt != null) {
      final months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      expiryText = 'Active until ${months[expiresAt.month - 1]} ${expiresAt.day}, ${expiresAt.year}';
    }

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: tier == SubscriptionTier.premium
              ? [Colors.deepPurple.shade600, Colors.deepPurple.shade800]
              : tier == SubscriptionTier.basic
                  ? [AppTheme.primaryDark, AppTheme.primaryLight]
                  : [Colors.grey.shade600, Colors.grey.shade800],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.2),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(
              tier == SubscriptionTier.premium
                  ? Icons.workspace_premium
                  : tier == SubscriptionTier.basic
                      ? Icons.verified
                      : Icons.hourglass_empty,
              color: Colors.white,
              size: 28,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  planName,
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  expiryText,
                  style: const TextStyle(
                    fontSize: 14,
                    color: Colors.white70,
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: statusColor,
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              statusText,
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: Colors.white,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
