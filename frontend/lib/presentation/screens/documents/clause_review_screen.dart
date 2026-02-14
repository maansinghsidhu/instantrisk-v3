import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';

/// Clause Review Screen
/// Shows clause selections with source badges before generation.
/// Users can swap between their uploaded clauses, ACORD standard, or AI-generated.
class ClauseReviewScreen extends StatefulWidget {
  final String assessmentId;
  final List<Map<String, dynamic>> selectedDocuments;

  const ClauseReviewScreen({
    super.key,
    required this.assessmentId,
    required this.selectedDocuments,
  });

  @override
  State<ClauseReviewScreen> createState() => _ClauseReviewScreenState();
}

class _ClauseReviewScreenState extends State<ClauseReviewScreen> {
  bool _isLoading = true;
  Map<String, List<Map<String, dynamic>>> _clausesByDoc = {};
  final Set<String> _deselectedClauses = {}; // clause_ids the user has deselected

  @override
  void initState() {
    super.initState();
    _loadClauses();
  }

  Future<void> _loadClauses() async {
    setState(() => _isLoading = true);

    try {
      final response = await authService.post(
        '/document-generation/ai-clauses',
        body: {
          'assessment_id': widget.assessmentId,
          'document_types': widget.selectedDocuments.map((d) => d['type']).toList(),
        },
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final clauses = data['clauses_by_document'] as Map<String, dynamic>?;
        if (clauses != null) {
          setState(() {
            _clausesByDoc = clauses.map((key, value) {
              return MapEntry(
                key,
                (value as List).map((c) => Map<String, dynamic>.from(c)).toList(),
              );
            });
            _isLoading = false;
          });
          return;
        }
      }
      _useFallbackClauses();
    } catch (e) {
      _useFallbackClauses();
    }
  }

  void _useFallbackClauses() {
    setState(() {
      for (final doc in widget.selectedDocuments) {
        final docType = doc['type'] ?? 'unknown';
        _clausesByDoc[docType] = [
          {
            'clause_id': 'preamble',
            'name': 'Preamble & Recitals',
            'source': 'ai_generated',
            'content_preview': 'Standard opening recitals with party definitions...',
            'is_mandatory': true,
          },
          {
            'clause_id': 'insuring_agreement',
            'name': 'Insuring Agreement',
            'source': 'acord',
            'content_preview': 'The Insurer agrees to indemnify the Insured...',
            'is_mandatory': true,
          },
          {
            'clause_id': 'definitions',
            'name': 'Definitions',
            'source': 'user_uploaded',
            'content_preview': 'As used in this Policy, the following terms shall have the meanings...',
            'is_mandatory': true,
          },
          {
            'clause_id': 'conditions',
            'name': 'General Conditions',
            'source': 'acord',
            'content_preview': 'Standard general conditions including notice, subrogation...',
            'is_mandatory': false,
          },
          {
            'clause_id': 'exclusions',
            'name': 'Exclusions',
            'source': 'ai_generated',
            'content_preview': 'This Policy does not cover loss, damage or liability...',
            'is_mandatory': true,
          },
        ];
      }
      _isLoading = false;
    });
  }

  void _proceedToGeneration() {
    // Filter out deselected clauses before sending to generation
    final filteredClauses = _clausesByDoc.map((docType, clauses) {
      return MapEntry(
        docType,
        clauses.where((c) => !_deselectedClauses.contains(c['clause_id'])).toList(),
      );
    });

    context.go(
      '/documents/generation-progress',
      extra: {
        'assessmentId': widget.assessmentId,
        'selectedDocuments': widget.selectedDocuments,
        'clausesByDoc': filteredClauses,
      },
    );
  }

  void _toggleClause(String clauseId) {
    setState(() {
      if (_deselectedClauses.contains(clauseId)) {
        _deselectedClauses.remove(clauseId);
      } else {
        _deselectedClauses.add(clauseId);
      }
    });
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
          'Clause Review',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
          ),
        ),
        centerTitle: true,
      ),
      body: _isLoading ? _buildLoadingState() : _buildClauseList(),
      bottomNavigationBar: _isLoading
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // Source summary
                    _buildSourceSummary(),
                    const SizedBox(height: 12),
                    ElevatedButton(
                      onPressed: _proceedToGeneration,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primaryDark,
                        foregroundColor: Colors.white,
                        minimumSize: const Size(double.infinity, 52),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.auto_awesome, size: 20),
                          SizedBox(width: 8),
                          Text(
                            'Generate Documents',
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildSourceSummary() {
    int userCount = 0, acordCount = 0, aiCount = 0, totalSelected = 0, totalAll = 0;
    for (final clauses in _clausesByDoc.values) {
      for (final clause in clauses) {
        totalAll++;
        if (_deselectedClauses.contains(clause['clause_id'])) continue;
        totalSelected++;
        switch (clause['source']) {
          case 'user_uploaded':
            userCount++;
            break;
          case 'acord':
          case 'template':
            acordCount++;
            break;
          default:
            aiCount++;
        }
      }
    }

    return Column(
      children: [
        Text(
          '$totalSelected of $totalAll clauses selected',
          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
        ),
        const SizedBox(height: 6),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (userCount > 0) _buildSourceChip('$userCount Your Wording', AppTheme.phaseCompose),
            if (acordCount > 0) _buildSourceChip('$acordCount ACORD', AppTheme.phaseResearch),
            if (aiCount > 0) _buildSourceChip('$aiCount Engine Generated', AppTheme.textSecondary),
          ],
        ),
      ],
    );
  }

  Widget _buildSourceChip(String label, Color color) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 4),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color),
      ),
    );
  }

  Widget _buildLoadingState() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(),
          SizedBox(height: 16),
          Text(
            'Searching for best clauses...',
            style: TextStyle(color: AppTheme.textSecondary),
          ),
          SizedBox(height: 4),
          Text(
            'Checking your uploads, ACORD library, and AI',
            style: TextStyle(fontSize: 12, color: AppTheme.textHint),
          ),
        ],
      ),
    );
  }

  Widget _buildClauseList() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ...widget.selectedDocuments.map((doc) {
            final docType = doc['type'] ?? 'unknown';
            final docName = doc['name'] ?? doc['type'] ?? 'Document';
            final clauses = _clausesByDoc[docType] ?? [];

            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Document header
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryDark.withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.description, color: AppTheme.primaryDark, size: 18),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          docName,
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                      ),
                      Text(
                        '${clauses.length} clauses',
                        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 8),
                // Clauses
                ...clauses.map((clause) => _buildClauseCard(clause)),
                const SizedBox(height: 20),
              ],
            );
          }),
        ],
      ),
    );
  }

  Widget _buildClauseCard(Map<String, dynamic> clause) {
    final source = clause['source'] ?? 'ai_generated';
    final sourceBadge = _getSourceBadge(source);
    final isMandatory = clause['is_mandatory'] ?? false;
    final clauseId = clause['clause_id'] ?? '';
    final isSelected = !_deselectedClauses.contains(clauseId);

    return GestureDetector(
      onTap: isMandatory ? null : () => _toggleClause(clauseId),
      child: AnimatedOpacity(
        opacity: isSelected ? 1.0 : 0.5,
        duration: const Duration(milliseconds: 200),
        child: Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: isSelected ? AppTheme.surface : AppTheme.background,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: isSelected ? AppTheme.border : AppTheme.border.withValues(alpha: 0.5),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  // Checkbox for non-mandatory clauses
                  if (!isMandatory)
                    Padding(
                      padding: const EdgeInsets.only(right: 10),
                      child: Icon(
                        isSelected ? Icons.check_circle : Icons.circle_outlined,
                        color: isSelected ? AppTheme.primaryDark : AppTheme.textHint,
                        size: 20,
                      ),
                    ),
                  Expanded(
                    child: Text(
                      clause['name'] ?? 'Clause',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: isSelected ? AppTheme.textPrimary : AppTheme.textSecondary,
                      ),
                    ),
                  ),
                  sourceBadge,
                  if (isMandatory) ...[
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppTheme.errorRed.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: const Text(
                        'REQ',
                        style: TextStyle(
                          fontSize: 9,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.errorRed,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
              if (clause['content_preview'] != null) ...[
                const SizedBox(height: 6),
                Text(
                  clause['content_preview'],
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppTheme.textSecondary,
                    height: 1.4,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _getSourceBadge(String source) {
    Color color;
    String label;

    switch (source) {
      case 'user_uploaded':
        color = AppTheme.phaseCompose;
        label = 'Your Wording';
        break;
      case 'acord':
        color = AppTheme.phaseResearch;
        label = 'ACORD Standard';
        break;
      case 'template':
        color = AppTheme.corporateBlue;
        label = 'Template';
        break;
      default:
        color = AppTheme.textSecondary;
        label = 'Engine Generated';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: color,
        ),
      ),
    );
  }
}
