import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/services/auth_service.dart';
import '../../../core/theme/app_theme.dart';

class BrokerSubmissionsScreen extends StatefulWidget {
  const BrokerSubmissionsScreen({super.key});

  @override
  State<BrokerSubmissionsScreen> createState() =>
      _BrokerSubmissionsScreenState();
}

class _BrokerSubmissionsScreenState extends State<BrokerSubmissionsScreen> {
  List<dynamic> _submissions = [];
  bool _isLoading = true;
  String? _error;
  String _filter = 'all';
  int _page = 1;

  static const List<_FilterOption> _filters = [
    _FilterOption('all', 'All'),
    _FilterOption('submitted', 'Submitted'),
    _FilterOption('under_review', 'Under Review'),
    _FilterOption('quote_pending', 'Quote Pending'),
    _FilterOption('bound', 'Bound'),
    _FilterOption('declined', 'Declined'),
  ];

  @override
  void initState() {
    super.initState();
    _loadSubmissions();
  }

  Future<void> _loadSubmissions() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final filter = _filter;
      final page = _page;
      final response = await authService
          .get('/broker-portal/all-submissions?status_filter=$filter&page=$page');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _submissions = data is List ? data : (data['items'] ?? []);
          _isLoading = false;
        });
      } else {
        setState(() {
          _error = 'Failed to load submissions (${response.statusCode}).';
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

  Future<void> _onRefresh() async {
    _page = 1;
    await _loadSubmissions();
  }

  void _onFilterSelected(String value) {
    if (_filter == value) return;
    setState(() {
      _filter = value;
      _page = 1;
    });
    _loadSubmissions();
  }

  // ── Status colour mapping ──

  Color _statusColor(String status) {
    switch (status) {
      case 'submitted':
        return Colors.orange;
      case 'under_review':
        return Colors.blue;
      case 'quote_pending':
        return const Color(0xFF7C3AED); // purple
      case 'bound':
        return Colors.green;
      case 'declined':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  String _statusLabel(String status) {
    switch (status) {
      case 'submitted':
        return 'Submitted';
      case 'under_review':
        return 'Under Review';
      case 'quote_pending':
        return 'Quote Pending';
      case 'bound':
        return 'Bound';
      case 'declined':
        return 'Declined';
      default:
        return status.replaceAll('_', ' ');
    }
  }

  String _formatSumInsured(dynamic value) {
    if (value == null) return '-';
    final num amount = value is num ? value : num.tryParse(value.toString()) ?? 0;
    if (amount >= 1000000) {
      final millions = amount / 1000000;
      return millions == millions.truncateToDouble()
          ? '\u00A3${millions.toInt()}m'
          : '\u00A3${millions.toStringAsFixed(1)}m';
    } else if (amount >= 1000) {
      return '\u00A3${(amount / 1000).toStringAsFixed(0)}k';
    }
    return '\u00A3${amount.toStringAsFixed(0)}';
  }

  String _formatDate(String? isoDate) {
    if (isoDate == null || isoDate.isEmpty) return '-';
    try {
      final dt = DateTime.parse(isoDate);
      return '${dt.day.toString().padLeft(2, '0')}/${dt.month.toString().padLeft(2, '0')}/${dt.year}';
    } catch (_) {
      return isoDate;
    }
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
          'Broker Submissions',
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
      body: Column(
        children: [
          _buildFilterBar(context),
          Expanded(child: _buildBody(context)),
        ],
      ),
    );
  }

  // ── Filter chips ──

  Widget _buildFilterBar(BuildContext context) {
    return Container(
      color: AppTheme.surfaceOf(context),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: _filters.map((f) {
            final isSelected = _filter == f.value;
            return Padding(
              padding: const EdgeInsets.only(right: 8),
              child: GestureDetector(
                onTap: () => _onFilterSelected(f.value),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  decoration: BoxDecoration(
                    color: isSelected
                        ? AppTheme.primaryDark.withOpacity(0.1)
                        : AppTheme.isDark(context)
                            ? AppTheme.darkCard
                            : AppTheme.surfaceVariant,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: isSelected
                          ? AppTheme.primaryDark
                          : AppTheme.borderOf(context),
                      width: isSelected ? 1.5 : 0.5,
                    ),
                  ),
                  child: Text(
                    f.label,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight:
                          isSelected ? FontWeight.w600 : FontWeight.w500,
                      color: isSelected
                          ? AppTheme.primaryDark
                          : AppTheme.text2(context),
                    ),
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  // ── Body: loading / error / empty / list ──

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

    if (_submissions.isEmpty) {
      return _buildEmptyState(context);
    }

    return RefreshIndicator(
      color: AppTheme.primaryDark,
      backgroundColor: AppTheme.surfaceOf(context),
      onRefresh: _onRefresh,
      child: ListView.builder(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        itemCount: _submissions.length,
        itemBuilder: (ctx, index) =>
            _buildSubmissionCard(context, _submissions[index]),
      ),
    );
  }

  // ── Empty state ──

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.inbox_outlined,
              size: 64,
              color: AppTheme.text2(context).withOpacity(0.4),
            ),
            const SizedBox(height: 16),
            Text(
              'No submissions found',
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w600,
                color: AppTheme.text1(context),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              _filter == 'all'
                  ? 'There are no broker submissions yet.'
                  : 'No submissions match the selected filter.',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                color: AppTheme.text2(context),
              ),
            ),
            const SizedBox(height: 24),
            OutlinedButton.icon(
              onPressed: _onRefresh,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('Refresh'),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppTheme.text1(context),
                side: BorderSide(color: AppTheme.borderOf(context)),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
              ),
            ),
          ],
        ),
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
              onPressed: _loadSubmissions,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  // ── Submission card ──

  Widget _buildSubmissionCard(BuildContext context, dynamic submission) {
    final String submissionId =
        (submission['submission_id'] ?? '').toString();
    final String insuredName =
        (submission['insured_name'] ?? 'Unknown').toString();
    final String riskCategory =
        (submission['risk_category'] ?? '').toString();
    final String status = (submission['status'] ?? '').toString();
    final String createdAt = (submission['created_at'] ?? '').toString();
    final bool hasAnalysis = submission['has_analysis'] == true;
    final bool hasQuote = submission['has_quote'] == true;
    final dynamic riskScore = submission['risk_score'];
    final dynamic sumInsured = submission['sum_insured'];
    final Map<String, dynamic> broker =
        submission['broker'] is Map<String, dynamic>
            ? submission['broker'] as Map<String, dynamic>
            : {};
    final String brokerName = (broker['name'] ?? 'Unknown Broker').toString();

    final Color sColor = _statusColor(status);

    return GestureDetector(
      onTap: () => context.go('/home/broker-submissions/$submissionId'),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: AppTheme.surfaceOf(context),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: AppTheme.borderOf(context),
            width: 0.5,
          ),
          boxShadow: AppTheme.isDark(context) ? null : AppTheme.subtleShadow,
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Row 1: Insured name + status badge ──
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      insuredName,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.text1(context),
                        letterSpacing: -0.1,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const SizedBox(width: 12),
                  _buildStatusBadge(sColor, _statusLabel(status)),
                ],
              ),

              const SizedBox(height: 8),

              // ── Row 2: Risk category badge + sum insured ──
              Row(
                children: [
                  if (riskCategory.isNotEmpty) ...[
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: AppTheme.isDark(context)
                            ? AppTheme.darkCard
                            : AppTheme.surfaceVariant,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        riskCategory.toUpperCase(),
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text2(context),
                          letterSpacing: 0.5,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                  ],
                  Text(
                    _formatSumInsured(sumInsured),
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.text1(context),
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 8),

              // ── Row 3: Broker name ──
              Row(
                children: [
                  Icon(
                    Icons.business_center_outlined,
                    size: 14,
                    color: AppTheme.text2(context),
                  ),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      brokerName,
                      style: TextStyle(
                        fontSize: 13,
                        color: AppTheme.text2(context),
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 10),

              // ── Row 4: Meta chips (date, risk score, quoted) ──
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  // Created date
                  _buildMetaChip(
                    context,
                    icon: Icons.calendar_today_outlined,
                    label: _formatDate(createdAt),
                  ),

                  // Risk score badge
                  if (hasAnalysis && riskScore != null)
                    _buildRiskScoreBadge(context, riskScore),

                  // Quoted indicator
                  if (hasQuote) _buildQuotedBadge(context),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ── Status badge ──

  Widget _buildStatusBadge(Color color, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: color,
        ),
      ),
    );
  }

  // ── Meta chip (date etc.) ──

  Widget _buildMetaChip(BuildContext context,
      {required IconData icon, required String label}) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 13, color: AppTheme.text2(context)),
        const SizedBox(width: 4),
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            color: AppTheme.text2(context),
          ),
        ),
      ],
    );
  }

  // ── Risk score badge ──

  Widget _buildRiskScoreBadge(BuildContext context, dynamic score) {
    final num numScore =
        score is num ? score : (num.tryParse(score.toString()) ?? 0);

    Color badgeColor;
    if (numScore >= 75) {
      badgeColor = AppTheme.danger;
    } else if (numScore >= 50) {
      badgeColor = AppTheme.warning;
    } else {
      badgeColor = AppTheme.success;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: badgeColor.withOpacity(0.12),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.shield_outlined, size: 12, color: badgeColor),
          const SizedBox(width: 4),
          Text(
            'Risk ${numScore.toStringAsFixed(0)}',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: badgeColor,
            ),
          ),
        ],
      ),
    );
  }

  // ── Quoted indicator ──

  Widget _buildQuotedBadge(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppTheme.info.withOpacity(0.12),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.description_outlined, size: 12, color: AppTheme.info),
          const SizedBox(width: 4),
          Text(
            'Quoted',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: AppTheme.info,
            ),
          ),
        ],
      ),
    );
  }
}

// ── Filter option helper ──

class _FilterOption {
  final String value;
  final String label;
  const _FilterOption(this.value, this.label);
}
