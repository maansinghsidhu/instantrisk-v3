import 'package:flutter/material.dart';
import '../../core/theme/app_theme.dart';

/// RapidRate AI Pricing Section - Embedded in analysis results screen
/// Displays premium estimate, experience mod, VaR table, Monte Carlo
class RapidRateSection extends StatelessWidget {
  final Map<String, dynamic> pricingData;
  final VoidCallback? onRecalculate;

  const RapidRateSection({
    super.key,
    required this.pricingData,
    this.onRecalculate,
  });

  @override
  Widget build(BuildContext context) {
    final premium = pricingData['premium'] ?? pricingData['estimated_premium'] ?? 0;
    final premiumLow = pricingData['premium_range']?['low'] ?? (premium * 0.85);
    final premiumHigh = pricingData['premium_range']?['high'] ?? (premium * 1.15);
    final experienceMod = pricingData['experience_mod'] ?? pricingData['experience_modification'] ?? 1.0;
    final frequencyRate = pricingData['frequency_rate'] ?? pricingData['frequency'] ?? 0.0;
    final avgSeverity = pricingData['avg_severity'] ?? pricingData['average_severity'] ?? 0;
    final lossRatio = pricingData['loss_ratio'] ?? pricingData['expected_loss_ratio'] ?? 0.0;
    final varData = pricingData['var_percentiles'] ?? pricingData['percentiles'] ?? {};
    final policyType = pricingData['policy_type'] ?? 'GL';
    final modelVersion = pricingData['model_version'] ?? 'v1.0';

    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF10B981).withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  const Color(0xFF10B981).withValues(alpha: 0.1),
                  Colors.transparent,
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(16),
                topRight: Radius.circular(16),
              ),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF10B981).withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.speed,
                    color: Color(0xFF10B981),
                    size: 20,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'AI Pricing (RapidRate)',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text1(context),
                          fontFamily: 'Inter',
                        ),
                      ),
                      SizedBox(height: 2),
                      Text(
                        'ML-powered premium estimation',
                        style: TextStyle(fontSize: 12, color: AppTheme.text2(context)),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xFF10B981).withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    policyType.toString().toUpperCase(),
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF10B981),
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Premium Display
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Large premium estimate
                Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      '\$${_formatCurrency(premium)}',
                      style: TextStyle(
                        fontSize: 32,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.text1(context),
                        fontFamily: 'Inter',
                      ),
                    ),
                    const SizedBox(width: 8),
                    Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Text(
                        'estimated premium',
                        style: TextStyle(
                          fontSize: 13,
                          color: AppTheme.text2(context),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  'Range: \$${_formatCurrency(premiumLow)} — \$${_formatCurrency(premiumHigh)}',
                  style: TextStyle(
                    fontSize: 13,
                    color: AppTheme.text2(context),
                  ),
                ),
                const SizedBox(height: 20),

                // Experience Mod Badge
                _buildExperienceModBadge(experienceMod),
                const SizedBox(height: 20),

                // Key Metrics Row
                Row(
                  children: [
                    _buildMetric('Frequency', frequencyRate is num ? (frequencyRate as num).toStringAsFixed(3) : '$frequencyRate'),
                    _buildMetric('Avg Severity', '\$${_formatCurrency(avgSeverity)}'),
                    _buildMetric('Loss Ratio', '${(lossRatio is num ? (lossRatio as num) * 100 : lossRatio).toStringAsFixed(1)}%'),
                  ],
                ),
                const SizedBox(height: 20),

                // VaR Table
                if (varData is Map && varData.isNotEmpty) ...[
                  Text(
                    'Value at Risk (VaR) Percentiles',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.text1(context),
                    ),
                  ),
                  const SizedBox(height: 12),
                  _buildVarTable(varData),
                  const SizedBox(height: 16),
                ],

                // Footer with recalculate and model version
                Row(
                  children: [
                    Icon(Icons.memory, size: 14, color: AppTheme.textH(context)),
                    const SizedBox(width: 4),
                    Text(
                      'Powered by RapidRate ML $modelVersion',
                      style: TextStyle(fontSize: 11, color: AppTheme.textH(context)),
                    ),
                    const Spacer(),
                    if (onRecalculate != null)
                      TextButton.icon(
                        onPressed: onRecalculate,
                        icon: const Icon(Icons.refresh, size: 16),
                        label: const Text('Recalculate', style: TextStyle(fontSize: 12)),
                        style: TextButton.styleFrom(
                          foregroundColor: const Color(0xFF10B981),
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildExperienceModBadge(dynamic mod) {
    final modValue = mod is num ? mod.toDouble() : 1.0;
    final isGood = modValue < 1.0;
    final isBad = modValue > 1.0;
    final color = isGood ? Color(0xFF10B981) : isBad ? Color(0xFFEF4444) : AppTheme.text2(context);
    final label = isGood ? 'Better than average' : isBad ? 'Worse than average' : 'Average';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'Experience Mod: ${modValue.toStringAsFixed(2)}',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            '— $label',
            style: TextStyle(fontSize: 13, color: color.withValues(alpha: 0.7)),
          ),
        ],
      ),
    );
  }

  Widget _buildMetric(String label, String value) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(fontSize: 11, color: AppTheme.textH(context)),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: AppTheme.text1(context),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildVarTable(Map<dynamic, dynamic> varData) {
    final percentiles = ['p50', 'p75', 'p90', 'p95', 'p99'];
    final labels = ['50th', '75th', '90th', '95th', '99th'];

    return Container(
      decoration: BoxDecoration(
        color: AppTheme.bg(context),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Table(
        defaultColumnWidth: const FlexColumnWidth(),
        children: [
          TableRow(
            decoration: BoxDecoration(
              color: AppTheme.surfaceOf(context),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(10),
                topRight: Radius.circular(10),
              ),
            ),
            children: labels.map((l) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 6),
              child: Text(
                l,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.text2(context),
                ),
              ),
            )).toList(),
          ),
          TableRow(
            children: percentiles.map((p) {
              final val = varData[p] ?? varData[p.replaceAll('p', '')] ?? '—';
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 6),
                child: Text(
                  val is num ? '\$${_formatCurrency(val)}' : '$val',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.text1(context),
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  String _formatCurrency(dynamic amount) {
    if (amount == null) return '0';
    final num value = amount is num ? amount : 0;
    if (value >= 1000000) {
      return '${(value / 1000000).toStringAsFixed(1)}M';
    } else if (value >= 1000) {
      return '${(value / 1000).toStringAsFixed(1)}K';
    }
    return value.toStringAsFixed(0);
  }
}
