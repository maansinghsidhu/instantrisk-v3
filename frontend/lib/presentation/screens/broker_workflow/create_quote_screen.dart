import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/services/auth_service.dart';
import '../../../core/theme/app_theme.dart';

/// Underwriter's quote creation screen for broker submissions.
/// Fetches assessment data, pre-populates AI-suggested values,
/// and allows the underwriter to craft and submit a quote.
class CreateQuoteScreen extends StatefulWidget {
  final String assessmentId;
  const CreateQuoteScreen({super.key, required this.assessmentId});

  @override
  State<CreateQuoteScreen> createState() => _CreateQuoteScreenState();
}

class _CreateQuoteScreenState extends State<CreateQuoteScreen> {
  final _formKey = GlobalKey<FormState>();

  // ── State ──
  Map<String, dynamic>? _assessment;
  bool _isLoading = true;
  bool _isSubmitting = false;
  String? _error;

  // ── AI data ──
  dynamic _riskScore;
  List<dynamic> _aiRecommendations = [];

  // ── Form controllers ──
  final _premiumController = TextEditingController();
  final _deductibleController = TextEditingController();
  final _conditionsController = TextEditingController();
  final _subjectivitiesController = TextEditingController();
  final _exclusionsController = TextEditingController();
  final _validityController = TextEditingController(text: '30');
  final _termsController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _fetchAssessment();
  }

  @override
  void dispose() {
    _premiumController.dispose();
    _deductibleController.dispose();
    _conditionsController.dispose();
    _subjectivitiesController.dispose();
    _exclusionsController.dispose();
    _validityController.dispose();
    _termsController.dispose();
    super.dispose();
  }

  // ── Fetch assessment data ──

  Future<void> _fetchAssessment() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final response =
          await authService.get('/assessments/${widget.assessmentId}');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        setState(() {
          _assessment = data;
          _riskScore = data['risk_score'];
          _isLoading = false;
        });
        _preFillFromAI(data);
      } else if (response.statusCode == 404) {
        setState(() {
          _error = 'Assessment not found.';
          _isLoading = false;
        });
      } else {
        setState(() {
          _error = 'Failed to load assessment (${response.statusCode}).';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Connection error: $e';
        _isLoading = false;
      });
    }
  }

  void _preFillFromAI(Map<String, dynamic> data) {
    final aiAnalysis = data['ai_analysis'] is Map<String, dynamic>
        ? data['ai_analysis'] as Map<String, dynamic>
        : <String, dynamic>{};

    // Pre-fill suggested premium
    if (aiAnalysis['suggested_premium'] != null) {
      _premiumController.text = aiAnalysis['suggested_premium'].toString();
    }

    // Collect AI recommendations
    if (data['ai_recommendations'] is List) {
      _aiRecommendations = data['ai_recommendations'] as List<dynamic>;
    } else if (aiAnalysis['recommendations'] is List) {
      _aiRecommendations = aiAnalysis['recommendations'] as List<dynamic>;
    }
  }

  // ── Submit quote ──

  Future<void> _submitQuote() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isSubmitting = true);

    // Parse comma-separated list fields
    List<String> _parseList(String text) {
      return text
          .split(',')
          .map((s) => s.trim())
          .where((s) => s.isNotEmpty)
          .toList();
    }

    final body = <String, dynamic>{
      'assessment_id': widget.assessmentId,
      'quoted_premium': double.tryParse(_premiumController.text) ?? 0,
      'currency': 'GBP',
      'deductible': _deductibleController.text.isNotEmpty
          ? double.tryParse(_deductibleController.text)
          : null,
      'conditions': _parseList(_conditionsController.text),
      'subjectivities': _parseList(_subjectivitiesController.text),
      'exclusions': _parseList(_exclusionsController.text),
      'terms': _termsController.text.isNotEmpty
          ? {'notes': _termsController.text}
          : null,
      'validity_days':
          int.tryParse(_validityController.text) ?? 30,
    };

    try {
      final response = await authService.post(
        '/broker-portal/create-quote',
        body: body,
      );

      if (response.statusCode == 201 || response.statusCode == 200) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('Quote created successfully.'),
            backgroundColor: AppTheme.success,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
          ),
        );
        context.pop();
      } else {
        final detail = _parseError(response.body);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(detail),
            backgroundColor: AppTheme.danger,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error: $e'),
          backgroundColor: AppTheme.danger,
          behavior: SnackBarBehavior.floating,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      );
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  String _parseError(String body) {
    try {
      final data = jsonDecode(body);
      return (data['detail'] ?? 'Failed to create quote.').toString();
    } catch (_) {
      return 'Failed to create quote.';
    }
  }

  // ── Helpers ──

  String _formatCurrency(dynamic value) {
    if (value == null) return 'N/A';
    final num amount =
        value is num ? value : (num.tryParse(value.toString()) ?? 0);
    if (amount >= 1000000) {
      final m = amount / 1000000;
      return m == m.truncateToDouble()
          ? '\u00A3${m.toInt()}m'
          : '\u00A3${m.toStringAsFixed(1)}m';
    } else if (amount >= 1000) {
      return '\u00A3${(amount / 1000).toStringAsFixed(0)}k';
    }
    return '\u00A3${amount.toStringAsFixed(0)}';
  }

  // ── Build ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceOf(context),
        elevation: 0,
        title: Text(
          'Create Quote',
          style: TextStyle(
            color: AppTheme.text1(context),
            fontWeight: FontWeight.w600,
            fontSize: 17,
            letterSpacing: -0.2,
          ),
        ),
        iconTheme: IconThemeData(color: AppTheme.text1(context)),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(
            height: 1,
            color: AppTheme.borderOf(context),
          ),
        ),
      ),
      body: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_isLoading) {
      return Center(
        child: CircularProgressIndicator(
          color: AppTheme.primaryDark,
          strokeWidth: 2.5,
        ),
      );
    }

    if (_error != null) {
      return _buildErrorState(context);
    }

    return Form(
      key: _formKey,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          // ── Risk score banner ──
          if (_riskScore != null) ...[
            _buildRiskScoreBanner(context),
            const SizedBox(height: 14),
          ],

          // ── AI Recommendations ──
          if (_aiRecommendations.isNotEmpty) ...[
            _buildRecommendationsCard(context),
            const SizedBox(height: 14),
          ],

          // ── Assessment summary ──
          _buildAssessmentSummary(context),
          const SizedBox(height: 14),

          // ── Quote form fields ──
          _buildFormCard(context),
          const SizedBox(height: 14),

          // ── Preview ──
          _buildPreviewCard(context),
          const SizedBox(height: 14),

          // ── Submit button ──
          _buildSubmitButton(context),
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  // ── Error state ──

  Widget _buildErrorState(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 56, color: AppTheme.danger),
            const SizedBox(height: 16),
            Text(
              'Something went wrong',
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w600,
                color: AppTheme.text1(context),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              _error ?? '',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 14, color: AppTheme.text2(context)),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _fetchAssessment,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  // ── Risk Score banner ──

  Widget _buildRiskScoreBanner(BuildContext context) {
    final num numScore = _riskScore is num
        ? _riskScore
        : (num.tryParse(_riskScore.toString()) ?? 0);

    Color scoreColor;
    String scoreLabel;
    if (numScore >= 75) {
      scoreColor = AppTheme.danger;
      scoreLabel = 'High Risk';
    } else if (numScore >= 50) {
      scoreColor = AppTheme.warning;
      scoreLabel = 'Medium Risk';
    } else {
      scoreColor = AppTheme.success;
      scoreLabel = 'Low Risk';
    }

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: scoreColor.withOpacity(0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: scoreColor.withOpacity(0.3), width: 1),
      ),
      child: Row(
        children: [
          // Circular score gauge
          SizedBox(
            width: 64,
            height: 64,
            child: Stack(
              alignment: Alignment.center,
              children: [
                SizedBox(
                  width: 64,
                  height: 64,
                  child: CircularProgressIndicator(
                    value: numScore / 100,
                    strokeWidth: 5,
                    backgroundColor: AppTheme.isDark(context)
                        ? AppTheme.darkCard
                        : Colors.white,
                    valueColor: AlwaysStoppedAnimation<Color>(scoreColor),
                  ),
                ),
                Text(
                  numScore.toStringAsFixed(0),
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: scoreColor,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Risk Score',
                  style: TextStyle(
                    fontSize: 12,
                    color: AppTheme.text2(context),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  scoreLabel,
                  style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                    color: scoreColor,
                    letterSpacing: -0.2,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'Based on AI analysis of the submission',
                  style: TextStyle(
                    fontSize: 12,
                    color: AppTheme.text2(context),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── AI Recommendations card ──

  Widget _buildRecommendationsCard(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context), width: 0.5),
        boxShadow: AppTheme.isDark(context) ? null : AppTheme.subtleShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.auto_awesome, size: 18, color: AppTheme.primaryDark),
              const SizedBox(width: 8),
              Text(
                'AI Recommendations',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.text1(context),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ..._aiRecommendations.map((rec) {
            final text = rec is String ? rec : (rec['text'] ?? rec.toString());
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    Icons.lightbulb_outline,
                    size: 16,
                    color: AppTheme.warning,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      text.toString(),
                      style: TextStyle(
                        fontSize: 13,
                        color: AppTheme.text1(context),
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  // ── Assessment summary ──

  Widget _buildAssessmentSummary(BuildContext context) {
    final sub = _assessment ?? {};
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context), width: 0.5),
        boxShadow: AppTheme.isDark(context) ? null : AppTheme.subtleShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.assignment_outlined,
                  size: 18, color: AppTheme.text2(context)),
              const SizedBox(width: 8),
              Text(
                'Assessment Summary',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.text1(context),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _buildDetailRow(context, 'Insured',
              sub['insured_name']?.toString() ?? 'N/A'),
          _buildDetailRow(context, 'Risk Category',
              sub['risk_category']?.toString() ?? 'N/A'),
          _buildDetailRow(
              context, 'Sum Insured', _formatCurrency(sub['sum_insured'])),
          _buildDetailRow(context, 'Territory',
              sub['territory']?.toString() ?? 'N/A'),
        ],
      ),
    );
  }

  Widget _buildDetailRow(BuildContext context, String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(
              label,
              style: TextStyle(
                fontSize: 13,
                color: AppTheme.text2(context),
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: AppTheme.text1(context),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── Form card ──

  Widget _buildFormCard(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context), width: 0.5),
        boxShadow: AppTheme.isDark(context) ? null : AppTheme.subtleShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.edit_note,
                  size: 18, color: AppTheme.text2(context)),
              const SizedBox(width: 8),
              Text(
                'Quote Details',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.text1(context),
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),

          // Quoted Premium
          _buildFieldLabel(context, 'Quoted Premium (GBP) *'),
          const SizedBox(height: 6),
          TextFormField(
            controller: _premiumController,
            keyboardType:
                const TextInputType.numberWithOptions(decimal: true),
            style: TextStyle(
              fontSize: 14,
              color: AppTheme.text1(context),
            ),
            decoration: InputDecoration(
              hintText: 'e.g. 50000.00',
              prefixText: '\u00A3 ',
              prefixStyle: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppTheme.text1(context),
              ),
            ),
            validator: (value) {
              if (value == null || value.trim().isEmpty) {
                return 'Premium is required';
              }
              if (double.tryParse(value.trim()) == null) {
                return 'Enter a valid number';
              }
              return null;
            },
          ),
          const SizedBox(height: 16),

          // Deductible
          _buildFieldLabel(context, 'Deductible (GBP)'),
          const SizedBox(height: 6),
          TextFormField(
            controller: _deductibleController,
            keyboardType:
                const TextInputType.numberWithOptions(decimal: true),
            style: TextStyle(
              fontSize: 14,
              color: AppTheme.text1(context),
            ),
            decoration: InputDecoration(
              hintText: 'e.g. 10000.00',
              prefixText: '\u00A3 ',
              prefixStyle: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppTheme.text1(context),
              ),
            ),
            validator: (value) {
              if (value != null && value.trim().isNotEmpty) {
                if (double.tryParse(value.trim()) == null) {
                  return 'Enter a valid number';
                }
              }
              return null;
            },
          ),
          const SizedBox(height: 16),

          // Conditions
          _buildFieldLabel(context, 'Conditions'),
          const SizedBox(height: 4),
          Text(
            'Comma-separated list',
            style: TextStyle(fontSize: 11, color: AppTheme.textH(context)),
          ),
          const SizedBox(height: 6),
          TextFormField(
            controller: _conditionsController,
            maxLines: 3,
            style: TextStyle(
              fontSize: 14,
              color: AppTheme.text1(context),
            ),
            decoration: const InputDecoration(
              hintText: 'e.g. Annual survey required, Loss runs to be provided',
            ),
          ),
          const SizedBox(height: 16),

          // Subjectivities
          _buildFieldLabel(context, 'Subjectivities'),
          const SizedBox(height: 4),
          Text(
            'Comma-separated list',
            style: TextStyle(fontSize: 11, color: AppTheme.textH(context)),
          ),
          const SizedBox(height: 6),
          TextFormField(
            controller: _subjectivitiesController,
            maxLines: 3,
            style: TextStyle(
              fontSize: 14,
              color: AppTheme.text1(context),
            ),
            decoration: const InputDecoration(
              hintText: 'e.g. Subject to satisfactory survey, NTU 30 days',
            ),
          ),
          const SizedBox(height: 16),

          // Exclusions
          _buildFieldLabel(context, 'Exclusions'),
          const SizedBox(height: 4),
          Text(
            'Comma-separated list',
            style: TextStyle(fontSize: 11, color: AppTheme.textH(context)),
          ),
          const SizedBox(height: 6),
          TextFormField(
            controller: _exclusionsController,
            maxLines: 3,
            style: TextStyle(
              fontSize: 14,
              color: AppTheme.text1(context),
            ),
            decoration: const InputDecoration(
              hintText: 'e.g. War & terrorism, Cyber exclusion',
            ),
          ),
          const SizedBox(height: 16),

          // Validity Period
          _buildFieldLabel(context, 'Validity Period (days)'),
          const SizedBox(height: 6),
          TextFormField(
            controller: _validityController,
            keyboardType: TextInputType.number,
            style: TextStyle(
              fontSize: 14,
              color: AppTheme.text1(context),
            ),
            decoration: const InputDecoration(
              hintText: '30',
            ),
            validator: (value) {
              if (value != null && value.trim().isNotEmpty) {
                if (int.tryParse(value.trim()) == null) {
                  return 'Enter a valid number';
                }
              }
              return null;
            },
          ),
          const SizedBox(height: 16),

          // Additional Terms
          _buildFieldLabel(context, 'Additional Terms / Notes'),
          const SizedBox(height: 6),
          TextFormField(
            controller: _termsController,
            maxLines: 3,
            style: TextStyle(
              fontSize: 14,
              color: AppTheme.text1(context),
            ),
            decoration: const InputDecoration(
              hintText: 'Any additional terms or notes...',
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFieldLabel(BuildContext context, String label) {
    return Text(
      label,
      style: TextStyle(
        fontSize: 13,
        fontWeight: FontWeight.w600,
        color: AppTheme.text1(context),
      ),
    );
  }

  // ── Preview card ──

  Widget _buildPreviewCard(BuildContext context) {
    final premium = double.tryParse(_premiumController.text);
    final deductible = double.tryParse(_deductibleController.text);
    final validity = int.tryParse(_validityController.text) ?? 30;
    final conditions = _conditionsController.text
        .split(',')
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .toList();
    final subjectivities = _subjectivitiesController.text
        .split(',')
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .toList();
    final exclusions = _exclusionsController.text
        .split(',')
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .toList();

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context), width: 0.5),
        boxShadow: AppTheme.isDark(context) ? null : AppTheme.subtleShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.preview_outlined,
                  size: 18, color: AppTheme.text2(context)),
              const SizedBox(width: 8),
              Text(
                'Preview Quote',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.text1(context),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Divider(color: AppTheme.borderOf(context), height: 1),
          const SizedBox(height: 14),

          // Premium
          _buildPreviewRow(
            context,
            'Premium',
            premium != null
                ? '\u00A3${premium.toStringAsFixed(2)}'
                : '\u2014',
            highlight: true,
          ),
          _buildPreviewRow(context, 'Currency', 'GBP'),
          _buildPreviewRow(
            context,
            'Deductible',
            deductible != null
                ? '\u00A3${deductible.toStringAsFixed(2)}'
                : 'None',
          ),
          _buildPreviewRow(
              context, 'Validity', '$validity days'),

          if (conditions.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'Conditions (${conditions.length})',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: AppTheme.text2(context),
              ),
            ),
            const SizedBox(height: 4),
            ...conditions.map((c) => _buildBulletItem(context, c)),
          ],

          if (subjectivities.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'Subjectivities (${subjectivities.length})',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: AppTheme.text2(context),
              ),
            ),
            const SizedBox(height: 4),
            ...subjectivities.map((s) => _buildBulletItem(context, s)),
          ],

          if (exclusions.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'Exclusions (${exclusions.length})',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: AppTheme.text2(context),
              ),
            ),
            const SizedBox(height: 4),
            ...exclusions.map((e) => _buildBulletItem(context, e)),
          ],

          if (_termsController.text.trim().isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'Additional Terms',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: AppTheme.text2(context),
              ),
            ),
            const SizedBox(height: 4),
            Text(
              _termsController.text.trim(),
              style: TextStyle(
                fontSize: 13,
                color: AppTheme.text1(context),
                height: 1.4,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildPreviewRow(BuildContext context, String label, String value,
      {bool highlight = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          SizedBox(
            width: 100,
            child: Text(
              label,
              style: TextStyle(
                fontSize: 13,
                color: AppTheme.text2(context),
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: highlight ? 16 : 14,
                fontWeight: highlight ? FontWeight.w700 : FontWeight.w500,
                color: highlight
                    ? AppTheme.primaryDark
                    : AppTheme.text1(context),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBulletItem(BuildContext context, String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4, left: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '\u2022  ',
            style: TextStyle(
              fontSize: 13,
              color: AppTheme.text2(context),
            ),
          ),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                fontSize: 13,
                color: AppTheme.text1(context),
                height: 1.3,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── Submit button ──

  Widget _buildSubmitButton(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: _isSubmitting ? null : _submitQuote,
        icon: _isSubmitting
            ? SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: AppTheme.isDark(context)
                      ? AppTheme.darkBg
                      : Colors.white,
                ),
              )
            : const Icon(Icons.send, size: 18),
        label: Text(_isSubmitting ? 'Submitting...' : 'Submit Quote'),
        style: ElevatedButton.styleFrom(
          backgroundColor: AppTheme.primaryDark,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          textStyle: const TextStyle(
            fontFamily: 'Inter',
            fontSize: 15,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}
