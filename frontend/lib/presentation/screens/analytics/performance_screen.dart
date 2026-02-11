import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/subscription_service.dart';

/// Performance Screen - Detailed performance metrics and trends
class PerformanceScreen extends StatefulWidget {
  const PerformanceScreen({super.key});

  @override
  State<PerformanceScreen> createState() => _PerformanceScreenState();
}

class _PerformanceScreenState extends State<PerformanceScreen> {
  String _selectedPeriod = 'Month';
  final List<String> _periods = ['Week', 'Month', 'Quarter', 'Year'];

  bool get _hasAccess => subscriptionService.isBasic || subscriptionService.isPremium;

  @override
  Widget build(BuildContext context) {
    // Check if user has Basic+ access for analytics
    if (!_hasAccess) {
      return Scaffold(
        backgroundColor: AppTheme.background,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios, color: AppTheme.textPrimary),
            onPressed: () => context.go('/analytics'),
          ),
          title: const Text(
            'Performance',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: AppTheme.textPrimary),
          ),
          centerTitle: true,
        ),
        body: Center(
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
                  child: const Icon(Icons.analytics_outlined, size: 64, color: AppTheme.primaryDark),
                ),
                const SizedBox(height: 24),
                const Text(
                  'Performance Analytics',
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: AppTheme.textPrimary),
                ),
                const SizedBox(height: 12),
                const Text(
                  'View detailed performance metrics, trends, and portfolio insights.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 15, color: AppTheme.textSecondary, height: 1.5),
                ),
                const SizedBox(height: 32),
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryDark.withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.primaryDark.withValues(alpha: 0.2)),
                  ),
                  child: const Column(
                    children: [
                      Icon(Icons.workspace_premium, color: AppTheme.primaryDark, size: 32),
                      SizedBox(height: 8),
                      Text('Basic+ Feature', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: AppTheme.primaryDark)),
                      SizedBox(height: 4),
                      Text('Upgrade to Basic to access performance analytics', textAlign: TextAlign.center, style: TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
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
      );
    }

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppTheme.textPrimary),
          onPressed: () => context.go('/analytics'),
        ),
        title: const Text(
          'Performance',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
            fontFamily: 'Inter',
          ),
        ),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.download_outlined, color: AppTheme.textPrimary),
            onPressed: () {
              // Export report
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Period Selector
            Container(
              padding: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.border),
              ),
              child: Row(
                children: _periods.map((period) {
                  final isSelected = period == _selectedPeriod;
                  return Expanded(
                    child: GestureDetector(
                      onTap: () => setState(() => _selectedPeriod = period),
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        decoration: BoxDecoration(
                          color: isSelected ? AppTheme.primaryDark : Colors.transparent,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Center(
                          child: Text(
                            period,
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              color: isSelected ? Colors.white : AppTheme.textSecondary,
                            ),
                          ),
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
            const SizedBox(height: 24),

            // Key Metrics Row
            Row(
              children: [
                Expanded(
                  child: _buildMetricCard(
                    title: 'Approval Rate',
                    value: '78%',
                    change: '+5%',
                    isPositive: true,
                    icon: Icons.check_circle_outline,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _buildMetricCard(
                    title: 'Avg Processing',
                    value: '2.4h',
                    change: '-18%',
                    isPositive: true,
                    icon: Icons.schedule_outlined,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _buildMetricCard(
                    title: 'Avg Premium',
                    value: '\u20AC38k',
                    change: '+12%',
                    isPositive: true,
                    icon: Icons.euro_outlined,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _buildMetricCard(
                    title: 'Claims Ratio',
                    value: '32%',
                    change: '-3%',
                    isPositive: true,
                    icon: Icons.trending_down_outlined,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),

            // Assessment Trends Chart
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: const [
                      Text(
                        'Assessment Trends',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                          fontFamily: 'Inter',
                        ),
                      ),
                      Text(
                        '156 total',
                        style: TextStyle(
                          fontSize: 14,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),

                  // Chart placeholder
                  SizedBox(
                    height: 200,
                    child: CustomPaint(
                      size: const Size(double.infinity, 200),
                      painter: _TrendChartPainter(),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Legend
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      _buildLegendItem('GO', AppTheme.success),
                      const SizedBox(width: 24),
                      _buildLegendItem('NO-GO', AppTheme.danger),
                      const SizedBox(width: 24),
                      _buildLegendItem('REFER', AppTheme.warning),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Risk Distribution
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Risk Score Distribution',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimary,
                      fontFamily: 'Inter',
                    ),
                  ),
                  const SizedBox(height: 20),
                  _buildDistributionBar('0-40 (High Risk)', 0.15, AppTheme.danger),
                  _buildDistributionBar('41-60 (Medium)', 0.25, AppTheme.warning),
                  _buildDistributionBar('61-80 (Low Risk)', 0.35, AppTheme.info),
                  _buildDistributionBar('81-100 (Very Low)', 0.25, AppTheme.success),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Premium Analysis
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Premium Analysis',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimary,
                      fontFamily: 'Inter',
                    ),
                  ),
                  const SizedBox(height: 20),
                  _buildPremiumRow('Total Written Premium', '\u20AC890,000'),
                  _buildPremiumRow('Average Premium', '\u20AC38,200'),
                  _buildPremiumRow('Highest Premium', '\u20AC156,000'),
                  _buildPremiumRow('Lowest Premium', '\u20AC8,500'),
                  const SizedBox(height: 16),
                  const Divider(color: AppTheme.border),
                  const SizedBox(height: 16),
                  _buildPremiumRow('Total Claims Paid', '\u20AC285,000', isNegative: true),
                  _buildPremiumRow('Loss Ratio', '32%'),
                  _buildPremiumRow('Net Underwriting Result', '\u20AC605,000', isPositive: true),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Top Performing Categories
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Top Performing Categories',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimary,
                      fontFamily: 'Inter',
                    ),
                  ),
                  const SizedBox(height: 16),
                  _buildCategoryItem(1, 'Property Insurance', '92% approval', '+15% profit'),
                  _buildCategoryItem(2, 'Commercial Liability', '85% approval', '+12% profit'),
                  _buildCategoryItem(3, 'Motor Fleet', '78% approval', '+8% profit'),
                  _buildCategoryItem(4, 'Professional Indemnity', '72% approval', '+6% profit'),
                ],
              ),
            ),
            const SizedBox(height: 40),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricCard({
    required String title,
    required String value,
    required String change,
    required bool isPositive,
    required IconData icon,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppTheme.primaryDark.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: AppTheme.primaryDark, size: 18),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: (isPositive ? AppTheme.success : AppTheme.danger).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  change,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: isPositive ? AppTheme.success : AppTheme.danger,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            value,
            style: const TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
              fontFamily: 'Inter',
            ),
          ),
          const SizedBox(height: 4),
          Text(
            title,
            style: const TextStyle(
              fontSize: 12,
              color: AppTheme.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLegendItem(String label, Color color) {
    return Row(
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(3),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: const TextStyle(
            fontSize: 12,
            color: AppTheme.textSecondary,
          ),
        ),
      ],
    );
  }

  Widget _buildDistributionBar(String label, double value, Color color) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                label,
                style: const TextStyle(
                  fontSize: 13,
                  color: AppTheme.textPrimary,
                ),
              ),
              Text(
                '${(value * 100).toInt()}%',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: color,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: value,
              backgroundColor: AppTheme.border,
              valueColor: AlwaysStoppedAnimation<Color>(color),
              minHeight: 8,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPremiumRow(String label, String value, {bool isPositive = false, bool isNegative = false}) {
    Color valueColor = AppTheme.textPrimary;
    if (isPositive) valueColor = AppTheme.success;
    if (isNegative) valueColor = AppTheme.danger;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 14,
              color: AppTheme.textSecondary,
            ),
          ),
          Text(
            value,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: valueColor,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCategoryItem(int rank, String name, String approval, String profit) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: rank == 1
                  ? AppTheme.warning
                  : rank == 2
                      ? AppTheme.textHint
                      : rank == 3
                          ? const Color(0xFFCD7F32)
                          : AppTheme.border,
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Text(
                '$rank',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: rank <= 3 ? Colors.white : AppTheme.textSecondary,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              name,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: AppTheme.textPrimary,
              ),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                approval,
                style: const TextStyle(
                  fontSize: 12,
                  color: AppTheme.textSecondary,
                ),
              ),
              Text(
                profit,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.success,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// Custom painter for the trend chart
class _TrendChartPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;

    // Draw grid
    final gridPaint = Paint()
      ..color = AppTheme.border
      ..strokeWidth = 1;

    for (int i = 0; i <= 4; i++) {
      final y = size.height * (i / 4);
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    // GO line (green)
    paint.color = AppTheme.success;
    final goPath = Path();
    goPath.moveTo(0, size.height * 0.3);
    goPath.lineTo(size.width * 0.17, size.height * 0.25);
    goPath.lineTo(size.width * 0.33, size.height * 0.35);
    goPath.lineTo(size.width * 0.5, size.height * 0.2);
    goPath.lineTo(size.width * 0.67, size.height * 0.28);
    goPath.lineTo(size.width * 0.83, size.height * 0.15);
    goPath.lineTo(size.width, size.height * 0.22);
    canvas.drawPath(goPath, paint);

    // NO-GO line (red)
    paint.color = AppTheme.danger;
    final noGoPath = Path();
    noGoPath.moveTo(0, size.height * 0.75);
    noGoPath.lineTo(size.width * 0.17, size.height * 0.7);
    noGoPath.lineTo(size.width * 0.33, size.height * 0.8);
    noGoPath.lineTo(size.width * 0.5, size.height * 0.72);
    noGoPath.lineTo(size.width * 0.67, size.height * 0.78);
    noGoPath.lineTo(size.width * 0.83, size.height * 0.68);
    noGoPath.lineTo(size.width, size.height * 0.75);
    canvas.drawPath(noGoPath, paint);

    // REFER line (orange)
    paint.color = AppTheme.warning;
    final referPath = Path();
    referPath.moveTo(0, size.height * 0.55);
    referPath.lineTo(size.width * 0.17, size.height * 0.5);
    referPath.lineTo(size.width * 0.33, size.height * 0.58);
    referPath.lineTo(size.width * 0.5, size.height * 0.48);
    referPath.lineTo(size.width * 0.67, size.height * 0.55);
    referPath.lineTo(size.width * 0.83, size.height * 0.45);
    referPath.lineTo(size.width, size.height * 0.52);
    canvas.drawPath(referPath, paint);

    // Draw data points
    paint.style = PaintingStyle.fill;
    final points = [0.0, 0.17, 0.33, 0.5, 0.67, 0.83, 1.0];

    for (final x in points) {
      // GO points
      canvas.drawCircle(
        Offset(size.width * x, _getGoY(x) * size.height),
        4,
        Paint()..color = AppTheme.success,
      );
    }
  }

  double _getGoY(double x) {
    final values = [0.3, 0.25, 0.35, 0.2, 0.28, 0.15, 0.22];
    final index = (x * 6).round();
    return values[index];
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
