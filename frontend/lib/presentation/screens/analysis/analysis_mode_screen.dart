import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../widgets/common/screen_header.dart';

/// Analysis Mode Selection Screen
/// Allows users to choose between Quick, Go/No-Go, and Deep analysis
class AnalysisModeScreen extends StatefulWidget {
  final String assessmentId;
  final int documentCount;
  final int totalChars;

  const AnalysisModeScreen({
    super.key,
    required this.assessmentId,
    this.documentCount = 1,
    this.totalChars = 2000,
  });

  @override
  State<AnalysisModeScreen> createState() => _AnalysisModeScreenState();
}

class _AnalysisModeScreenState extends State<AnalysisModeScreen> {
  List<Map<String, dynamic>> _modes = [];
  String _recommendedMode = 'go_no_go';
  String? _selectedMode;
  bool _isLoading = true;
  bool _isStarting = false;

  @override
  void initState() {
    super.initState();
    _loadModes();
  }

  Future<void> _loadModes() async {
    try {
      final response = await authService.get(
        '/analysis/modes?document_count=${widget.documentCount}&total_chars=${widget.totalChars}'
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _modes = List<Map<String, dynamic>>.from(data['modes'] ?? []);
          _recommendedMode = data['recommended'] ?? 'go_no_go';
          _selectedMode = _recommendedMode;
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() => _isLoading = false);
      // Use default modes if API fails
      _modes = [
        {
          'mode': 'quick',
          'mode_info': {
            'name': 'Quick Analysis',
            'description': 'Fast classification and decision. Best for time-sensitive quotes.',
            'icon': 'flash_on',
            'agents': ['Classifier', 'Underwriter'],
          },
          'estimated_seconds': 45,
          'agents_count': 2,
        },
        {
          'mode': 'go_no_go',
          'mode_info': {
            'name': 'Go/No-Go Analysis',
            'description': 'Standard 4-agent analysis with risk assessment. Recommended for most submissions.',
            'icon': 'gavel',
            'agents': ['Classifier', 'Extractor', 'Risk Analyst', 'Underwriter'],
          },
          'estimated_seconds': 120,
          'agents_count': 4,
        },
        {
          'mode': 'deep',
          'mode_info': {
            'name': 'Deep Analysis',
            'description': 'Comprehensive 9-agent analysis with financial, compliance, and verification. Best for complex risks.',
            'icon': 'analytics',
            'agents': ['Classifier', 'Extractor', 'Financial', 'Risk Analyst', 'Compliance', 'Exposure', 'Underwriter', 'Verification', 'QA'],
          },
          'estimated_seconds': 300,
          'agents_count': 9,
        },
      ];
      _selectedMode = 'go_no_go';
    }
  }

  IconData _getIconForMode(String? iconName) {
    switch (iconName) {
      case 'flash_on':
        return Icons.flash_on;
      case 'gavel':
        return Icons.gavel;
      case 'analytics':
        return Icons.analytics;
      default:
        return Icons.auto_awesome;
    }
  }

  Color _getColorForMode(String mode) {
    switch (mode) {
      case 'quick':
        return const Color(0xFFF59E0B); // Amber
      case 'go_no_go':
        return const Color(0xFF2563EB); // Blue
      case 'deep':
        return const Color(0xFF7C3AED); // Purple
      default:
        return AppTheme.primaryDark;
    }
  }

  String _formatDuration(int seconds) {
    if (seconds < 60) {
      return '~$seconds sec';
    } else {
      final minutes = seconds ~/ 60;
      final remainingSeconds = seconds % 60;
      if (remainingSeconds == 0) {
        return '~$minutes min';
      }
      return '~$minutes min $remainingSeconds sec';
    }
  }

  /// Calculate estimated time based on document count and total characters
  int _calculateEstimatedTime(String mode, int baseSeconds) {
    // Base time per document varies by mode
    final baseTimePerDoc = mode == 'quick' ? 10 : mode == 'go_no_go' ? 25 : 50;
    // Additional time based on character count (roughly 1 second per 10k chars)
    final charTimeSeconds = (widget.totalChars / 10000).ceil();
    // Calculate total: base + (docs * perDocTime) + charTime
    final estimated = baseSeconds + ((widget.documentCount - 1) * baseTimePerDoc) + charTimeSeconds;
    return estimated;
  }

  Future<void> _startAnalysis() async {
    if (_selectedMode == null) return;

    setState(() => _isStarting = true);

    // Navigate to progress screen with selected mode
    if (mounted) {
      context.go(
        '/analysis/progress/${widget.assessmentId}',
        extra: {
          'mode': _selectedMode,
          'documentCount': widget.documentCount,
          'totalChars': widget.totalChars,
        },
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      body: Column(
        children: [
          ScreenHeader(
            title: l10n.analysisMode,
            subtitle: 'Choose analysis depth',
            leading: IconButton(
              icon: const Icon(Icons.arrow_back, color: Colors.white),
              onPressed: () => context.pop(),
            ),
          ),
          Expanded(
            child: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                // Header info
                Container(
                  padding: EdgeInsets.all(20),
                  color: AppTheme.surfaceOf(context),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: AppTheme.primaryDark.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(
                          Icons.description_outlined,
                          color: AppTheme.primaryDark,
                          size: 24,
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '${widget.documentCount} document${widget.documentCount > 1 ? 's' : ''} to analyze',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                                color: AppTheme.text1(context),
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${(widget.totalChars / 1000).toStringAsFixed(1)}k characters',
                              style: TextStyle(
                                fontSize: 13,
                                color: AppTheme.text2(context),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

                // Mode selection cards
                Expanded(
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _modes.length,
                    itemBuilder: (context, index) {
                      final mode = _modes[index];
                      return _buildModeCard(mode, l10n);
                    },
                  ),
                ),

                // Start button
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceOf(context),
                    border: Border(top: BorderSide(color: AppTheme.borderOf(context))),
                  ),
                  child: SafeArea(
                    child: SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: _isStarting ? null : _startAnalysis,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: _selectedMode != null
                              ? _getColorForMode(_selectedMode!)
                              : AppTheme.primaryDark,
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                        child: _isStarting
                            ? const SizedBox(
                                width: 24,
                                height: 24,
                                child: CircularProgressIndicator(
                                  color: Colors.white,
                                  strokeWidth: 2,
                                ),
                              )
                            : Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  const Icon(Icons.play_arrow, color: Colors.white),
                                  const SizedBox(width: 8),
                                  Text(
                                    l10n.startAnalysis,
                                    style: const TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.w600,
                                      color: Colors.white,
                                    ),
                                  ),
                                ],
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
  }

  Widget _buildModeCard(Map<String, dynamic> mode, AppLocalizations l10n) {
    final modeId = mode['mode'] as String;
    final modeInfo = mode['mode_info'] as Map<String, dynamic>? ?? {};
    final isSelected = _selectedMode == modeId;
    final isRecommended = _recommendedMode == modeId;
    final color = _getColorForMode(modeId);
    final baseSeconds = mode['estimated_seconds'] as int? ?? 30;
    // Calculate dynamic estimate based on document count and size
    final estimatedSeconds = _calculateEstimatedTime(modeId, baseSeconds);
    final agents = List<String>.from(modeInfo['agents'] ?? []);

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      child: Material(
        color: isSelected ? color.withOpacity(0.05) : AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          onTap: () => setState(() => _selectedMode = modeId),
          borderRadius: BorderRadius.circular(16),
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: isSelected ? color : AppTheme.borderOf(context),
                width: isSelected ? 2 : 1,
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    // Icon
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: color.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        _getIconForMode(modeInfo['icon'] as String?),
                        color: color,
                        size: 28,
                      ),
                    ),
                    const SizedBox(width: 16),

                    // Title and badges
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text(
                                modeInfo['name'] as String? ?? modeId,
                                style: TextStyle(
                                  fontSize: 17,
                                  fontWeight: FontWeight.w700,
                                  color: isSelected ? color : AppTheme.text1(context),
                                  fontFamily: 'Inter',
                                ),
                              ),
                              if (isRecommended) ...[
                                const SizedBox(width: 8),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 8,
                                    vertical: 3,
                                  ),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF059669).withOpacity(0.1),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Text(
                                    l10n.recommended,
                                    style: const TextStyle(
                                      fontSize: 9,
                                      fontWeight: FontWeight.w700,
                                      color: Color(0xFF059669),
                                      letterSpacing: 0.5,
                                    ),
                                  ),
                                ),
                              ],
                            ],
                          ),
                          const SizedBox(height: 4),
                          Row(
                            children: [
                              Icon(
                                Icons.timer_outlined,
                                size: 14,
                                color: AppTheme.text2(context),
                              ),
                              const SizedBox(width: 4),
                              Text(
                                _formatDuration(estimatedSeconds),
                                style: TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w500,
                                  color: AppTheme.text2(context),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Icon(
                                Icons.smart_toy_outlined,
                                size: 14,
                                color: AppTheme.text2(context),
                              ),
                              const SizedBox(width: 4),
                              Text(
                                '${mode['agents_count']} ${l10n.agents}',
                                style: TextStyle(
                                  fontSize: 13,
                                  color: AppTheme.text2(context),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),

                    // Selection indicator
                    Container(
                      width: 24,
                      height: 24,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: isSelected ? color : Colors.transparent,
                        border: Border.all(
                          color: isSelected ? color : AppTheme.borderOf(context),
                          width: 2,
                        ),
                      ),
                      child: isSelected
                          ? const Icon(Icons.check, color: Colors.white, size: 16)
                          : null,
                    ),
                  ],
                ),

                const SizedBox(height: 16),

                // Description
                Text(
                  modeInfo['description'] as String? ?? '',
                  style: TextStyle(
                    fontSize: 14,
                    color: AppTheme.text2(context),
                    height: 1.4,
                  ),
                ),

                const SizedBox(height: 16),

                // Agents list
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: agents.map((agent) => Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: isSelected ? color.withOpacity(0.1) : AppTheme.bg(context),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(
                        color: isSelected ? color.withOpacity(0.3) : AppTheme.borderOf(context),
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.psychology_outlined,
                          size: 14,
                          color: isSelected ? color : AppTheme.text2(context),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          agent,
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                            color: isSelected ? color : AppTheme.text2(context),
                          ),
                        ),
                      ],
                    ),
                  )).toList(),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
