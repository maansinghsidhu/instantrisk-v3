import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/subscription_service.dart';

/// Portfolio Screen - Overview of insurance portfolio analytics
class PortfolioScreen extends StatelessWidget {
  const PortfolioScreen({super.key});

  bool get _hasAccess => subscriptionService.isBasic || subscriptionService.isPremium;

  @override
  Widget build(BuildContext context) {
    // Check if user has Basic+ access for analytics
    if (!_hasAccess) {
      return Scaffold(
        backgroundColor: AppTheme.bg(context),
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(32.0),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryDark.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: const Icon(Icons.pie_chart_outline, size: 64, color: AppTheme.primaryDark),
                  ),
                  const SizedBox(height: 24),
                  Text(
                    'Portfolio Analytics',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: AppTheme.text1(context)),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'View your portfolio distribution, risk breakdown, and performance metrics.',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 15, color: AppTheme.text2(context), height: 1.5),
                  ),
                  const SizedBox(height: 32),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryDark.withValues(alpha: 0.05),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppTheme.primaryDark.withValues(alpha: 0.2)),
                    ),
                    child: Column(
                      children: [
                        Icon(Icons.workspace_premium, color: AppTheme.primaryDark, size: 32),
                        SizedBox(height: 8),
                        Text('Basic+ Feature', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: AppTheme.primaryDark)),
                        SizedBox(height: 4),
                        Text('Upgrade to Basic to access portfolio analytics', textAlign: TextAlign.center, style: TextStyle(fontSize: 13, color: AppTheme.text2(context))),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: () => context.go('/subscription'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primaryDark,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      child: const Text('Upgrade to Basic', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            // Header
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.all(20.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Portfolio Analytics',
                          style: TextStyle(
                            fontSize: 28,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.text1(context),
                            fontFamily: 'Inter',
                          ),
                        ),
                        IconButton(
                          onPressed: () => context.go('/analytics/performance'),
                          icon: const Icon(
                            Icons.bar_chart_outlined,
                            color: AppTheme.primaryDark,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'January 2026',
                      style: TextStyle(
                        fontSize: 14,
                        color: AppTheme.text2(context),
                        fontFamily: 'Inter',
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Portfolio Value Card
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [AppTheme.primaryDark, AppTheme.primaryLight],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Total Portfolio Value',
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.white70,
                          fontFamily: 'Inter',
                        ),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        '\u20AC4.2M',
                        style: TextStyle(
                          fontSize: 36,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                          fontFamily: 'Inter',
                        ),
                      ),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: AppTheme.success.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Row(
                              children: const [
                                Icon(Icons.trending_up, color: Colors.white, size: 16),
                                SizedBox(width: 4),
                                Text(
                                  '+12.5%',
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    color: Colors.white,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 8),
                          const Text(
                            'vs last month',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.white70,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 24)),

            // Quick Stats
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: Row(
                  children: [
                    Expanded(
                      child: _buildStatCard(context,
                        title: 'Active Policies',
                        value: '156',
                        icon: Icons.policy_outlined,
                        color: AppTheme.primaryDark,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _buildStatCard(context,
                        title: 'Total Premium',
                        value: '\u20AC890k',
                        icon: Icons.payments_outlined,
                        color: AppTheme.success,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _buildStatCard(context,
                        title: 'Loss Ratio',
                        value: '42%',
                        icon: Icons.pie_chart_outline,
                        color: AppTheme.warning,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 24)),

            // Portfolio Distribution
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: Container(
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
                        'Portfolio Distribution',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text1(context),
                          fontFamily: 'Inter',
                        ),
                      ),
                      const SizedBox(height: 20),
                      _buildDistributionItem(context, 'Property', 0.45, AppTheme.primaryDark, '\u20AC1.89M'),
                      _buildDistributionItem(context, 'Liability', 0.25, AppTheme.accent, '\u20AC1.05M'),
                      _buildDistributionItem(context, 'Motor', 0.18, AppTheme.warning, '\u20AC756k'),
                      _buildDistributionItem(context, 'Other', 0.12, AppTheme.info, '\u20AC504k'),
                    ],
                  ),
                ),
              ),
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 24)),

            // Recent Activity Section
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Recent Activity',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.text1(context),
                        fontFamily: 'Inter',
                      ),
                    ),
                    TextButton(
                      onPressed: () {
                        // View all activity
                      },
                      child: const Text(
                        'View All',
                        style: TextStyle(
                          color: AppTheme.primaryDark,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Activity List
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
                  _buildActivityItem(
                    context,
                    'New policy issued',
                    'Property Insurance - Acme Corp',
                    Icons.add_circle_outline,
                    AppTheme.success,
                    '2h ago',
                  ),
                  _buildActivityItem(
                    context,
                    'Claim submitted',
                    'Motor Fleet - Logistics Pro',
                    Icons.warning_amber_outlined,
                    AppTheme.warning,
                    '5h ago',
                  ),
                  _buildActivityItem(
                    context,
                    'Policy renewed',
                    'Liability - Tech Solutions',
                    Icons.refresh_outlined,
                    AppTheme.info,
                    '1d ago',
                  ),
                  _buildActivityItem(
                    context,
                    'Assessment completed',
                    'Commercial - Retail Giants',
                    Icons.check_circle_outline,
                    AppTheme.success,
                    '2d ago',
                  ),
                ]),
              ),
            ),

            const SliverToBoxAdapter(child: SizedBox(height: 100)),
          ],
        ),
      ),
    );
  }

  Widget _buildStatCard(BuildContext context, {
    required String title,
    required String value,
    required IconData icon,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: color, size: 18),
          ),
          const SizedBox(height: 12),
          Text(
            value,
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: AppTheme.text1(context),
              fontFamily: 'Inter',
            ),
          ),
          const SizedBox(height: 2),
          Text(
            title,
            style: TextStyle(
              fontSize: 11,
              color: AppTheme.text2(context),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDistributionItem(BuildContext context, String label, double percentage, Color color, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    width: 12,
                    height: 12,
                    decoration: BoxDecoration(
                      color: color,
                      borderRadius: BorderRadius.circular(3),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    label,
                    style: TextStyle(
                      fontSize: 14,
                      color: AppTheme.text1(context),
                    ),
                  ),
                ],
              ),
              Row(
                children: [
                  Text(
                    value,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.text1(context),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '${(percentage * 100).toInt()}%',
                    style: TextStyle(
                      fontSize: 12,
                      color: AppTheme.text2(context),
                    ),
                  ),
                ],
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
      ),
    );
  }

  Widget _buildActivityItem(
    BuildContext context,
    String title,
    String subtitle,
    IconData icon,
    Color color,
    String time,
  ) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.text1(context),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: TextStyle(
                    fontSize: 12,
                    color: AppTheme.text2(context),
                  ),
                ),
              ],
            ),
          ),
          Text(
            time,
            style: TextStyle(
              fontSize: 12,
              color: AppTheme.textH(context),
            ),
          ),
        ],
      ),
    );
  }
}
