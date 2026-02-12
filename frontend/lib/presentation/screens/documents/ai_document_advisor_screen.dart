import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';

/// AI Document Advisor Screen
/// Replaces static document type selection with AI-driven recommendations.
/// The AI analyzes the assessment and recommends which documents to generate.
class AIDocumentAdvisorScreen extends StatefulWidget {
  final String assessmentId;

  const AIDocumentAdvisorScreen({super.key, required this.assessmentId});

  @override
  State<AIDocumentAdvisorScreen> createState() => _AIDocumentAdvisorScreenState();
}

class _AIDocumentAdvisorScreenState extends State<AIDocumentAdvisorScreen> {
  bool _isAnalyzing = true;
  String? _error;
  List<Map<String, dynamic>> _recommendations = [];
  Set<int> _selectedIndices = {};
  final TextEditingController _requestController = TextEditingController();
  bool _isAddingCustom = false;

  @override
  void initState() {
    super.initState();
    _analyzeAssessment();
  }

  @override
  void dispose() {
    _requestController.dispose();
    super.dispose();
  }

  Future<void> _analyzeAssessment() async {
    setState(() {
      _isAnalyzing = true;
      _error = null;
    });

    try {
      final response = await authService.post(
        '/document-generation/ai-recommend',
        body: {'assessment_id': widget.assessmentId},
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final docs = (data['recommended_documents'] as List?)
            ?.map((d) => Map<String, dynamic>.from(d))
            .toList() ?? [];

        setState(() {
          _recommendations = docs;
          // Auto-select mandatory docs
          _selectedIndices = {};
          for (int i = 0; i < docs.length; i++) {
            if (docs[i]['priority'] == 'mandatory') {
              _selectedIndices.add(i);
            }
          }
          _isAnalyzing = false;
        });
      } else {
        // Fallback: use default recommendations
        _useFallbackRecommendations();
      }
    } catch (e) {
      _useFallbackRecommendations();
    }
  }

  void _useFallbackRecommendations() {
    setState(() {
      _recommendations = [
        {
          'type': 'mrc_slip',
          'name': 'MRC Slip',
          'reason': 'Standard placement document for Lloyd\'s market submissions',
          'priority': 'mandatory',
          'estimated_sections': 12,
        },
        {
          'type': 'policy_wording',
          'name': 'Policy Wording',
          'reason': 'Full policy document with terms, conditions, and coverage details',
          'priority': 'mandatory',
          'estimated_sections': 18,
        },
        {
          'type': 'endorsement_schedule',
          'name': 'Endorsement Schedule',
          'reason': 'List of endorsements and amendments to standard policy terms',
          'priority': 'recommended',
          'estimated_sections': 8,
        },
        {
          'type': 'pricing_summary',
          'name': 'Pricing Summary',
          'reason': 'Technical pricing breakdown with rate derivation',
          'priority': 'recommended',
          'estimated_sections': 6,
        },
        {
          'type': 'risk_survey_report',
          'name': 'Risk Survey Report',
          'reason': 'Comprehensive risk assessment summary for file documentation',
          'priority': 'optional',
          'estimated_sections': 10,
        },
      ];
      _selectedIndices = {0, 1}; // Auto-select mandatory
      _isAnalyzing = false;
    });
  }

  Future<void> _addCustomRequest() async {
    final text = _requestController.text.trim();
    if (text.isEmpty) return;

    setState(() => _isAddingCustom = true);

    try {
      final response = await authService.post(
        '/document-generation/ai-recommend',
        body: {
          'assessment_id': widget.assessmentId,
          'user_request': text,
        },
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final newDocs = (data['recommended_documents'] as List?)
            ?.map((d) => Map<String, dynamic>.from(d))
            .toList() ?? [];

        if (newDocs.isNotEmpty) {
          setState(() {
            final startIndex = _recommendations.length;
            _recommendations.addAll(newDocs);
            for (int i = startIndex; i < _recommendations.length; i++) {
              _selectedIndices.add(i);
            }
          });
        }
      } else {
        // Add as custom doc type
        setState(() {
          _recommendations.add({
            'type': 'custom',
            'name': text,
            'reason': 'Custom document requested by user',
            'priority': 'user_requested',
            'estimated_sections': 8,
          });
          _selectedIndices.add(_recommendations.length - 1);
        });
      }
    } catch (e) {
      setState(() {
        _recommendations.add({
          'type': 'custom',
          'name': text,
          'reason': 'Custom document requested by user',
          'priority': 'user_requested',
          'estimated_sections': 8,
        });
        _selectedIndices.add(_recommendations.length - 1);
      });
    }

    _requestController.clear();
    setState(() => _isAddingCustom = false);
  }

  void _proceedToClauseReview() {
    final selectedDocs = _selectedIndices
        .map((i) => _recommendations[i])
        .toList();

    if (selectedDocs.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select at least one document to generate')),
      );
      return;
    }

    context.go(
      '/documents/clause-review',
      extra: {
        'assessmentId': widget.assessmentId,
        'selectedDocuments': selectedDocs,
      },
    );
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
          onPressed: () => context.pop(),
        ),
        title: const Text(
          'AI Document Advisor',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
          ),
        ),
        centerTitle: true,
      ),
      body: _isAnalyzing ? _buildAnalyzingState() : _buildRecommendations(),
      bottomNavigationBar: _isAnalyzing
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: ElevatedButton(
                  onPressed: _selectedIndices.isNotEmpty ? _proceedToClauseReview : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryDark,
                    foregroundColor: Colors.white,
                    disabledBackgroundColor: AppTheme.border,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: Text(
                    'Generate ${_selectedIndices.length} Document${_selectedIndices.length != 1 ? 's' : ''}',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                  ),
                ),
              ),
            ),
    );
  }

  Widget _buildAnalyzingState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: AppTheme.primaryDark.withValues(alpha: 0.1),
              shape: BoxShape.circle,
            ),
            child: const Center(
              child: SizedBox(
                width: 40,
                height: 40,
                child: CircularProgressIndicator(
                  strokeWidth: 3,
                  color: AppTheme.primaryDark,
                ),
              ),
            ),
          ),
          const SizedBox(height: 24),
          const Text(
            'AI is analyzing your assessment...',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Determining which documents you need and why',
            style: TextStyle(fontSize: 14, color: AppTheme.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _buildRecommendations() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // User request input
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.border),
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _requestController,
                    style: const TextStyle(color: AppTheme.textPrimary, fontSize: 14),
                    decoration: const InputDecoration(
                      hintText: 'I also need a war risks endorsement...',
                      hintStyle: TextStyle(color: AppTheme.textHint, fontSize: 14),
                      border: InputBorder.none,
                      contentPadding: EdgeInsets.zero,
                      isDense: true,
                    ),
                    onSubmitted: (_) => _addCustomRequest(),
                  ),
                ),
                const SizedBox(width: 8),
                _isAddingCustom
                    ? const SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : IconButton(
                        icon: const Icon(Icons.add_circle, color: AppTheme.primaryDark),
                        onPressed: _addCustomRequest,
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(),
                      ),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // Recommendations header
          Text(
            'AI Recommendations',
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            '${_recommendations.length} documents recommended for this assessment',
            style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
          ),
          const SizedBox(height: 16),

          // Document cards
          ...List.generate(_recommendations.length, (index) {
            final doc = _recommendations[index];
            final isSelected = _selectedIndices.contains(index);
            return _buildDocCard(doc, index, isSelected);
          }),
        ],
      ),
    );
  }

  Widget _buildDocCard(Map<String, dynamic> doc, int index, bool isSelected) {
    final priority = doc['priority'] ?? 'optional';
    final priorityColor = priority == 'mandatory'
        ? AppTheme.errorRed
        : priority == 'recommended'
            ? AppTheme.warningAmber
            : priority == 'user_requested'
                ? AppTheme.primaryDark
                : AppTheme.textSecondary;
    final priorityLabel = priority == 'mandatory'
        ? 'MANDATORY'
        : priority == 'recommended'
            ? 'RECOMMENDED'
            : priority == 'user_requested'
                ? 'YOUR REQUEST'
                : 'OPTIONAL';

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: () {
          setState(() {
            if (isSelected) {
              _selectedIndices.remove(index);
            } else {
              _selectedIndices.add(index);
            }
          });
        },
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isSelected
                  ? AppTheme.primaryDark.withValues(alpha: 0.5)
                  : AppTheme.border,
              width: isSelected ? 2 : 1,
            ),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Checkbox
              Container(
                width: 24,
                height: 24,
                decoration: BoxDecoration(
                  color: isSelected ? AppTheme.primaryDark : Colors.transparent,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(
                    color: isSelected ? AppTheme.primaryDark : AppTheme.border,
                    width: 2,
                  ),
                ),
                child: isSelected
                    ? const Icon(Icons.check, color: Colors.white, size: 16)
                    : null,
              ),
              const SizedBox(width: 14),
              // Content
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            doc['name'] ?? doc['type'] ?? 'Document',
                            style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: priorityColor.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            priorityLabel,
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w700,
                              color: priorityColor,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      doc['reason'] ?? '',
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppTheme.textSecondary,
                        height: 1.4,
                      ),
                    ),
                    if (doc['estimated_sections'] != null) ...[
                      const SizedBox(height: 8),
                      Text(
                        '~${doc['estimated_sections']} sections',
                        style: const TextStyle(fontSize: 11, color: AppTheme.textHint),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
