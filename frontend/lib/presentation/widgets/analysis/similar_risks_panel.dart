import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/precedent_service.dart';

/// SimilarRisksPanel - Shows up to 5 precedent cases similar to the current assessment.
/// Displays similarity score, LOB, decision, and key risk factors for each case.
class SimilarRisksPanel extends StatefulWidget {
  final String assessmentId;

  const SimilarRisksPanel({
    super.key,
    required this.assessmentId,
  });

  @override
  State<SimilarRisksPanel> createState() => _SimilarRisksPanelState();
}

class _SimilarRisksPanelState extends State<SimilarRisksPanel> {
  List<Map<String, dynamic>> _precedents = [];
  bool _isLoading = true;
  bool _isExpanded = true;

  @override
  void initState() {
    super.initState();
    _loadPrecedents();
  }

  Future<void> _loadPrecedents() async {
    setState(() => _isLoading = true);
    final results = await precedentService.searchPrecedents(
      assessmentId: widget.assessmentId,
      limit: 5,
    );
    if (mounted) {
      setState(() {
        _precedents = results;
        _isLoading = false;
      });
    }
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
                      color: AppTheme.analysisPurple.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.manage_search,
                      size: 18,
                      color: AppTheme.analysisPurple,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Similar Precedents',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.text1(context),
                      ),
                    ),
                  ),
                  if (_precedents.isNotEmpty)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: AppTheme.analysisPurple.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        '${_precedents.length}',
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.analysisPurple,
                        ),
                      ),
                    ),
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
            if (_isLoading)
              const Padding(
                padding: EdgeInsets.all(24),
                child: Center(
                  child: Column(
                    children: [
                      SizedBox(
                        width: 28,
                        height: 28,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: AppTheme.analysisPurple,
                        ),
                      ),
                      SizedBox(height: 8),
                      Text(
                        'Searching precedents...',
                        style: TextStyle(fontSize: 12, color: Colors.grey),
                      ),
                    ],
                  ),
                ),
              )
            else if (_precedents.isEmpty)
              Padding(
                padding: const EdgeInsets.all(24),
                child: Center(
                  child: Column(
                    children: [
                      Icon(Icons.search_off, size: 32, color: AppTheme.textH(context)),
                      const SizedBox(height: 8),
                      Text(
                        'No precedents found',
                        style: TextStyle(
                          fontSize: 13,
                          color: AppTheme.text2(context),
                        ),
                      ),
                    ],
                  ),
                ),
              )
            else
              ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: _precedents.length,
                separatorBuilder: (_, __) => Divider(
                  height: 1,
                  color: AppTheme.borderOf(context),
                ),
                itemBuilder: (context, index) {
                  return _PrecedentCard(
                    data: _precedents[index],
                    rank: index + 1,
                  );
                },
              ),
          ],
        ],
      ),
    );
  }
}

class _PrecedentCard extends StatelessWidget {
  final Map<String, dynamic> data;
  final int rank;

  const _PrecedentCard({required this.data, required this.rank});

  Color _decisionColor(String decision) {
    switch (decision.toUpperCase()) {
      case 'GO':
      case 'APPROVED':
        return AppTheme.success;
      case 'NO_GO':
      case 'DECLINED':
        return AppTheme.danger;
      default:
        return AppTheme.warning;
    }
  }

  @override
  Widget build(BuildContext context) {
    final similarity = ((data['similarity_score'] ?? data['score'] ?? 0.0) * 100).toStringAsFixed(0);
    final decision = data['decision']?.toString() ?? 'UNKNOWN';
    final lob = data['line_of_business']?.toString() ?? data['lob']?.toString() ?? 'N/A';
    final title = data['title']?.toString() ?? data['name']?.toString() ?? 'Precedent #$rank';
    final year = data['year']?.toString() ?? data['policy_year']?.toString() ?? '';
    final keyFactors = data['key_factors'] as List? ?? [];

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Rank badge
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: AppTheme.analysisPurple.withOpacity(0.1),
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: Text(
              '#$rank',
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: AppTheme.analysisPurple,
              ),
            ),
          ),
          const SizedBox(width: 12),

          // Content
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        title,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text1(context),
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                      decoration: BoxDecoration(
                        color: _decisionColor(decision).withOpacity(0.1),
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(
                          color: _decisionColor(decision).withOpacity(0.3),
                        ),
                      ),
                      child: Text(
                        decision.replaceAll('_', ' '),
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: _decisionColor(decision),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    _Chip(label: lob, color: AppTheme.analysisClassifier),
                    if (year.isNotEmpty) ...[
                      const SizedBox(width: 6),
                      _Chip(label: year, color: AppTheme.textSecondary),
                    ],
                    const Spacer(),
                    // Similarity bar
                    Text(
                      '$similarity% match',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.analysisPurple,
                      ),
                    ),
                  ],
                ),
                if (keyFactors.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 4,
                    runSpacing: 4,
                    children: keyFactors.take(3).map((f) {
                      return Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceVariant,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          f.toString(),
                          style: TextStyle(
                            fontSize: 10,
                            color: AppTheme.text2(context),
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final Color color;

  const _Chip({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w500,
          color: color,
        ),
      ),
    );
  }
}
