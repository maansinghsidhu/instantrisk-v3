import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/subscription_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// History Screen - List of all past assessments (fetched from API)
class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  String _selectedFilter = 'All';
  final List<String> _filters = ['All', 'GO', 'NO-GO', 'PROCESSING'];
  List<AssessmentItem> _assessments = [];
  bool _isLoading = true;
  String? _error;

  // Subscription service for tier-based UI
  final SubscriptionService _subscriptionService = SubscriptionService();

  // Tier helpers
  bool get _isPremium => _subscriptionService.isPremium;
  bool get _isBasicOrHigher => _subscriptionService.isBasic || _subscriptionService.isPremium;
  bool get _isTrial => _subscriptionService.isTrial;

  @override
  void initState() {
    super.initState();
    _checkAuthAndFetch();
  }

  Future<void> _checkAuthAndFetch() async {
    if (!authService.isLoggedIn) {
      if (mounted) {
        context.go('/login');
      }
      return;
    }
    _fetchAssessments();
  }

  Future<void> _fetchAssessments() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await authService.get('/assessments/?page=1&page_size=50');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final List<dynamic> items = data['items'] ?? [];

        setState(() {
          _assessments = items.map((item) => AssessmentItem(
            id: item['id']?.toString() ?? '',
            referenceNumber: item['reference_number'] ?? '',
            title: item['title'] ?? 'Unknown',
            company: item['insured_name'] ?? 'Unknown',
            status: _mapStatus(item),
            riskScore: item['risk_score'] ?? 0,
            premium: (item['premium'] is num) ? (item['premium'] as num).toDouble() : 0.0,
            date: DateTime.tryParse(item['created_at'] ?? '') ?? DateTime.now(),
            riskCategory: item['risk_category'] ?? '',
            territory: item['territory'] ?? '',
          )).toList();
          _isLoading = false;
        });
      } else if (response.statusCode == 401) {
        if (mounted) {
          context.go('/login');
        }
      } else {
        setState(() {
          _error = 'Failed to load assessments';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Error: $e';
        _isLoading = false;
      });
    }
  }

  String _mapStatus(Map<String, dynamic> item) {
    // Check if assessment is still processing
    // Backend uses: draft, pending_review, in_progress, completed, cancelled, failed
    final status = item['status']?.toString().toLowerCase() ?? '';
    final isStillProcessing = status == 'draft' ||
                               status == 'pending_review' ||
                               status == 'in_progress' ||
                               status == 'processing' ||
                               status == 'pending' ||
                               status == 'uploading';
    if (isStillProcessing) {
      return 'PROCESSING';
    }

    // Map the decision
    final decision = item['decision']?.toString().toLowerCase() ?? '';
    switch (decision) {
      case 'go':
        return 'GO';
      case 'no_go':
        return 'NO-GO';
      case 'refer':
        return 'REFER';
      default:
        return 'PENDING';
    }
  }

  List<AssessmentItem> get _filteredAssessments {
    if (_selectedFilter == 'All') return _assessments;
    return _assessments.where((a) => a.status == _selectedFilter).toList();
  }

  Future<void> _deleteAssessment(AssessmentItem assessment) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Assessment'),
        content: Text('Are you sure you want to delete "${assessment.title}"? This will also remove all generated documents. This cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: AppTheme.error),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirm != true) return;

    try {
      final response = await authService.delete('/assessments/${assessment.id}');
      if (response.statusCode == 200 || response.statusCode == 204) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Assessment deleted')),
          );
          _fetchAssessments();
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete: $e')),
        );
      }
    }
  }

  // Rename dialog (available for all tiers)
  Future<void> _showRenameDialog(AssessmentItem assessment) async {
    final controller = TextEditingController(text: assessment.title);

    final result = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Rename Analysis'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(
            labelText: 'Account Name',
            hintText: 'Enter account or company name',
          ),
          autofocus: true,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, controller.text),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryDark,
              foregroundColor: Colors.white,
            ),
            child: const Text('Save'),
          ),
        ],
      ),
    );

    if (result != null && result.isNotEmpty && result != assessment.title) {
      await _updateAssessmentTitle(assessment.id, result);
    }
  }

  Future<void> _updateAssessmentTitle(String id, String newTitle) async {
    try {
      final response = await authService.put(
        '/assessments/$id',
        body: {'title': newTitle},
      );
      if (response.statusCode == 200) {
        await _fetchAssessments();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Analysis renamed successfully'),
              backgroundColor: AppTheme.success,
            ),
          );
        }
      } else {
        throw Exception('Failed to rename');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to rename: $e'),
            backgroundColor: AppTheme.danger,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.go('/home/intake'),
        backgroundColor: AppTheme.primaryDark,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add),
        label: Text(
          l10n.startAnalysis,
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Header
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    l10n.reports,
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.text1(context),
                      fontFamily: 'Inter',
                    ),
                  ),
                  IconButton(
                    icon: Icon(Icons.refresh, color: AppTheme.text1(context), size: 20),
                    onPressed: _fetchAssessments,
                  ),
                ],
              ),
            ),

            // Filter chips
            SizedBox(
              height: 40,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: _filters.length,
                itemBuilder: (context, index) {
                  final filter = _filters[index];
                  final isSelected = filter == _selectedFilter;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: FilterChip(
                      label: Text(filter),
                      selected: isSelected,
                      onSelected: (selected) {
                        setState(() => _selectedFilter = filter);
                      },
                      backgroundColor: AppTheme.surfaceOf(context),
                      selectedColor: AppTheme.primaryDark.withOpacity(0.2),
                      labelStyle: TextStyle(
                        color: isSelected ? AppTheme.primaryDark : AppTheme.text2(context),
                        fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                      ),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(20),
                        side: BorderSide(
                          color: isSelected ? AppTheme.primaryDark : AppTheme.borderOf(context),
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: 16),

            // Content
            Expanded(
              child: _isLoading
                  ? const Center(child: CircularProgressIndicator())
                  : _error != null
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.error_outline, size: 48, color: AppTheme.danger),
                              SizedBox(height: 16),
                              Text(_error!, style: TextStyle(color: AppTheme.text2(context))),
                              const SizedBox(height: 16),
                              ElevatedButton(
                                onPressed: _fetchAssessments,
                                child: Text(l10n.retry),
                              ),
                            ],
                          ),
                        )
                      : _filteredAssessments.isEmpty
                          ? Center(
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Container(
                                    width: 60,
                                    height: 60,
                                    decoration: BoxDecoration(
                                      color: AppTheme.primaryDark.withOpacity(0.1),
                                      shape: BoxShape.circle,
                                    ),
                                    child: Icon(Icons.assessment_outlined, size: 28, color: AppTheme.primaryDark),
                                  ),
                                  const SizedBox(height: 16),
                                  Text(
                                    l10n.noData,
                                    style: TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.w600,
                                      color: AppTheme.text1(context),
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    l10n.uploadDocument,
                                    textAlign: TextAlign.center,
                                    style: TextStyle(color: AppTheme.text2(context)),
                                  ),
                                  const SizedBox(height: 24),
                                  ElevatedButton.icon(
                                    onPressed: () => context.go('/home/intake'),
                                    icon: const Icon(Icons.add),
                                    label: Text(l10n.startAnalysis),
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: AppTheme.primaryDark,
                                      foregroundColor: Colors.white,
                                      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(12),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            )
                          : RefreshIndicator(
                              onRefresh: _fetchAssessments,
                              child: ListView.builder(
                                padding: const EdgeInsets.symmetric(horizontal: 16),
                                itemCount: _filteredAssessments.length,
                                itemBuilder: (context, index) {
                                  return _buildAssessmentCard(_filteredAssessments[index]);
                                },
                              ),
                            ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAssessmentCard(AssessmentItem assessment) {
    Color statusColor;
    switch (assessment.status) {
      case 'GO':
        statusColor = AppTheme.success;
        break;
      case 'NO-GO':
        statusColor = AppTheme.danger;
        break;
      case 'REFER':
        statusColor = AppTheme.warning;
        break;
      case 'PROCESSING':
        statusColor = AppTheme.primaryDark;
        break;
      default:
        statusColor = AppTheme.textH(context);
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () => context.go('/reports/results/${assessment.id}'),
          onLongPress: () => _showRenameDialog(assessment), // Rename on long press (all tiers)
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            assessment.referenceNumber.isNotEmpty
                                ? assessment.referenceNumber
                                : '#${assessment.id}',
                            style: TextStyle(
                              fontSize: 12,
                              color: AppTheme.textH(context),
                              fontFamily: 'Inter',
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            assessment.title,
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.text1(context),
                              fontFamily: 'Inter',
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: statusColor.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        assessment.status,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: statusColor,
                          fontFamily: 'Inter',
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    GestureDetector(
                      onTap: () => _deleteAssessment(assessment),
                      child: Icon(Icons.delete_outline, size: 20, color: AppTheme.textH(context)),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Icon(Icons.business, size: 16, color: AppTheme.textH(context)),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        assessment.company,
                        style: TextStyle(
                          fontSize: 14,
                          color: AppTheme.text2(context),
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
                // Show additional metrics only for Basic+ users
                if (_isBasicOrHigher) ...[
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      if (assessment.premium > 0)
                        _buildMetricChip(
                          Icons.attach_money,
                          _formatCurrency(assessment.premium),
                          AppTheme.success,
                        ),
                      if (assessment.premium > 0) const SizedBox(width: 8),
                      if (assessment.riskCategory.isNotEmpty)
                        _buildMetricChip(
                          Icons.category_outlined,
                          assessment.riskCategory,
                          AppTheme.primaryDark,
                        ),
                    ],
                  ),
                ],
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    // Show hint for rename on long press
                    Text(
                      'Long press to rename',
                      style: TextStyle(
                        fontSize: 10,
                        color: AppTheme.textH(context).withOpacity(0.6),
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                    Text(
                      _formatDate(assessment.date),
                      style: TextStyle(
                        fontSize: 12,
                        color: AppTheme.textH(context),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildMetricChip(IconData icon, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(
            value,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  Color _getRiskColor(int score) {
    if (score >= 70) return AppTheme.success;
    if (score >= 40) return AppTheme.warning;
    return AppTheme.danger;
  }

  String _formatCurrency(double value) {
    if (value >= 1000000) {
      return '${(value / 1000000).toStringAsFixed(1)}M';
    } else if (value >= 1000) {
      return '${(value / 1000).toStringAsFixed(1)}k';
    }
    return value.toStringAsFixed(0);
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final diff = now.difference(date);

    if (diff.inDays == 0) {
      return '${date.hour}:${date.minute.toString().padLeft(2, '0')}';
    } else if (diff.inDays == 1) {
      return '1d';
    } else if (diff.inDays < 7) {
      return '${diff.inDays}d';
    } else {
      return '${date.day}/${date.month}/${date.year}';
    }
  }
}

class AssessmentItem {
  final String id;
  final String referenceNumber;
  final String title;
  final String company;
  final String status;
  final int riskScore;
  final double premium;
  final DateTime date;
  final String riskCategory;
  final String territory;

  AssessmentItem({
    required this.id,
    this.referenceNumber = '',
    required this.title,
    required this.company,
    required this.status,
    required this.riskScore,
    required this.premium,
    required this.date,
    this.riskCategory = '',
    this.territory = '',
  });
}
