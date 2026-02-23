import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/services/auth_service.dart';
import '../../../core/theme/app_theme.dart';

/// Underwriter's view of a single broker submission.
/// Fetches data via /assessments/:id and provides actions like
/// Assign to Me, Push to Analysis, and Create Quote.
class BrokerSubmissionViewScreen extends StatefulWidget {
  final String submissionId;
  const BrokerSubmissionViewScreen({super.key, required this.submissionId});

  @override
  State<BrokerSubmissionViewScreen> createState() =>
      _BrokerSubmissionViewScreenState();
}

class _BrokerSubmissionViewScreenState
    extends State<BrokerSubmissionViewScreen> {
  Map<String, dynamic>? _submission;
  List<dynamic> _documents = [];
  bool _isLoading = true;
  bool _isAssigning = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchSubmission();
  }

  Future<void> _fetchSubmission() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final response =
          await authService.get('/assessments/${widget.submissionId}');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        setState(() {
          _submission = data;
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

  Future<void> _assignToMe() async {
    setState(() => _isAssigning = true);
    try {
      final response = await authService.post(
        '/broker-portal/submissions/${widget.submissionId}/assign',
      );
      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('Submission assigned to you.'),
            backgroundColor: AppTheme.success,
            behavior: SnackBarBehavior.floating,
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
        );
        await _fetchSubmission();
      } else {
        final body = jsonDecode(response.body);
        final detail = body['detail'] ?? 'Failed to assign.';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(detail.toString()),
            backgroundColor: AppTheme.danger,
            behavior: SnackBarBehavior.floating,
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
        );
      }
    } catch (e) {
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
      if (mounted) setState(() => _isAssigning = false);
    }
  }

  // ── Helpers ──

  Color _statusColor(String status) {
    switch (status) {
      case 'submitted':
        return Colors.orange;
      case 'under_review':
        return Colors.blue;
      case 'quote_pending':
        return const Color(0xFF7C3AED);
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

  String _formatCurrency(dynamic value) {
    if (value == null) return 'N/A';
    final num amount =
        value is num ? value : num.tryParse(value.toString()) ?? 0;
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

  Color _decisionColor(String? decision) {
    switch (decision?.toLowerCase()) {
      case 'go':
        return AppTheme.success;
      case 'no_go':
        return AppTheme.danger;
      case 'refer':
        return AppTheme.warning;
      default:
        return Colors.grey;
    }
  }

  String _decisionLabel(String? decision) {
    switch (decision?.toLowerCase()) {
      case 'go':
        return 'GO';
      case 'no_go':
        return 'NO GO';
      case 'refer':
        return 'REFER';
      default:
        return decision?.toUpperCase() ?? 'N/A';
    }
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

  // ── Build ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceOf(context),
        elevation: 0,
        title: Text(
          'Submission Review',
          style: TextStyle(
            color: AppTheme.text1(context),
            fontWeight: FontWeight.w600,
            fontSize: 17,
            letterSpacing: -0.2,
          ),
        ),
        iconTheme: IconThemeData(color: AppTheme.text1(context)),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchSubmission,
            tooltip: 'Refresh',
          ),
        ],
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
    final bool hasAnalysis = sub['has_analysis'] == true;
    final bool hasQuote = sub['has_quote'] == true;
    final dynamic riskScore = sub['risk_score'];
    final String? decision = sub['decision'] as String?;
    final String? assignedUnderwriter =
        (sub['assigned_underwriter'] ?? sub['assigned_to']) as String?;
    final String? uploadSessionToken =
        sub['upload_session_token'] as String?;
    final Map<String, dynamic> broker =
        sub['broker'] is Map<String, dynamic>
            ? sub['broker'] as Map<String, dynamic>
            : {};

    return RefreshIndicator(
      color: AppTheme.primaryDark,
      backgroundColor: AppTheme.surfaceOf(context),
      onRefresh: _fetchSubmission,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          // ── Header card ──
          _buildHeaderCard(context, sub, status, assignedUnderwriter),
          const SizedBox(height: 14),

          // ── Assign to Me ──
          if (assignedUnderwriter == null ||
              assignedUnderwriter.isEmpty) ...[
            _buildAssignButton(context),
            const SizedBox(height: 14),
          ],

          // ── Broker Info card ──
          if (broker.isNotEmpty) ...[
            _buildBrokerInfoCard(context, broker),
            const SizedBox(height: 14),
          ],

          // ── Risk Details card ──
          _buildRiskDetailsCard(context, sub),
          const SizedBox(height: 14),

          // ── AI Analysis section ──
          _buildAnalysisSection(
            context,
            hasAnalysis: hasAnalysis,
            riskScore: riskScore,
            decision: decision,
            uploadSessionToken: uploadSessionToken,
          ),
          const SizedBox(height: 14),

          // ── Quote section ──
          _buildQuoteSection(context,
              hasAnalysis: hasAnalysis, hasQuote: hasQuote),
          const SizedBox(height: 14),

          // ── Documents section ──
          if (_documents.isNotEmpty) _buildDocumentsSection(context),
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
              onPressed: _fetchSubmission,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  // ── Header card ──

  Widget _buildHeaderCard(BuildContext context, Map<String, dynamic> sub,
      String status, String? assignedUnderwriter) {
    final sColor = _statusColor(status);
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
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  sub['insured_name']?.toString() ?? 'Unknown Insured',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.text1(context),
                    letterSpacing: -0.3,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: sColor.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  _statusLabel(status),
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: sColor,
                  ),
                ),
              ),
            ],
          ),
          if (sub['reference'] != null) ...[
            const SizedBox(height: 8),
            Text(
              'Ref: ${sub['reference']}',
              style: TextStyle(
                fontSize: 13,
                color: AppTheme.text2(context),
              ),
            ),
          ],
          if (assignedUnderwriter != null &&
              assignedUnderwriter.isNotEmpty) ...[
            const SizedBox(height: 10),
            Row(
              children: [
                Icon(Icons.person_outline,
                    size: 15, color: AppTheme.text2(context)),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    'Assigned to: $assignedUnderwriter',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                      color: AppTheme.text2(context),
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  // ── Assign to Me button ──

  Widget _buildAssignButton(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: _isAssigning ? null : _assignToMe,
        icon: _isAssigning
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
            : const Icon(Icons.assignment_ind, size: 18),
        label: Text(_isAssigning ? 'Assigning...' : 'Assign to Me'),
        style: ElevatedButton.styleFrom(
          backgroundColor: AppTheme.primaryDark,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          textStyle: const TextStyle(
            fontFamily: 'Inter',
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }

  // ── Broker Info card ──

  Widget _buildBrokerInfoCard(
      BuildContext context, Map<String, dynamic> broker) {
    final name = (broker['name'] ?? broker['full_name'] ?? 'Unknown Broker')
        .toString();
    final email = (broker['email'] ?? '').toString();

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
              Icon(Icons.business_center_outlined,
                  size: 18, color: AppTheme.text2(context)),
              const SizedBox(width: 8),
              Text(
                'Broker Information',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.text1(context),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _buildDetailRow(context, 'Broker Name', name),
          if (email.isNotEmpty) _buildDetailRow(context, 'Email', email),
        ],
      ),
    );
  }

  // ── Risk Details card ──

  Widget _buildRiskDetailsCard(
      BuildContext context, Map<String, dynamic> sub) {
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
              Icon(Icons.shield_outlined,
                  size: 18, color: AppTheme.text2(context)),
              const SizedBox(width: 8),
              Text(
                'Risk Details',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.text1(context),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _buildDetailRow(
              context, 'Risk Category', sub['risk_category']?.toString() ?? 'N/A'),
          _buildDetailRow(
              context, 'Sum Insured', _formatCurrency(sub['sum_insured'])),
          _buildDetailRow(
              context, 'Territory', sub['territory']?.toString() ?? 'N/A'),
          _buildDetailRow(
              context, 'Inception Date', _formatDate(sub['inception_date']?.toString())),
          _buildDetailRow(
              context, 'Expiry Date', _formatDate(sub['expiry_date']?.toString())),
          if (sub['description'] != null &&
              (sub['description'] as String).isNotEmpty) ...[
            const SizedBox(height: 4),
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
              sub['description'].toString(),
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

  // ── AI Analysis section ──

  Widget _buildAnalysisSection(
    BuildContext context, {
    required bool hasAnalysis,
    required dynamic riskScore,
    required String? decision,
    required String? uploadSessionToken,
  }) {
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
              Icon(Icons.auto_awesome,
                  size: 18, color: AppTheme.primaryDark),
              const SizedBox(width: 8),
              Text(
                'AI Analysis',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.text1(context),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (hasAnalysis && riskScore != null)
            _buildAnalysisResults(context, riskScore, decision)
          else
            _buildPushToAnalysis(context, uploadSessionToken),
        ],
      ),
    );
  }

  Widget _buildAnalysisResults(
      BuildContext context, dynamic riskScore, String? decision) {
    final num numScore =
        riskScore is num ? riskScore : (num.tryParse(riskScore.toString()) ?? 0);

    // Risk score colour
    Color scoreColor;
    if (numScore >= 75) {
      scoreColor = AppTheme.danger;
    } else if (numScore >= 50) {
      scoreColor = AppTheme.warning;
    } else {
      scoreColor = AppTheme.success;
    }

    final dColor = _decisionColor(decision);
    final dLabel = _decisionLabel(decision);

    return Column(
      children: [
        // Risk score gauge
        Row(
          children: [
            // Circular gauge
            SizedBox(
              width: 72,
              height: 72,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  SizedBox(
                    width: 72,
                    height: 72,
                    child: CircularProgressIndicator(
                      value: numScore / 100,
                      strokeWidth: 6,
                      backgroundColor: AppTheme.isDark(context)
                          ? AppTheme.darkCard
                          : AppTheme.surfaceVariant,
                      valueColor:
                          AlwaysStoppedAnimation<Color>(scoreColor),
                    ),
                  ),
                  Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        numScore.toStringAsFixed(0),
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                          color: scoreColor,
                        ),
                      ),
                      Text(
                        'Risk',
                        style: TextStyle(
                          fontSize: 10,
                          color: AppTheme.text2(context),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 20),
            // Decision badge
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Decision',
                    style: TextStyle(
                      fontSize: 12,
                      color: AppTheme.text2(context),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 14, vertical: 8),
                    decoration: BoxDecoration(
                      color: dColor.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      dLabel,
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: dColor,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 14),
        // View full results link
        SizedBox(
          width: double.infinity,
          child: OutlinedButton.icon(
            onPressed: () {
              context.go(
                '/assessments/${widget.submissionId}/results',
                extra: {'isProcessing': false},
              );
            },
            icon: const Icon(Icons.analytics_outlined, size: 18),
            label: const Text('View Full Analysis'),
            style: OutlinedButton.styleFrom(
              foregroundColor: AppTheme.text1(context),
              side: BorderSide(color: AppTheme.borderOf(context)),
              padding: const EdgeInsets.symmetric(vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildPushToAnalysis(
      BuildContext context, String? uploadSessionToken) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: AppTheme.isDark(context)
                    ? AppTheme.darkCard
                    : AppTheme.surfaceVariant,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                Icons.hourglass_empty,
                size: 20,
                color: AppTheme.text2(context),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Text(
                'No AI analysis has been run yet.',
                style: TextStyle(
                  fontSize: 14,
                  color: AppTheme.text2(context),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: () {
              if (uploadSessionToken != null &&
                  uploadSessionToken.isNotEmpty) {
                context.go(
                  '/analysis/progress/${widget.submissionId}',
                  extra: {
                    'isProcessing': true,
                    'sessionToken': uploadSessionToken,
                  },
                );
              } else {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content:
                        const Text('No documents uploaded for analysis.'),
                    backgroundColor: AppTheme.warning,
                    behavior: SnackBarBehavior.floating,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10)),
                  ),
                );
              }
            },
            icon: const Icon(Icons.play_arrow, size: 18),
            label: const Text('Push to Analysis'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryDark,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
              textStyle: const TextStyle(
                fontFamily: 'Inter',
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
      ],
    );
  }

  // ── Quote section ──

  Widget _buildQuoteSection(BuildContext context,
      {required bool hasAnalysis, required bool hasQuote}) {
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
              Icon(Icons.description_outlined,
                  size: 18, color: AppTheme.text2(context)),
              const SizedBox(width: 8),
              Text(
                'Quote',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.text1(context),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          if (hasQuote)
            _buildQuoteIssued(context)
          else if (hasAnalysis)
            _buildCreateQuoteButton(context)
          else
            _buildQuoteWaiting(context),
        ],
      ),
    );
  }

  Widget _buildQuoteIssued(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: AppTheme.success.withOpacity(0.15),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(Icons.check_circle, color: AppTheme.success, size: 20),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Quote Issued',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.success,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                'A quote has been created for this submission.',
                style: TextStyle(
                  fontSize: 13,
                  color: AppTheme.text2(context),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildCreateQuoteButton(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: () {
          context.go(
              '/home/broker-submissions/${widget.submissionId}/quote');
        },
        icon: const Icon(Icons.add_circle_outline, size: 18),
        label: const Text('Create Quote'),
        style: ElevatedButton.styleFrom(
          backgroundColor: AppTheme.primaryDark,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          textStyle: const TextStyle(
            fontFamily: 'Inter',
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }

  Widget _buildQuoteWaiting(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: AppTheme.isDark(context)
                ? AppTheme.darkCard
                : AppTheme.surfaceVariant,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(
            Icons.info_outline,
            size: 20,
            color: AppTheme.text2(context),
          ),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Text(
            'Run analysis first before creating a quote.',
            style: TextStyle(
              fontSize: 14,
              color: AppTheme.text2(context),
            ),
          ),
        ),
      ],
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
        boxShadow: AppTheme.isDark(context) ? null : AppTheme.subtleShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.attach_file,
                  size: 18, color: AppTheme.text2(context)),
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
            final name = doc['name']?.toString() ??
                doc['filename']?.toString() ??
                'Untitled';
            final type = doc['type']?.toString() ??
                doc['file_type']?.toString() ??
                '';
            final size = doc['size'] ?? doc['file_size'];
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                decoration: BoxDecoration(
                  color: AppTheme.bg(context),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                      color: AppTheme.borderOf(context), width: 0.5),
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
                          if (type.isNotEmpty || size != null)
                            Row(
                              children: [
                                if (type.isNotEmpty)
                                  Text(
                                    type.toUpperCase(),
                                    style: TextStyle(
                                      fontSize: 11,
                                      color: AppTheme.text2(context),
                                    ),
                                  ),
                                if (type.isNotEmpty && size != null)
                                  Text(
                                    '  \u00B7  ',
                                    style: TextStyle(
                                      fontSize: 11,
                                      color: AppTheme.textH(context),
                                    ),
                                  ),
                                if (size != null)
                                  Text(
                                    _formatFileSize(size),
                                    style: TextStyle(
                                      fontSize: 11,
                                      color: AppTheme.text2(context),
                                    ),
                                  ),
                              ],
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

  String _formatFileSize(dynamic size) {
    if (size == null) return '';
    final num bytes = size is num ? size : (num.tryParse(size.toString()) ?? 0);
    if (bytes >= 1048576) {
      return '${(bytes / 1048576).toStringAsFixed(1)} MB';
    } else if (bytes >= 1024) {
      return '${(bytes / 1024).toStringAsFixed(0)} KB';
    }
    return '${bytes.toStringAsFixed(0)} B';
  }
}
