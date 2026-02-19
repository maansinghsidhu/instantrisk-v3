import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';

/// ShapWaterfallChart - SHAP explainability visualization
/// Shows which features drove the model's decision (positive = increased risk, negative = decreased)
class ShapWaterfallChart extends StatefulWidget {
  /// List of SHAP values: each entry has 'feature', 'value' (double), 'impact' (+/-)
  final List<Map<String, dynamic>> shapValues;
  final double baseValue;
  final double finalPrediction;
  final String title;

  const ShapWaterfallChart({
    super.key,
    required this.shapValues,
    this.baseValue = 0.5,
    this.finalPrediction = 0.7,
    this.title = 'Risk Explanation',
  });

  @override
  State<ShapWaterfallChart> createState() => _ShapWaterfallChartState();
}

class _ShapWaterfallChartState extends State<ShapWaterfallChart>
    with SingleTickerProviderStateMixin {
  late AnimationController _animController;
  late Animation<double> _anim;
  bool _isExpanded = true;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    );
    _anim = CurvedAnimation(parent: _animController, curve: Curves.easeOut);
    _animController.forward();
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  List<Map<String, dynamic>> get _sortedValues {
    final sorted = List<Map<String, dynamic>>.from(widget.shapValues);
    sorted.sort((a, b) {
      final aAbs = (a['value'] as num).abs();
      final bAbs = (b['value'] as num).abs();
      return bAbs.compareTo(aAbs);
    });
    return sorted.take(8).toList();
  }

  double get _maxAbs {
    if (_sortedValues.isEmpty) return 1.0;
    return _sortedValues
        .map((e) => (e['value'] as num).abs().toDouble())
        .reduce((a, b) => a > b ? a : b);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          InkWell(
            onTap: () => setState(() => _isExpanded = !_isExpanded),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: AppTheme.highlightBlue.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.auto_graph,
                      size: 18,
                      color: AppTheme.highlightBlue,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      widget.title,
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.text1(context),
                      ),
                    ),
                  ),
                  // Legend chips
                  _LegendChip(label: 'Increases risk', color: AppTheme.danger),
                  const SizedBox(width: 6),
                  _LegendChip(label: 'Decreases risk', color: AppTheme.success),
                  const SizedBox(width: 8),
                  Icon(
                    _isExpanded ? Icons.expand_less : Icons.expand_more,
                    size: 20,
                    color: AppTheme.text2(context),
                  ),
                ],
              ),
            ),
          ),

          if (_isExpanded) ...[
            Divider(height: 1, color: AppTheme.borderOf(context)),

            // Summary row
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                children: [
                  _SummaryBox(
                    label: 'Base Value',
                    value: '${(widget.baseValue * 100).toStringAsFixed(0)}%',
                    color: AppTheme.textSecondary,
                    context: context,
                  ),
                  const SizedBox(width: 8),
                  const Icon(Icons.arrow_forward, size: 16, color: Colors.grey),
                  const SizedBox(width: 8),
                  _SummaryBox(
                    label: 'Prediction',
                    value: '${(widget.finalPrediction * 100).toStringAsFixed(0)}%',
                    color: widget.finalPrediction > 0.6
                        ? AppTheme.danger
                        : AppTheme.success,
                    context: context,
                  ),
                ],
              ),
            ),

            Divider(height: 1, color: AppTheme.borderOf(context)),

            if (widget.shapValues.isEmpty)
              Padding(
                padding: const EdgeInsets.all(24),
                child: Center(
                  child: Text(
                    'No explainability data available',
                    style: TextStyle(
                      fontSize: 13,
                      color: AppTheme.text2(context),
                    ),
                  ),
                ),
              )
            else
              AnimatedBuilder(
                animation: _anim,
                builder: (context, _) {
                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    child: Column(
                      children: _sortedValues.asMap().entries.map((entry) {
                        final item = entry.value;
                        final shapVal = (item['value'] as num).toDouble();
                        final barWidth = (_anim.value * (shapVal.abs() / _maxAbs));
                        final isPositive = shapVal > 0;
                        final color = isPositive ? AppTheme.danger : AppTheme.success;
                        final featureName = item['feature']?.toString() ?? 'Feature ${entry.key + 1}';
                        final displayVal = shapVal > 0
                            ? '+${shapVal.toStringAsFixed(3)}'
                            : shapVal.toStringAsFixed(3);

                        return Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Row(
                            children: [
                              // Feature name
                              SizedBox(
                                width: 140,
                                child: Text(
                                  featureName,
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: AppTheme.text1(context),
                                    fontWeight: FontWeight.w500,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              const SizedBox(width: 8),
                              // Bar
                              Expanded(
                                child: Stack(
                                  children: [
                                    // Background track
                                    Container(
                                      height: 24,
                                      decoration: BoxDecoration(
                                        color: AppTheme.borderLightOf(context),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                    ),
                                    // Value bar
                                    Positioned.fill(
                                      child: Align(
                                        alignment: isPositive
                                            ? Alignment.centerLeft
                                            : Alignment.centerRight,
                                        child: FractionallySizedBox(
                                          widthFactor: barWidth.clamp(0.02, 1.0),
                                          child: Container(
                                            height: 24,
                                            decoration: BoxDecoration(
                                              color: color.withOpacity(0.8),
                                              borderRadius: BorderRadius.circular(4),
                                            ),
                                          ),
                                        ),
                                      ),
                                    ),
                                    // Value label
                                    Positioned.fill(
                                      child: Padding(
                                        padding: const EdgeInsets.symmetric(horizontal: 6),
                                        child: Align(
                                          alignment: isPositive
                                              ? Alignment.centerRight
                                              : Alignment.centerLeft,
                                          child: Text(
                                            displayVal,
                                            style: const TextStyle(
                                              fontSize: 10,
                                              fontWeight: FontWeight.w700,
                                              color: Colors.white,
                                            ),
                                          ),
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        );
                      }).toList(),
                    ),
                  );
                },
              ),
          ],
        ],
      ),
    );
  }
}

class _LegendChip extends StatelessWidget {
  final String label;
  final Color color;

  const _LegendChip({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 3),
        Text(
          label,
          style: TextStyle(fontSize: 10, color: AppTheme.text2(context)),
        ),
      ],
    );
  }
}

class _SummaryBox extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  final BuildContext context;

  const _SummaryBox({
    required this.label,
    required this.value,
    required this.color,
    required this.context,
  });

  @override
  Widget build(BuildContext ctx) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 10,
              color: AppTheme.text2(context),
            ),
          ),
          Text(
            value,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}
