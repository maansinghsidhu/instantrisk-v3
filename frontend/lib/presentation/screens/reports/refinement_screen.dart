import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';

/// Refinement Screen - Adjust parameters and recalculate assessment
class RefinementScreen extends StatefulWidget {
  final String assessmentId;

  const RefinementScreen({
    super.key,
    required this.assessmentId,
  });

  @override
  State<RefinementScreen> createState() => _RefinementScreenState();
}

class _RefinementScreenState extends State<RefinementScreen> {
  double _coverageLimit = 500000;
  double _deductible = 10000;
  String _policyTerm = '12 months';
  bool _includeFlood = true;
  bool _includeEarthquake = false;
  bool _includeBusinessInterruption = true;
  bool _isRecalculating = false;

  final List<String> _policyTerms = ['6 months', '12 months', '24 months', '36 months'];

  Future<void> _recalculate() async {
    setState(() => _isRecalculating = true);

    // Simulate recalculation
    await Future.delayed(const Duration(seconds: 2));

    setState(() => _isRecalculating = false);

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('Assessment recalculated successfully'),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppTheme.textPrimary),
          onPressed: () => context.go('/reports/results/${widget.assessmentId}'),
        ),
        title: const Text(
          'Refine Assessment',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
            fontFamily: 'Inter',
          ),
        ),
        centerTitle: true,
      ),
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Info Card
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppTheme.info.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      children: const [
                        Icon(Icons.info_outline, color: AppTheme.info, size: 24),
                        SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            'Adjust parameters below to see how they affect the risk assessment and premium calculation.',
                            style: TextStyle(
                              fontSize: 14,
                              color: AppTheme.textPrimary,
                              height: 1.4,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Coverage Limit Slider
                  _buildSectionTitle('Coverage Limit'),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppTheme.border),
                    ),
                    child: Column(
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text(
                              'Limit Amount',
                              style: TextStyle(
                                fontSize: 14,
                                color: AppTheme.textSecondary,
                              ),
                            ),
                            Text(
                              '\u20AC${_formatNumber(_coverageLimit)}',
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.w700,
                                color: AppTheme.primaryDark,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        SliderTheme(
                          data: SliderThemeData(
                            activeTrackColor: AppTheme.primaryDark,
                            inactiveTrackColor: AppTheme.border,
                            thumbColor: AppTheme.primaryDark,
                            overlayColor: AppTheme.primaryDark.withOpacity(0.2),
                          ),
                          child: Slider(
                            value: _coverageLimit,
                            min: 100000,
                            max: 2000000,
                            divisions: 19,
                            onChanged: (value) {
                              setState(() => _coverageLimit = value);
                            },
                          ),
                        ),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: const [
                            Text('\u20AC100k', style: TextStyle(fontSize: 12, color: AppTheme.textHint)),
                            Text('\u20AC2M', style: TextStyle(fontSize: 12, color: AppTheme.textHint)),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Deductible Slider
                  _buildSectionTitle('Deductible'),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppTheme.border),
                    ),
                    child: Column(
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text(
                              'Deductible Amount',
                              style: TextStyle(
                                fontSize: 14,
                                color: AppTheme.textSecondary,
                              ),
                            ),
                            Text(
                              '\u20AC${_formatNumber(_deductible)}',
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.w700,
                                color: AppTheme.primaryDark,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        SliderTheme(
                          data: SliderThemeData(
                            activeTrackColor: AppTheme.primaryDark,
                            inactiveTrackColor: AppTheme.border,
                            thumbColor: AppTheme.primaryDark,
                            overlayColor: AppTheme.primaryDark.withOpacity(0.2),
                          ),
                          child: Slider(
                            value: _deductible,
                            min: 1000,
                            max: 50000,
                            divisions: 49,
                            onChanged: (value) {
                              setState(() => _deductible = value);
                            },
                          ),
                        ),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: const [
                            Text('\u20AC1k', style: TextStyle(fontSize: 12, color: AppTheme.textHint)),
                            Text('\u20AC50k', style: TextStyle(fontSize: 12, color: AppTheme.textHint)),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Policy Term
                  _buildSectionTitle('Policy Term'),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppTheme.border),
                    ),
                    child: DropdownButtonHideUnderline(
                      child: DropdownButton<String>(
                        value: _policyTerm,
                        isExpanded: true,
                        icon: const Icon(Icons.keyboard_arrow_down, color: AppTheme.textSecondary),
                        items: _policyTerms.map((term) {
                          return DropdownMenuItem(
                            value: term,
                            child: Text(
                              term,
                              style: const TextStyle(
                                fontSize: 16,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                          );
                        }).toList(),
                        onChanged: (value) {
                          if (value != null) {
                            setState(() => _policyTerm = value);
                          }
                        },
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Additional Coverage Options
                  _buildSectionTitle('Additional Coverage'),
                  const SizedBox(height: 12),
                  Container(
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppTheme.border),
                    ),
                    child: Column(
                      children: [
                        _buildToggleOption(
                          'Flood Coverage',
                          'Covers damage from flooding',
                          _includeFlood,
                          (value) => setState(() => _includeFlood = value),
                        ),
                        const Divider(height: 1, color: AppTheme.border),
                        _buildToggleOption(
                          'Earthquake Coverage',
                          'Covers seismic event damage',
                          _includeEarthquake,
                          (value) => setState(() => _includeEarthquake = value),
                        ),
                        const Divider(height: 1, color: AppTheme.border),
                        _buildToggleOption(
                          'Business Interruption',
                          'Covers income loss during recovery',
                          _includeBusinessInterruption,
                          (value) => setState(() => _includeBusinessInterruption = value),
                          showDivider: false,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Estimated Impact Card
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryDark.withOpacity(0.05),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppTheme.primaryDark.withOpacity(0.2)),
                    ),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: AppTheme.primaryDark.withOpacity(0.1),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(
                            Icons.calculate_outlined,
                            color: AppTheme.primaryDark,
                            size: 24,
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'Estimated Premium Impact',
                                style: TextStyle(
                                  fontSize: 14,
                                  color: AppTheme.textSecondary,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '\u20AC${_calculateEstimatedPremium()}',
                                style: const TextStyle(
                                  fontSize: 20,
                                  fontWeight: FontWeight.w700,
                                  color: AppTheme.primaryDark,
                                ),
                              ),
                            ],
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: AppTheme.success.withOpacity(0.1),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: const Text(
                            '-8%',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.success,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),

          // Bottom Action Buttons
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.05),
                  blurRadius: 10,
                  offset: const Offset(0, -5),
                ),
              ],
            ),
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      // Reset to defaults
                      setState(() {
                        _coverageLimit = 500000;
                        _deductible = 10000;
                        _policyTerm = '12 months';
                        _includeFlood = true;
                        _includeEarthquake = false;
                        _includeBusinessInterruption = true;
                      });
                    },
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      side: const BorderSide(color: AppTheme.border),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: const Text(
                      'Reset',
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 2,
                  child: ElevatedButton(
                    onPressed: _isRecalculating ? null : _recalculate,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primaryDark,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: _isRecalculating
                        ? const SizedBox(
                            width: 24,
                            height: 24,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 2,
                            ),
                          )
                        : const Text(
                            'Recalculate',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
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
  }

  Widget _buildSectionTitle(String title) {
    return Text(
      title,
      style: const TextStyle(
        fontSize: 16,
        fontWeight: FontWeight.w600,
        color: AppTheme.textPrimary,
        fontFamily: 'Inter',
      ),
    );
  }

  Widget _buildToggleOption(
    String title,
    String subtitle,
    bool value,
    ValueChanged<bool> onChanged, {
    bool showDivider = true,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w500,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: AppTheme.success,
          ),
        ],
      ),
    );
  }

  String _formatNumber(double value) {
    if (value >= 1000000) {
      return '${(value / 1000000).toStringAsFixed(1)}M';
    } else if (value >= 1000) {
      return '${(value / 1000).toStringAsFixed(0)}k';
    }
    return value.toStringAsFixed(0);
  }

  String _calculateEstimatedPremium() {
    // Simple calculation for demonstration
    double basePremium = (_coverageLimit / 100) * 0.85;
    basePremium -= (_deductible / 100) * 2;
    if (_includeFlood) basePremium += 2500;
    if (_includeEarthquake) basePremium += 3500;
    if (_includeBusinessInterruption) basePremium += 4000;

    return _formatNumber(basePremium);
  }
}
