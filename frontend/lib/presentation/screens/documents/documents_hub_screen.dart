import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:async';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/documents_prefetch_service.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../widgets/common/screen_header.dart';

/// Documents Hub Screen - V3 Document Center
/// Entry point for all document operations - viewing, creating, and managing documents
class DocumentsHubScreen extends StatefulWidget {
  const DocumentsHubScreen({super.key});

  @override
  State<DocumentsHubScreen> createState() => _DocumentsHubScreenState();
}

class _DocumentsHubScreenState extends State<DocumentsHubScreen> {
  List<Map<String, dynamic>> _recentDocuments = [];
  List<Map<String, dynamic>> _assessments = [];
  bool _isLoading = true;
  Timer? _refreshTimer;
  String _searchQuery = '';
  String _activeFilter = 'all'; // all, generated, assessments
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();

    // Use prefetched data if available for instant loading
    if (documentsPrefetchService.hasCachedData) {
      _recentDocuments = documentsPrefetchService.recentDocuments;
      _assessments = documentsPrefetchService.assessments;
      _isLoading = false;

      // Refresh in background if cache is stale
      if (!documentsPrefetchService.isCacheValid) {
        _loadData(silent: true);
      }
    } else {
      _loadData();
    }

    // Auto-refresh every 30 seconds
    _refreshTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      _loadData(silent: true);
    });
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadData({bool silent = false}) async {
    try {
      if (!silent) setState(() => _isLoading = true);

      // Use prefetch service to load and cache data
      await documentsPrefetchService.prefetch();

      // Update local state from cache
      _recentDocuments = documentsPrefetchService.recentDocuments;
      _assessments = documentsPrefetchService.assessments;

      if (mounted) {
        setState(() => _isLoading = false);
      }
    } catch (e) {
      if (mounted && !silent) setState(() => _isLoading = false);
    }
  }

  Future<void> _deleteGeneratedDocument(String docId) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Document'),
        content: const Text('Are you sure you want to delete this generated document? This cannot be undone.'),
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
      final response = await authService.delete('/generated-documents/$docId');
      if (response.statusCode == 204 || response.statusCode == 200) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Document deleted')),
          );
          _loadData();
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

  Future<void> _deleteAssessment(String assessmentId) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Assessment'),
        content: const Text('Are you sure you want to delete this assessment and all its generated documents? This cannot be undone.'),
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
      final response = await authService.delete('/assessments/$assessmentId');
      if (response.statusCode == 200 || response.statusCode == 204) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Assessment deleted')),
          );
          _loadData();
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

  /// Filter documents by search query
  List<Map<String, dynamic>> get _filteredDocuments {
    if (_searchQuery.isEmpty) return _recentDocuments;
    final q = _searchQuery.toLowerCase();
    return _recentDocuments.where((doc) {
      final title = (doc['title'] as String? ?? '').toLowerCase();
      final status = (doc['status'] as String? ?? '').toLowerCase();
      final docType = (doc['document_type'] as String? ?? '').toLowerCase();
      return title.contains(q) || status.contains(q) || docType.contains(q);
    }).toList();
  }

  /// Filter assessments by search query
  List<Map<String, dynamic>> get _filteredAssessments {
    if (_searchQuery.isEmpty) return _assessments;
    final q = _searchQuery.toLowerCase();
    return _assessments.where((a) {
      final title = (a['title'] as String? ?? '').toLowerCase();
      final ref = (a['reference_number'] as String? ?? '').toLowerCase();
      final decision = (a['decision'] as String? ?? '').toLowerCase();
      return title.contains(q) || ref.contains(q) || decision.contains(q);
    }).toList();
  }

  bool get _showGenerated =>
      _activeFilter == 'all' || _activeFilter == 'generated';
  bool get _showAssessments =>
      _activeFilter == 'all' || _activeFilter == 'assessments';

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      body: CustomScrollView(
        slivers: [
          // Header
          SliverToBoxAdapter(
            child: ScreenHeader(
              title: l10n.documentCenter,
              subtitle: 'Manage and generate documents',
              actions: [
                IconButton(
                  icon: Icon(Icons.refresh, color: AppTheme.text2(context), size: 20),
                  onPressed: _loadData,
                ),
              ],
            ),
          ),

          // Search bar + filters
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: Column(
                children: [
                  // Inline search bar
                  TextField(
                    controller: _searchController,
                    onChanged: (v) => setState(() => _searchQuery = v),
                    style: TextStyle(
                      fontSize: 14,
                      color: AppTheme.text1(context),
                    ),
                    decoration: InputDecoration(
                      hintText: 'Search documents...',
                      hintStyle: TextStyle(
                        fontSize: 14,
                        color: AppTheme.textH(context),
                      ),
                      prefixIcon: Icon(Icons.search, size: 20, color: AppTheme.textH(context)),
                      suffixIcon: _searchQuery.isNotEmpty
                          ? IconButton(
                              icon: Icon(Icons.clear, size: 18, color: AppTheme.textH(context)),
                              onPressed: () {
                                _searchController.clear();
                                setState(() => _searchQuery = '');
                              },
                            )
                          : null,
                      filled: true,
                      fillColor: AppTheme.cardOf(context),
                      contentPadding: const EdgeInsets.symmetric(vertical: 10),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide(color: AppTheme.borderOf(context)),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide(color: AppTheme.borderOf(context)),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide(color: AppTheme.primaryDark, width: 1.5),
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),
                  // Filter chips
                  Row(
                    children: [
                      _buildFilterChip('All', 'all'),
                      const SizedBox(width: 8),
                      _buildFilterChip('Generated', 'generated'),
                      const SizedBox(width: 8),
                      _buildFilterChip('Assessments', 'assessments'),
                    ],
                  ),
                ],
              ),
            ),
          ),

          // Content
          SliverToBoxAdapter(
            child: _isLoading
                ? const Padding(
                    padding: EdgeInsets.all(48),
                    child: Center(child: CircularProgressIndicator()),
                  )
                : _buildContent(),
          ),
        ],
      ),
    );
  }

  Widget _buildContent() {
    final docs = _filteredDocuments;
    final assessments = _filteredAssessments;
    final hasNoResults = _searchQuery.isNotEmpty &&
        docs.isEmpty &&
        assessments.isEmpty;

    if (hasNoResults) {
      return Padding(
        padding: const EdgeInsets.all(48),
        child: Center(
          child: Column(
            children: [
              Icon(Icons.search_off, size: 40, color: AppTheme.textH(context)),
              const SizedBox(height: 12),
              Text(
                'No results for "$_searchQuery"',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.text2(context),
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Generated Documents
        if (_showGenerated && docs.isNotEmpty) ...[
          _buildSectionHeader('Generated Documents'),
          _buildDocumentsList(docs),
        ],

        // Assessments
        if (_showAssessments) ...[
          _buildSectionHeader('Assessments'),
          if (assessments.isEmpty)
            _buildEmptyAssessments()
          else
            ...assessments.map(_buildAssessmentCard),
        ],

        const SizedBox(height: 32),
      ],
    );
  }

  Widget _buildFilterChip(String label, String filter) {
    final isActive = _activeFilter == filter;
    return GestureDetector(
      onTap: () => setState(() => _activeFilter = filter),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(
          color: isActive
              ? AppTheme.primaryDark.withValues(alpha: 0.15)
              : AppTheme.cardOf(context),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isActive ? AppTheme.primaryDark : AppTheme.borderOf(context),
            width: isActive ? 1.5 : 1,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 13,
            color: isActive ? AppTheme.primaryDark : AppTheme.text2(context),
            fontWeight: isActive ? FontWeight.w600 : FontWeight.w400,
          ),
        ),
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
      child: Text(
        title,
        style: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w700,
          color: AppTheme.text1(context),
          fontFamily: 'Inter',
        ),
      ),
    );
  }

  Widget _buildDocumentsList(List<Map<String, dynamic>> docs) {
    return ListView.builder(
      shrinkWrap: true,
      physics: NeverScrollableScrollPhysics(),
      padding: EdgeInsets.symmetric(horizontal: 16),
      itemCount: docs.length,
      itemBuilder: (context, index) => _buildDocumentRow(docs[index]),
    );
  }

  Widget _buildDocumentRow(Map<String, dynamic> doc) {
    final status = doc['status'] as String? ?? 'draft';
    final createdAt = doc['created_at'] as String?;
    final title = doc['title'] as String? ?? 'Untitled Document';
    final docType = doc['document_type'] as String? ?? '';

    Color statusColor;
    switch (status) {
      case 'finalized':
        statusColor = AppTheme.success;
        break;
      case 'approved':
        statusColor = AppTheme.info;
        break;
      case 'review_required':
        statusColor = AppTheme.warning;
        break;
      default:
        statusColor = AppTheme.text2(context);
    }

    return Card(
      elevation: 0,
      margin: EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(color: AppTheme.borderOf(context)),
      ),
      color: AppTheme.cardOf(context),
      child: InkWell(
        onTap: () {
          final docId = doc['id']?.toString();
          if (docId != null) {
            context.push('/documents/preview/$docId');
          }
        },
        borderRadius: BorderRadius.circular(10),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              // Icon
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: statusColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(Icons.description, color: statusColor, size: 18),
              ),
              const SizedBox(width: 10),
              // Title + type
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.text1(context),
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (docType.isNotEmpty)
                      Text(
                        docType.replaceAll('_', ' '),
                        style: TextStyle(
                          fontSize: 11,
                          color: AppTheme.text2(context),
                        ),
                      ),
                  ],
                ),
              ),
              // Status + date
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: statusColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      status.toUpperCase(),
                      style: TextStyle(
                        fontSize: 9,
                        fontWeight: FontWeight.w600,
                        color: statusColor,
                      ),
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    _formatDate(createdAt),
                    style: TextStyle(
                      fontSize: 10,
                      color: AppTheme.textH(context),
                    ),
                  ),
                ],
              ),
              const SizedBox(width: 6),
              GestureDetector(
                onTap: () {
                  final docId = doc['id']?.toString();
                  if (docId != null) _deleteGeneratedDocument(docId);
                },
                child: Icon(Icons.delete_outline, size: 18, color: AppTheme.textH(context)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatDate(String? dateStr) {
    if (dateStr == null) return '';
    try {
      final date = DateTime.parse(dateStr);
      final now = DateTime.now();
      final diff = now.difference(date);

      if (diff.inMinutes < 60) {
        return '${diff.inMinutes}m ago';
      } else if (diff.inHours < 24) {
        return '${diff.inHours}h ago';
      } else if (diff.inDays == 1) {
        return 'Yesterday';
      } else if (diff.inDays < 7) {
        return '${diff.inDays}d ago';
      } else {
        return '${date.day}/${date.month}/${date.year}';
      }
    } catch (_) {
      return dateStr;
    }
  }

  Widget _buildAssessmentCard(Map<String, dynamic> assessment) {
    final decision = assessment['decision'] ?? 'pending';
    final decisionColor = decision == 'go'
        ? AppTheme.success
        : decision == 'no_go'
            ? AppTheme.error
            : decision == 'refer'
                ? AppTheme.warning
                : AppTheme.textH(context);

    final uploadedCount = assessment['uploaded_count'] ?? 0;
    final generatedCount = assessment['generated_count'] ?? 0;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 3),
      child: Card(
        elevation: 0,
        color: AppTheme.cardOf(context),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
          side: BorderSide(color: AppTheme.borderOf(context)),
        ),
        child: InkWell(
          onTap: () {
            context.push('/reports/documents/${assessment['id']}');
          },
          borderRadius: BorderRadius.circular(10),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                // Decision icon
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: decisionColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(
                    decision == 'go'
                        ? Icons.check_circle
                        : decision == 'no_go'
                            ? Icons.cancel
                            : decision == 'refer'
                                ? Icons.help_outline
                                : Icons.pending,
                    color: decisionColor,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 10),
                // Title + ref
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        assessment['title'] ?? 'Assessment',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text1(context),
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Row(
                        children: [
                          Text(
                            assessment['reference_number'] ?? '',
                            style: TextStyle(
                              fontSize: 11,
                              color: AppTheme.text2(context),
                            ),
                          ),
                          if (uploadedCount > 0 || generatedCount > 0) ...[
                            Text(
                              '  ·  ',
                              style: TextStyle(color: AppTheme.textH(context)),
                            ),
                            Icon(Icons.upload_file, size: 12, color: AppTheme.info),
                            Text(
                              ' $uploadedCount',
                              style: TextStyle(fontSize: 11, color: AppTheme.text2(context)),
                            ),
                            const SizedBox(width: 6),
                            Icon(Icons.auto_awesome, size: 12, color: AppTheme.success),
                            Text(
                              ' $generatedCount',
                              style: TextStyle(fontSize: 11, color: AppTheme.text2(context)),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
                // Decision badge + generate
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: decisionColor.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        decision.toString().toUpperCase().replaceAll('_', ' '),
                        style: TextStyle(
                          fontSize: 9,
                          fontWeight: FontWeight.w600,
                          color: decisionColor,
                        ),
                      ),
                    ),
                    const SizedBox(height: 4),
                    GestureDetector(
                      onTap: () {
                        context.push('/reports/generate/${assessment['id']}');
                      },
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.add, size: 14, color: AppTheme.primaryDark),
                          const SizedBox(width: 2),
                          Text(
                            'Generate',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w500,
                              color: AppTheme.primaryDark,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 4),
                    GestureDetector(
                      onTap: () {
                        final id = assessment['id']?.toString();
                        if (id != null) _deleteAssessment(id);
                      },
                      child: Icon(Icons.delete_outline, size: 16, color: AppTheme.textH(context)),
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

  Widget _buildEmptyAssessments() {
    final l10n = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Center(
        child: Column(
          children: [
            Icon(
              Icons.folder_open,
              size: 40,
              color: AppTheme.textH(context),
            ),
            const SizedBox(height: 12),
            Text(
              l10n.noAssessmentsYet,
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w600,
                color: AppTheme.text2(context),
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Upload documents to create assessments',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13,
                color: AppTheme.textH(context),
              ),
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: () => context.go('/home/intake'),
              icon: const Icon(Icons.upload_file, size: 18),
              label: Text(l10n.uploadDocuments),
              style: OutlinedButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
