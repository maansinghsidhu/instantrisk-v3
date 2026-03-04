import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:async';
import 'dart:convert';
import 'package:url_launcher/url_launcher.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Assessment Documents Screen - Shows all documents for an assessment
/// Includes both original uploaded files and AI-generated documents
class AssessmentDocumentsScreen extends StatefulWidget {
  final String assessmentId;

  const AssessmentDocumentsScreen({
    super.key,
    required this.assessmentId,
  });

  @override
  State<AssessmentDocumentsScreen> createState() =>
      _AssessmentDocumentsScreenState();
}

class _AssessmentDocumentsScreenState extends State<AssessmentDocumentsScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  Map<String, dynamic>? _assessment;
  List<Map<String, dynamic>> _uploadedDocs = [];
  List<Map<String, dynamic>> _generatedDocs = [];
  List<Map<String, dynamic>> _pendingJobs = [];
  bool _isLoading = true;
  Timer? _refreshTimer;
  int _previousUploadedCount = 0;
  int _previousGeneratedCount = 0;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadDocuments();
    // Start auto-refresh timer - checks every 5 seconds for new documents
    _startAutoRefresh();
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _tabController.dispose();
    super.dispose();
  }

  void _startAutoRefresh() {
    _refreshTimer = Timer.periodic(const Duration(seconds: 5), (timer) {
      _refreshDocumentsSilently();
    });
  }

  /// Silently refresh documents without showing loading indicator
  Future<void> _refreshDocumentsSilently() async {
    if (!mounted) return;

    try {
      // Load uploaded documents count
      List<Map<String, dynamic>> newUploadedDocs = [];

      // Get documents from assessment's AI analysis
      if (_assessment != null && _assessment!['ai_analysis'] != null) {
        final aiAnalysis = _assessment!['ai_analysis'] as Map<String, dynamic>;
        if (aiAnalysis['ocr_extracted_text'] != null) {
          newUploadedDocs.add({
            'name': _assessment!['title'] ?? 'Source Document',
            'type': aiAnalysis['document_type'] ?? 'Document',
            'reference': _assessment!['reference_number'],
            'ocr_preview': (aiAnalysis['ocr_extracted_text'] as String?)
                    ?.substring(0, 500) ??
                '',
            'status': 'processed',
          });
        }
      }

      // Also get from documents endpoint
      final docsRes =
          await authService.get('/assessments/${widget.assessmentId}/documents');
      if (docsRes.statusCode == 200) {
        final data = jsonDecode(docsRes.body);
        final docs = data['items'] ?? data['documents'] ?? [];
        for (final doc in docs) {
          newUploadedDocs.add(Map<String, dynamic>.from(doc));
        }
      }

      // Load generated documents
      List<Map<String, dynamic>> newGeneratedDocs = [];
      final genRes =
          await authService.get('/assessments/${widget.assessmentId}/generated');
      if (genRes.statusCode == 200) {
        final data = jsonDecode(genRes.body);
        newGeneratedDocs = List<Map<String, dynamic>>.from(data['items'] ?? []);
      }

      // Only update UI if counts changed (new documents added)
      if (mounted &&
          (newUploadedDocs.length != _previousUploadedCount ||
           newGeneratedDocs.length != _previousGeneratedCount)) {
        setState(() {
          _uploadedDocs = newUploadedDocs;
          _generatedDocs = newGeneratedDocs;
          _previousUploadedCount = newUploadedDocs.length;
          _previousGeneratedCount = newGeneratedDocs.length;
        });
      }
    } catch (e) {
      // Silently fail - don't show error for background refresh
    }
  }

  Future<void> _deleteUploadedDocument(String docId) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Document'),
        content: const Text('Are you sure you want to delete this uploaded document?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirm != true) return;

    try {
      final response = await authService.delete('/documents/$docId');
      if (response.statusCode == 200 || response.statusCode == 204) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Document deleted')),
          );
          _loadDocuments();
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

  Future<void> _deleteGeneratedDocument(String docId) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Document'),
        content: const Text('Are you sure you want to delete this generated document?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirm != true) return;

    try {
      final response = await authService.delete('/generated-documents/$docId');
      if (response.statusCode == 200 || response.statusCode == 204) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Document deleted')),
          );
          _loadDocuments();
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

  Future<void> _loadDocuments() async {
    try {
      setState(() => _isLoading = true);

      // Load assessment details
      final assessmentRes =
          await authService.get('/assessments/${widget.assessmentId}');
      if (assessmentRes.statusCode == 200) {
        _assessment = jsonDecode(assessmentRes.body);
      }

      // Load uploaded documents (from upload session or assessment)
      await _loadUploadedDocuments();

      // Load generated documents
      final genRes =
          await authService.get('/assessments/${widget.assessmentId}/generated');
      if (genRes.statusCode == 200) {
        final data = jsonDecode(genRes.body);
        _generatedDocs = List<Map<String, dynamic>>.from(data['items'] ?? []);
      }

      // Load pending generation jobs
      await _loadPendingJobs();

      // Track counts for auto-refresh comparison
      _previousUploadedCount = _uploadedDocs.length;
      _previousGeneratedCount = _generatedDocs.length;

      setState(() => _isLoading = false);
    } catch (e) {
      setState(() => _isLoading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load documents: $e')),
        );
      }
    }
  }

  Future<void> _loadUploadedDocuments() async {
    try {
      // Get documents from assessment's AI analysis
      if (_assessment != null && _assessment!['ai_analysis'] != null) {
        final aiAnalysis = _assessment!['ai_analysis'] as Map<String, dynamic>;

        // Check for OCR text (indicates uploaded document)
        if (aiAnalysis['ocr_extracted_text'] != null) {
          _uploadedDocs.add({
            'name': _assessment!['title'] ?? 'Source Document',
            'type': aiAnalysis['document_type'] ?? 'Document',
            'reference': _assessment!['reference_number'],
            'ocr_preview': (aiAnalysis['ocr_extracted_text'] as String?)
                    ?.substring(0, 500) ??
                '',
            'status': 'processed',
          });
        }
      }

      // Also try to get from documents endpoint if available
      final docsRes =
          await authService.get('/assessments/${widget.assessmentId}/documents');
      if (docsRes.statusCode == 200) {
        final data = jsonDecode(docsRes.body);
        final docs = data['items'] ?? data['documents'] ?? [];
        for (final doc in docs) {
          _uploadedDocs.add(Map<String, dynamic>.from(doc));
        }
      }
    } catch (e) {
      // Continue even if this fails
    }
  }

  Future<void> _loadPendingJobs() async {
    try {
      // Get all generation jobs for this assessment
      final jobsRes = await authService.get('/generation-jobs/');
      if (jobsRes.statusCode == 200) {
        final data = jsonDecode(jobsRes.body);
        final jobs = List<Map<String, dynamic>>.from(data['items'] ?? []);
        // Filter for pending/processing jobs for this assessment
        _pendingJobs = jobs.where((job) {
          final status = job['status'] as String?;
          final assessmentId = job['assessment_id']?.toString();
          return (status == 'pending' || status == 'processing') &&
              assessmentId == widget.assessmentId;
        }).toList();
      }
    } catch (e) {
      // Continue even if this fails
      _pendingJobs = [];
    }
  }

  Future<void> _downloadDocument(Map<String, dynamic> doc) async {
    try {
      final docId = doc['id'];
      final docName = doc['title'] ?? doc['document_type'] ?? 'document';

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Preparing download...')),
        );
      }

      // First finalize if not already
      if (doc['status'] != 'finalized') {
        final finalizeRes = await authService.post(
          '/generated-documents/$docId/finalize',
          body: {},
        );
        if (finalizeRes.statusCode != 200) {
          throw Exception('Failed to finalize document');
        }
      }

      // Get download URL and trigger download
      final downloadUrl = '${authService.baseUrl}/generated-documents/$docId/download';
      final token = await authService.getToken();

      // Use url_launcher to open in browser with auth (downloads the file)
      // For web: use JS interop to download with headers
      // For mobile: use http to download and save
      await authService.downloadFile(downloadUrl, '${docName}_$docId.pdf');

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Downloaded: $docName'),
            backgroundColor: AppTheme.success,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Download failed: $e'),
            backgroundColor: AppTheme.error,
          ),
        );
      }
    }
  }

  Future<void> _downloadUploadedDocument(Map<String, dynamic> doc) async {
    try {
      final docId = doc['id'];
      if (docId == null) {
        throw Exception('No document ID available');
      }

      // Download with auth headers
      final response = await authService.get('/documents/$docId/download');

      if (response.statusCode == 200) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Document downloaded successfully')),
          );
        }
      } else {
        throw Exception('Download failed: ${response.statusCode}');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Download failed: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceOf(context),
        elevation: 0,
        leading: IconButton(
          onPressed: () => context.pop(),
          icon: Icon(Icons.arrow_back),
          color: AppTheme.text1(context),
        ),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Text(
              'Assessment Documents',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: AppTheme.text1(context),
                fontFamily: 'Inter',
              ),
            ),
            if (_assessment != null)
              Text(
                _assessment!['reference_number'] ?? '',
                style: TextStyle(
                  fontSize: 12,
                  color: AppTheme.text2(context),
                ),
              ),
          ],
        ),
        centerTitle: true,
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppTheme.primaryDark,
          unselectedLabelColor: AppTheme.text2(context),
          indicatorColor: AppTheme.primaryDark,
          tabs: [
            Tab(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.upload_file, size: 18),
                  const SizedBox(width: 8),
                  Text('Uploaded (${_uploadedDocs.length})'),
                ],
              ),
            ),
            Tab(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.auto_awesome, size: 18),
                  const SizedBox(width: 8),
                  Text('Generated (${_generatedDocs.length})'),
                ],
              ),
            ),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildUploadedDocsList(),
                _buildGeneratedDocsList(),
              ],
            ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          context.push('/reports/generate/${widget.assessmentId}');
        },
        backgroundColor: AppTheme.primaryDark,
        icon: const Icon(Icons.add, color: Colors.white),
        label: const Text(
          'Generate More',
          style: TextStyle(color: Colors.white),
        ),
      ),
    );
  }

  Widget _buildUploadedDocsList() {
    if (_uploadedDocs.isEmpty) {
      return RefreshIndicator(
        onRefresh: _loadDocuments,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          child: SizedBox(
            height: MediaQuery.of(context).size.height * 0.6,
            child: _buildEmptyState(
              icon: Icons.upload_file_outlined,
              title: 'No Source Documents',
              subtitle: 'Original uploaded documents will appear here\nPull to refresh',
            ),
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadDocuments,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _uploadedDocs.length,
        itemBuilder: (context, index) => _buildUploadedDocCard(_uploadedDocs[index]),
      ),
    );
  }

  Widget _buildGeneratedDocsList() {
    final allItems = [
      ..._pendingJobs.map((j) => {'...data': j, '_type': 'pending'}),
      ..._generatedDocs.map((d) => {'...data': d, '_type': 'generated'}),
    ];

    if (allItems.isEmpty) {
      return RefreshIndicator(
        onRefresh: _loadDocuments,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          child: SizedBox(
            height: MediaQuery.of(context).size.height * 0.6,
            child: _buildEmptyState(
              icon: Icons.description_outlined,
              title: 'No Generated Documents',
              subtitle: 'Generated documents will appear here\nPull to refresh',
              actionLabel: 'Generate Documents',
              onAction: () {
                context.push('/reports/generate/${widget.assessmentId}');
              },
            ),
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadDocuments,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Pending generation jobs
          if (_pendingJobs.isNotEmpty) ...[
            Padding(
              padding: EdgeInsets.only(bottom: 8),
              child: Text(
                'GENERATING',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textH(context),
                  letterSpacing: 1,
                ),
              ),
            ),
            ..._pendingJobs.map((job) => _buildPendingJobCard(job)),
            const SizedBox(height: 16),
          ],

          // Generated documents
          if (_generatedDocs.isNotEmpty) ...[
            Padding(
              padding: EdgeInsets.only(bottom: 8),
              child: Text(
                'GENERATED DOCUMENTS',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textH(context),
                  letterSpacing: 1,
                ),
              ),
            ),
            ..._generatedDocs.map((doc) => _buildGeneratedDocCard(doc)),
            const SizedBox(height: 16),
          ],

        ],
      ),
    );
  }

  Widget _buildPendingJobCard(Map<String, dynamic> job) {
    final progress = job['progress_percentage'] ?? 0;
    final currentAgent = job['current_agent'] ?? 'Initializing';
    final description = job['current_agent_description'] ?? 'Starting...';
    final docsCount = job['total_documents'] ?? 0;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.primaryDark.withOpacity(0.3)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryDark.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Generating $docsCount Document${docsCount > 1 ? 's' : ''}',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text1(context),
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        currentAgent,
                        style: TextStyle(
                          fontSize: 12,
                          color: AppTheme.primaryDark,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
                Text(
                  '$progress%',
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.primaryDark,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            // Progress bar
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: progress / 100,
                backgroundColor: AppTheme.borderOf(context),
                valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primaryDark),
                minHeight: 6,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              description,
              style: TextStyle(
                fontSize: 12,
                color: AppTheme.text2(context),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState({
    required IconData icon,
    required String title,
    required String subtitle,
    String? actionLabel,
    VoidCallback? onAction,
  }) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: AppTheme.primaryLight.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, size: 48, color: AppTheme.primaryDark),
            ),
            const SizedBox(height: 24),
            Text(
              title,
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: AppTheme.text1(context),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              subtitle,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                color: AppTheme.text2(context),
              ),
            ),
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: onAction,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryDark,
                  padding:
                      const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
                child: Text(
                  actionLabel,
                  style: const TextStyle(color: Colors.white),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildUploadedDocCard(Map<String, dynamic> doc) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppTheme.infoLight.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.insert_drive_file,
                    color: AppTheme.info,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        doc['name'] ?? 'Document',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text1(context),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: AppTheme.successLight.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              doc['type'] ?? 'Source',
                              style: const TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w500,
                                color: AppTheme.success,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            doc['status'] ?? 'processed',
                            style: TextStyle(
                              fontSize: 12,
                              color: AppTheme.text2(context),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                if (doc['id'] != null)
                  IconButton(
                    onPressed: () => _downloadUploadedDocument(doc),
                    icon: const Icon(Icons.download, color: AppTheme.primaryDark),
                    tooltip: 'Download',
                  ),
                if (doc['id'] != null)
                  IconButton(
                    onPressed: () => _deleteUploadedDocument(doc['id'].toString()),
                    icon: Icon(Icons.delete_outline, color: AppTheme.textH(context)),
                    tooltip: 'Delete',
                  ),
              ],
            ),
            if (doc['ocr_preview'] != null) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.bg(context),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '${doc['ocr_preview']}...',
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 12,
                    color: AppTheme.text2(context),
                    height: 1.4,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildGeneratedDocCard(Map<String, dynamic> doc) {
    final docType = doc['document_type'] ?? '';
    final title = doc['title'] ?? _formatDocType(docType);
    final status = doc['status'] ?? 'draft';
    final confidence = (doc['ai_confidence'] ?? 0.0) * 100;
    final placeholders = doc['placeholders_remaining'] ?? 0;
    final compliance = doc['compliance_report'] as Map<String, dynamic>? ?? {};
    final complianceScore = compliance['compliance_score'] ?? 0;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: _getDocTypeColor(docType).withOpacity(0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(
                    _getDocTypeIcon(docType),
                    color: _getDocTypeColor(docType),
                    size: 24,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text1(context),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          _buildStatusBadge(status),
                          const SizedBox(width: 8),
                          Text(
                            '${confidence.toStringAsFixed(0)}% confidence',
                            style: TextStyle(
                              fontSize: 12,
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

          // Stats Row
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: AppTheme.bg(context),
              border: Border(
                top: BorderSide(color: AppTheme.borderOf(context)),
              ),
            ),
            child: Row(
              children: [
                _buildStatItem(
                  icon: Icons.check_circle_outline,
                  label: 'Compliance',
                  value: '$complianceScore%',
                  color: complianceScore >= 70
                      ? AppTheme.success
                      : complianceScore >= 40
                          ? AppTheme.warning
                          : AppTheme.error,
                ),
                const SizedBox(width: 24),
                _buildStatItem(
                  icon: Icons.edit_note,
                  label: 'Placeholders',
                  value: placeholders.toString(),
                  color: placeholders == 0
                      ? AppTheme.success
                      : AppTheme.warning,
                ),
                const Spacer(),
                // Action buttons
                Row(
                  children: [
                    TextButton.icon(
                      onPressed: () {
                        // View/Edit document
                        _showDocumentPreview(doc);
                      },
                      icon: const Icon(Icons.visibility, size: 18),
                      label: const Text('View'),
                      style: TextButton.styleFrom(
                        foregroundColor: AppTheme.primaryDark,
                      ),
                    ),
                    const SizedBox(width: 8),
                    ElevatedButton.icon(
                      onPressed: () => _downloadDocument(doc),
                      icon: const Icon(Icons.download, size: 18),
                      label: const Text('Download'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primaryDark,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 8,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton(
                      onPressed: () {
                        final docId = doc['id']?.toString();
                        if (docId != null) _deleteGeneratedDocument(docId);
                      },
                      icon: Icon(Icons.delete_outline, color: AppTheme.textH(context), size: 20),
                      tooltip: 'Delete',
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusBadge(String status) {
    Color bgColor;
    Color textColor;
    String label;

    switch (status.toLowerCase()) {
      case 'draft':
        bgColor = AppTheme.infoLight.withOpacity(0.2);
        textColor = AppTheme.info;
        label = 'Draft';
        break;
      case 'review_required':
        bgColor = AppTheme.warningLight.withOpacity(0.2);
        textColor = AppTheme.warning;
        label = 'Review Required';
        break;
      case 'approved':
      case 'finalized':
        bgColor = AppTheme.successLight.withOpacity(0.2);
        textColor = AppTheme.success;
        label = 'Ready';
        break;
      case 'failed':
        bgColor = AppTheme.errorLight.withOpacity(0.2);
        textColor = AppTheme.error;
        label = 'Failed';
        break;
      default:
        bgColor = AppTheme.borderOf(context);
        textColor = AppTheme.text2(context);
        label = status;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w500,
          color: textColor,
        ),
      ),
    );
  }

  Widget _buildStatItem({
    required IconData icon,
    required String label,
    required String value,
    required Color color,
  }) {
    return Row(
      children: [
        Icon(icon, size: 16, color: color),
        SizedBox(width: 4),
        Text(
          '$label: ',
          style: TextStyle(
            fontSize: 12,
            color: AppTheme.text2(context),
          ),
        ),
        Text(
          value,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: color,
          ),
        ),
      ],
    );
  }

  Color _getDocTypeColor(String docType) {
    if (docType.contains('slip')) return AppTheme.primary;
    if (docType.contains('policy')) return AppTheme.info;
    if (docType.contains('cover_note')) return AppTheme.success;
    if (docType.contains('quote')) return AppTheme.warning;
    if (docType.contains('certificate')) return AppTheme.secondary;
    return AppTheme.text2(context);
  }

  IconData _getDocTypeIcon(String docType) {
    if (docType.contains('slip')) return Icons.description;
    if (docType.contains('policy')) return Icons.policy;
    if (docType.contains('cover_note')) return Icons.note;
    if (docType.contains('quote')) return Icons.request_quote;
    if (docType.contains('certificate')) return Icons.verified;
    return Icons.article;
  }

  String _formatDocType(String docType) {
    return docType
        .replaceAll('_', ' ')
        .split(' ')
        .map((word) => word.isNotEmpty
            ? '${word[0].toUpperCase()}${word.substring(1)}'
            : '')
        .join(' ');
  }

  void _showDocumentPreview(Map<String, dynamic> doc) {
    final draftContent = doc['draft_content'] as Map<String, dynamic>? ?? {};
    final sections = draftContent['sections'] as List<dynamic>? ?? [];

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.9,
        minChildSize: 0.5,
        maxChildSize: 0.95,
        builder: (context, scrollController) => Container(
          decoration: BoxDecoration(
            color: AppTheme.surfaceOf(context),
            borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
          ),
          child: Column(
            children: [
              // Handle
              Container(
                margin: const EdgeInsets.only(top: 12),
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AppTheme.borderOf(context),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              // Header
              Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        doc['title'] ?? 'Document Preview',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.text1(context),
                        ),
                      ),
                    ),
                    IconButton(
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1),
              // Content
              Expanded(
                child: sections.isEmpty
                    ? const Center(
                        child: Text('No content available'),
                      )
                    : ListView.builder(
                        controller: scrollController,
                        padding: const EdgeInsets.all(16),
                        itemCount: sections.length,
                        itemBuilder: (context, index) {
                          final section =
                              sections[index] as Map<String, dynamic>;
                          return _buildSectionCard(section);
                        },
                      ),
              ),
              // Actions
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.surfaceOf(context),
                  border: Border(top: BorderSide(color: AppTheme.borderOf(context))),
                ),
                child: SafeArea(
                  child: Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () {
                            Navigator.pop(context);
                            context.push('/documents/edit/${doc['id']}', extra: {
                              'assessmentId': widget.assessmentId,
                            });
                          },
                          icon: const Icon(Icons.edit),
                          label: const Text('Edit'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: () {
                            Navigator.pop(context);
                            _downloadDocument(doc);
                          },
                          icon: const Icon(Icons.download),
                          label: const Text('Download'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppTheme.primaryDark,
                            foregroundColor: Colors.white,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSectionCard(Map<String, dynamic> section) {
    final title = section['section_title'] ?? section['section_name'] ?? '';
    final content = section['content'] ?? '';
    final isComplete = section['is_complete'] ?? false;
    final placeholders =
        (section['placeholders'] as List<dynamic>?)?.cast<String>() ?? [];

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: AppTheme.bg(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isComplete ? AppTheme.borderOf(context) : AppTheme.warning.withOpacity(0.5),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: isComplete
                  ? AppTheme.successLight.withOpacity(0.1)
                  : AppTheme.warningLight.withOpacity(0.1),
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(11)),
            ),
            child: Row(
              children: [
                Icon(
                  isComplete ? Icons.check_circle : Icons.pending,
                  size: 18,
                  color: isComplete ? AppTheme.success : AppTheme.warning,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    title,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.text1(context),
                    ),
                  ),
                ),
                if (placeholders.isNotEmpty)
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppTheme.warning.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      '${placeholders.length} placeholder${placeholders.length > 1 ? 's' : ''}',
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppTheme.warning,
                      ),
                    ),
                  ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              content,
              style: TextStyle(
                fontSize: 13,
                height: 1.6,
                color: AppTheme.text1(context),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
