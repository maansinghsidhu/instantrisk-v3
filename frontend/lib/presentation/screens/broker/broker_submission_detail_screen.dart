import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/services/auth_service.dart';
import '../../../core/theme/app_theme.dart';

class BrokerSubmissionDetailScreen extends StatefulWidget {
  final String submissionId;
  const BrokerSubmissionDetailScreen({super.key, required this.submissionId});

  @override
  State<BrokerSubmissionDetailScreen> createState() =>
      _BrokerSubmissionDetailScreenState();
}

class _BrokerSubmissionDetailScreenState
    extends State<BrokerSubmissionDetailScreen> {
  Map<String, dynamic>? _submission;
  Map<String, dynamic>? _quote;
  List<dynamic> _documents = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchSubmissionDetail();
  }

  Future<void> _fetchSubmissionDetail() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final response = await authService
          .get('/broker-portal/submissions/${widget.submissionId}');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        setState(() {
          _submission = data['submission'] as Map<String, dynamic>?;
          _quote = data['quote'] as Map<String, dynamic>?;
          _documents = (data['documents'] as List<dynamic>?) ?? [];
          _isLoading = false;
        });
      } else if (response.statusCode == 404) {
        setState(() {
          _error = 'Submission not found.';
          _isLoading = false;
        });
      } else {
        setState(() {
          _error = 'Failed to load submission (${response.statusCode}).';
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

  // ── Status helpers ──

  static const List<String> _statusSteps = [
    'submitted',
    'under_review',
    'quote_pending',
  ];

  Color _statusColor(String status) {
    switch (status) {
      case 'submitted':
        return Colors.orange;
      case 'under_review':
        return Colors.blue;
      case 'quote_pending':
        return Colors.purple;
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
        return status.replaceAll('_', ' ').toUpperCase();
    }
  }

  String _formatCurrency(dynamic value) {
    if (value == null) return 'N/A';
    final num amount = value is num ? value : num.tryParse(value.toString()) ?? 0;
    if (amount >= 1000000) {
      return '\u00A3${(amount / 1000000).toStringAsFixed(1)}M';
    } else if (amount >= 1000) {
      return '\u00A3${(amount / 1000).toStringAsFixed(0)}K';
    }
    return '\u00A3${amount.toStringAsFixed(0)}';
  }

  // ── Build ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        title: Text(
          'Submission Details',
          style: TextStyle(color: AppTheme.text1(context)),
        ),
        backgroundColor: AppTheme.surfaceOf(context),
        iconTheme: IconThemeData(color: AppTheme.text1(context)),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchSubmissionDetail,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.error_outline, size: 48, color: AppTheme.danger),
              const SizedBox(height: 16),
              Text(
                _error!,
                textAlign: TextAlign.center,
                style: TextStyle(color: AppTheme.text2(context), fontSize: 15),
              ),
              const SizedBox(height: 24),
              OutlinedButton.icon(
                onPressed: _fetchSubmissionDetail,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_submission == null) {
      return Center(
        child: Text(
          'No submission data.',
          style: TextStyle(color: AppTheme.text2(context)),
        ),
      );
    }

    final sub = _submission!;
    final status = (sub['status'] as String?) ?? 'submitted';

    return RefreshIndicator(
      onRefresh: _fetchSubmissionDetail,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Header card
          _buildHeaderCard(context, sub, status),
          const SizedBox(height: 16),

          // Status timeline
          _buildStatusTimeline(context, status),
          const SizedBox(height: 16),

          // Details card
          _buildDetailsCard(context, sub),
          const SizedBox(height: 16),

          // Quote section
          _buildQuoteSection(context),
          const SizedBox(height: 16),

          // Documents section
          if (_documents.isNotEmpty) _buildDocumentsSection(context),
        ],
      ),
    );
  }

  // ── Header card ──

  Widget _buildHeaderCard(
      BuildContext context, Map<String, dynamic> sub, String status) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context), width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  sub['insured_name'] ?? 'Unknown Insured',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.text1(context),
                    letterSpacing: -0.3,
                  ),
                ),
              ),
              _buildStatusBadge(context, status),
            ],
          ),
          const SizedBox(height: 8),
          if (sub['reference'] != null)
            Text(
              'Ref: ${sub['reference']}',
              style: TextStyle(
                fontSize: 13,
                color: AppTheme.text2(context),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildStatusBadge(BuildContext context, String status) {
    final color = _statusColor(status);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        _statusLabel(status),
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.w600,
          fontSize: 12,
        ),
      ),
    );
  }

  // ── Status timeline ──

  Widget _buildStatusTimeline(BuildContext context, String currentStatus) {
    // Determine the ordered list including the terminal state
    final bool isDeclined = currentStatus == 'declined';
    final bool isBound = currentStatus == 'bound';

    final List<String> steps = [
      ..._statusSteps,
      if (isDeclined) 'declined' else 'bound',
    ];

    // Find how far along we are
    int currentIndex = steps.indexOf(currentStatus);
    if (currentIndex < 0) currentIndex = 0;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context), width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Status Timeline',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w600,
              color: AppTheme.text1(context),
            ),
          ),
          const SizedBox(height: 16),
          ...List.generate(steps.length, (i) {
            final step = steps[i];
            final bool isCompleted = i < currentIndex;
            final bool isCurrent = i == currentIndex;
            final bool isLast = i == steps.length - 1;
            final color = isCurrent
                ? _statusColor(step)
                : isCompleted
                    ? AppTheme.success
                    : AppTheme.isDark(context)
                        ? Colors.white24
                        : Colors.grey.shade300;

            return Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Dot + connector line
                SizedBox(
                  width: 28,
                  child: Column(
                    children: [
                      Container(
                        width: isCurrent ? 16 : 12,
                        height: isCurrent ? 16 : 12,
                        decoration: BoxDecoration(
                          color: (isCompleted || isCurrent)
                              ? color
                              : Colors.transparent,
                          border: Border.all(color: color, width: 2),
                          shape: BoxShape.circle,
                        ),
                        child: isCompleted
                            ? const Icon(Icons.check,
                                size: 8, color: Colors.white)
                            : null,
                      ),
                      if (!isLast)
                        Container(
                          width: 2,
                          height: 28,
                          color: isCompleted
                              ? AppTheme.success
                              : AppTheme.isDark(context)
                                  ? Colors.white12
                                  : Colors.grey.shade200,
                        ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Padding(
                    padding: EdgeInsets.only(bottom: isLast ? 0 : 16),
                    child: Text(
                      _statusLabel(step),
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight:
                            isCurrent ? FontWeight.w600 : FontWeight.w400,
                        color: isCurrent
                            ? AppTheme.text1(context)
                            : isCompleted
                                ? AppTheme.text2(context)
                                : AppTheme.textH(context),
                      ),
                    ),
                  ),
                ),
              ],
            );
          }),
        ],
      ),
    );
  }

  // ── Details card ──

  Widget _buildDetailsCard(BuildContext context, Map<String, dynamic> sub) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context), width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Submission Details',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w600,
              color: AppTheme.text1(context),
            ),
          ),
          const SizedBox(height: 16),
          _buildDetailRow(context, 'Insured Name', sub['insured_name'] ?? 'N/A'),
          _buildDetailRow(
              context, 'Risk Category', sub['risk_category'] ?? 'N/A'),
          _buildDetailRow(
              context, 'Sum Insured', _formatCurrency(sub['sum_insured'])),
          _buildDetailRow(context, 'Territory', sub['territory'] ?? 'N/A'),
          _buildDetailRow(
              context, 'Inception Date', sub['inception_date'] ?? 'N/A'),
          _buildDetailRow(
              context, 'Expiry Date', sub['expiry_date'] ?? 'N/A'),
          if (sub['description'] != null &&
              (sub['description'] as String).isNotEmpty) ...[
            const SizedBox(height: 12),
            Divider(color: AppTheme.borderOf(context), height: 1),
            const SizedBox(height: 12),
            Text(
              'Description',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppTheme.text2(context),
              ),
            ),
            const SizedBox(height: 6),
            Text(
              sub['description'],
              style: TextStyle(
                fontSize: 14,
                color: AppTheme.text1(context),
                height: 1.5,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildDetailRow(BuildContext context, String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 130,
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

  // ── Quote section ──

  Widget _buildQuoteSection(BuildContext context) {
    if (_quote != null) {
      return Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppTheme.surfaceOf(context),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.borderOf(context), width: 0.5),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.description_outlined,
                    size: 20, color: AppTheme.success),
                const SizedBox(width: 8),
                Text(
                  'Quote Available',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.text1(context),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              'A quote has been prepared for this submission.',
              style: TextStyle(
                fontSize: 14,
                color: AppTheme.text2(context),
              ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () {
                  final quoteId = _quote!['quote_id']?.toString() ?? '';
                  if (quoteId.isNotEmpty) {
                    context.go('/broker/quotes/$quoteId');
                  }
                },
                icon: const Icon(Icons.visibility),
                label: const Text('View Quote'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryDark,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
              ),
            ),
          ],
        ),
      );
    }

    // No quote yet
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context), width: 0.5),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: Colors.orange.withOpacity(0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.hourglass_empty,
                color: Colors.orange, size: 20),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Waiting for underwriter review',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.text1(context),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'A quote will appear here once an underwriter has reviewed your submission.',
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
    );
  }

  // ── Documents section ──

  Widget _buildDocumentsSection(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context), width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.attach_file, size: 20, color: AppTheme.text2(context)),
              const SizedBox(width: 8),
              Text(
                'Documents (${_documents.length})',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.text1(context),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ..._documents.map((doc) {
            final name = doc['name']?.toString() ?? 'Untitled';
            final type = doc['type']?.toString() ?? '';
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                decoration: BoxDecoration(
                  color: AppTheme.bg(context),
                  borderRadius: BorderRadius.circular(8),
                  border:
                      Border.all(color: AppTheme.borderOf(context), width: 0.5),
                ),
                child: Row(
                  children: [
                    Icon(
                      _documentIcon(type),
                      size: 20,
                      color: AppTheme.text2(context),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            name,
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w500,
                              color: AppTheme.text1(context),
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                          if (type.isNotEmpty)
                            Text(
                              type.toUpperCase(),
                              style: TextStyle(
                                fontSize: 11,
                                color: AppTheme.text2(context),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            );
          }),
        ],
      ),
    );
  }

  IconData _documentIcon(String type) {
    switch (type.toLowerCase()) {
      case 'pdf':
        return Icons.picture_as_pdf;
      case 'spreadsheet':
      case 'xlsx':
      case 'xls':
      case 'csv':
        return Icons.table_chart;
      case 'image':
      case 'png':
      case 'jpg':
      case 'jpeg':
        return Icons.image;
      default:
        return Icons.insert_drive_file;
    }
  }
}
