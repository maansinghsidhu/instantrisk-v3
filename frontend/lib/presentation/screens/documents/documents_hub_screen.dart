import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:async';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/documents_prefetch_service.dart';
import '../../../l10n/generated/app_localizations.dart';

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
  List<Map<String, dynamic>> _trainingDocuments = [];
  bool _isLoading = true;
  Timer? _refreshTimer;
  String _searchQuery = '';
  bool _showAllAssessments = false;
  String _activeFilter = 'all'; // all, generated, training, assessments, templates

  // Template categories
  static final List<Map<String, dynamic>> _templateCategories = [
    {
      'id': 'cyber',
      'name': 'Cyber',
      'icon': Icons.security,
      'color': AppTheme.lobColors[0],
      'count': 15,
    },
    {
      'id': 'marine',
      'name': 'Marine',
      'icon': Icons.directions_boat,
      'color': AppTheme.lobColors[1],
      'count': 23,
    },
    {
      'id': 'aviation',
      'name': 'Aviation',
      'icon': Icons.flight,
      'color': AppTheme.lobColors[2],
      'count': 12,
    },
    {
      'id': 'property',
      'name': 'Property',
      'icon': Icons.business,
      'color': AppTheme.lobColors[3],
      'count': 18,
    },
    {
      'id': 'casualty',
      'name': 'Casualty',
      'icon': Icons.person_outline,
      'color': AppTheme.lobColors[4],
      'count': 15,
    },
    {
      'id': 'financial',
      'name': 'Financial',
      'icon': Icons.account_balance,
      'color': AppTheme.lobColors[5],
      'count': 14,
    },
    {
      'id': 'energy',
      'name': 'Energy',
      'icon': Icons.bolt,
      'color': AppTheme.lobColors[6],
      'count': 11,
    },
    {
      'id': 'reinsurance',
      'name': 'Reinsurance',
      'icon': Icons.autorenew,
      'color': AppTheme.lobColors[7],
      'count': 8,
    },
  ];

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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      body: CustomScrollView(
        slivers: [
          // Custom App Bar
          SliverAppBar(
            expandedHeight: 120,
            floating: false,
            pinned: true,
            backgroundColor: AppTheme.primaryDark,
            leading: IconButton(
              icon: const Icon(Icons.arrow_back_ios, color: Colors.white),
              onPressed: () => context.go('/home'),
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.search, color: Colors.white),
                onPressed: _showSearchDialog,
              ),
              IconButton(
                icon: const Icon(Icons.refresh, color: Colors.white),
                onPressed: _loadData,
              ),
            ],
            flexibleSpace: FlexibleSpaceBar(
              title: Text(
                AppLocalizations.of(context).documentCenter,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              background: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      AppTheme.primaryDark,
                      AppTheme.primaryLight,
                    ],
                  ),
                ),
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
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const SizedBox(height: 8),

                      // Filter Chips
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        child: Row(
                          children: [
                            _buildFilterChip('All', 'all'),
                            _buildFilterChip('Generated', 'generated'),
                            _buildFilterChip('Training', 'training'),
                            _buildFilterChip('Assessments', 'assessments'),
                            _buildFilterChip('Templates', 'templates'),
                          ],
                        ),
                      ),
                      const SizedBox(height: 8),

                      // Recent Documents Section
                      if (_recentDocuments.isNotEmpty) ...[
                        _buildSectionHeader(
                          AppLocalizations.of(context).recentDocuments,
                          onViewAll: () => context.push('/reports'),
                        ),
                        _buildRecentDocumentsList(),
                      ],

                      // Assessment Documents Section
                      _buildSectionHeader(
                        AppLocalizations.of(context).assessmentDocuments,
                        onViewAll: _assessments.length > 3
                            ? () {
                                setState(() {
                                  _showAllAssessments = !_showAllAssessments;
                                });
                              }
                            : null,
                        viewAllLabel: _showAllAssessments ? 'Show Less' : 'View All',
                      ),
                      if (_assessments.isEmpty)
                        _buildEmptyAssessments()
                      else
                        ...(_showAllAssessments
                            ? _assessments
                            : _assessments.take(3))
                            .map(_buildAssessmentCard),

                      const SizedBox(height: 32), // Bottom padding
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String label, String filter) {
    final isActive = _activeFilter == filter;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: FilterChip(
        label: Text(label),
        selected: isActive,
        onSelected: (_) => setState(() => _activeFilter = filter),
        selectedColor: AppTheme.primaryDark.withValues(alpha: 0.2),
        checkmarkColor: AppTheme.primaryDark,
        labelStyle: TextStyle(
          fontSize: 13,
          color: isActive ? AppTheme.primaryDark : AppTheme.textSecondary,
          fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
        ),
      ),
    );
  }

  Widget _buildSectionHeader(
    String title, {
    String? subtitle,
    VoidCallback? onViewAll,
    String viewAllLabel = 'View All',
  }) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                  fontFamily: 'Inter',
                ),
              ),
              if (subtitle != null)
                Text(
                  subtitle,
                  style: TextStyle(
                    fontSize: 13,
                    color: AppTheme.textSecondary,
                  ),
                ),
            ],
          ),
          if (onViewAll != null)
            TextButton(
              onPressed: onViewAll,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(viewAllLabel),
                  const SizedBox(width: 4),
                  Icon(
                    viewAllLabel == 'Show Less'
                        ? Icons.keyboard_arrow_up
                        : Icons.arrow_forward,
                    size: 16,
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildSectionHeaderWithIcon(
    String title, {
    required IconData icon,
    required Color iconColor,
    String? subtitle,
    VoidCallback? onViewAll,
  }) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: iconColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  icon,
                  color: iconColor,
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                      fontFamily: 'Inter',
                    ),
                  ),
                  if (subtitle != null)
                    Text(
                      subtitle,
                      style: TextStyle(
                        fontSize: 13,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                ],
              ),
            ],
          ),
          if (onViewAll != null)
            TextButton.icon(
              onPressed: onViewAll,
              icon: const Icon(Icons.folder_open, size: 16),
              label: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('View All'),
                  const SizedBox(width: 4),
                  const Icon(Icons.arrow_forward, size: 16),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildRecentDocumentsList() {
    return SizedBox(
      height: 140,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        itemCount: _recentDocuments.length,
        itemBuilder: (context, index) {
          final doc = _recentDocuments[index];
          return _buildRecentDocumentCard(doc);
        },
      ),
    );
  }

  Widget _buildRecentDocumentCard(Map<String, dynamic> doc) {
    final status = doc['status'] as String? ?? 'draft';
    final createdAt = doc['created_at'] as String?;

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
        statusColor = AppTheme.textSecondary;
    }

    return Container(
      width: 200,
      margin: const EdgeInsets.symmetric(horizontal: 4),
      child: Card(
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: AppTheme.border),
        ),
        child: InkWell(
          onTap: () {
            final docId = doc['id']?.toString();
            if (docId != null) {
              context.push('/documents/preview/$docId');
            }
          },
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: statusColor.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Icon(
                        Icons.description,
                        color: statusColor,
                        size: 18,
                      ),
                    ),
                    const Spacer(),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 3,
                      ),
                      decoration: BoxDecoration(
                        color: statusColor.withOpacity(0.1),
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
                  ],
                ),
                const SizedBox(height: 12),
                Text(
                  doc['title'] as String? ?? 'Untitled Document',
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const Spacer(),
                Text(
                  _formatDate(createdAt),
                  style: TextStyle(
                    fontSize: 11,
                    color: AppTheme.textHint,
                  ),
                ),
              ],
            ),
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
        return '${diff.inMinutes} min ago';
      } else if (diff.inHours < 24) {
        return '${diff.inHours} hours ago';
      } else if (diff.inDays == 1) {
        return 'Yesterday';
      } else if (diff.inDays < 7) {
        return '${diff.inDays} days ago';
      } else {
        return '${date.day}/${date.month}/${date.year}';
      }
    } catch (_) {
      return dateStr;
    }
  }

  Widget _buildTemplatesGrid() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        int crossAxisCount;
        double childAspectRatio;

        if (width > 900) {
          crossAxisCount = 6;
          childAspectRatio = 1.0;
        } else if (width > 600) {
          crossAxisCount = 4;
          childAspectRatio = 0.95;
        } else {
          crossAxisCount = 3;
          childAspectRatio = 0.9;
        }

        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: crossAxisCount,
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
              childAspectRatio: childAspectRatio,
            ),
            itemCount: _templateCategories.length,
            itemBuilder: (context, index) {
              final category = _templateCategories[index];
              return _buildTemplateCategoryCard(category);
            },
          ),
        );
      },
    );
  }

  Widget _buildTemplateCategoryCard(Map<String, dynamic> category) {
    final Color color = category['color'] as Color;

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: AppTheme.border),
      ),
      child: InkWell(
        onTap: () {
          context.push('/templates', extra: {
            'category': category['id'],
          });
        },
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: color.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  category['icon'] as IconData,
                  color: color,
                  size: 22,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                category['name'] as String,
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                ),
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              Text(
                '${category['count']} docs',
                style: TextStyle(
                  fontSize: 9,
                  color: AppTheme.textHint,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAssessmentCard(Map<String, dynamic> assessment) {
    final decision = assessment['decision'] ?? 'pending';
    final decisionColor = decision == 'go'
        ? AppTheme.success
        : decision == 'no_go'
            ? AppTheme.error
            : decision == 'refer'
                ? AppTheme.warning
                : AppTheme.textHint;

    final uploadedCount = assessment['uploaded_count'] ?? 0;
    final generatedCount = assessment['generated_count'] ?? 0;
    final totalDocs = uploadedCount + generatedCount;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Card(
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: AppTheme.border),
        ),
        child: InkWell(
          onTap: () {
            context.push('/reports/documents/${assessment['id']}');
          },
          borderRadius: BorderRadius.circular(14),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header row
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: decisionColor.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(
                        decision == 'go'
                            ? Icons.check_circle
                            : decision == 'no_go'
                                ? Icons.cancel
                                : decision == 'refer'
                                    ? Icons.help
                                    : Icons.pending,
                        color: decisionColor,
                        size: 22,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            assessment['title'] ?? 'Assessment',
                            style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w600,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 2),
                          Text(
                            assessment['reference_number'] ?? '',
                            style: TextStyle(
                              fontSize: 12,
                              color: AppTheme.textSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: decisionColor.withOpacity(0.1),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            decision
                                .toString()
                                .toUpperCase()
                                .replaceAll('_', ' '),
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w600,
                              color: decisionColor,
                            ),
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '$totalDocs docs',
                          style: TextStyle(
                            fontSize: 11,
                            color: AppTheme.textHint,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),

                // Document summary
                const SizedBox(height: 12),
                Row(
                  children: [
                    _buildDocBadge(
                      icon: Icons.upload_file,
                      count: uploadedCount,
                      label: 'Uploaded',
                      color: AppTheme.info,
                    ),
                    const SizedBox(width: 12),
                    _buildDocBadge(
                      icon: Icons.auto_awesome,
                      count: generatedCount,
                      label: 'Generated',
                      color: AppTheme.success,
                    ),
                    const Spacer(),
                    TextButton(
                      onPressed: () {
                        context.push('/reports/generate/${assessment['id']}');
                      },
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.add, size: 16),
                          SizedBox(width: 4),
                          Text('Generate'),
                        ],
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

  Widget _buildDocBadge({
    required IconData icon,
    required int count,
    required String label,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Text(
            '$count $label',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w500,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyAssessments() {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Center(
        child: Column(
          children: [
            Icon(
              Icons.folder_open,
              size: 48,
              color: AppTheme.textHint.withOpacity(0.5),
            ),
            const SizedBox(height: 16),
            Text(
              AppLocalizations.of(context).noAssessmentsYet,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Upload documents to create assessments and generate AI-powered documents',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13,
                color: AppTheme.textHint,
              ),
            ),
            const SizedBox(height: 20),
            OutlinedButton.icon(
              onPressed: () => context.go('/home/intake'),
              icon: const Icon(Icons.upload_file),
              label: Text(AppLocalizations.of(context).uploadDocuments),
              style: OutlinedButton.styleFrom(
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 12,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showSearchDialog() {
    final l10n = AppLocalizations.of(context);
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(l10n.searchDocuments),
        content: TextField(
          autofocus: true,
          decoration: InputDecoration(
            hintText: 'Search by title, type, or reference...',
            prefixIcon: const Icon(Icons.search),
            border: const OutlineInputBorder(),
          ),
          onChanged: (value) {
            setState(() => _searchQuery = value);
          },
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: Text(l10n.cancel),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              // Perform search
              _performSearch();
            },
            child: Text(l10n.search),
          ),
        ],
      ),
    );
  }

  void _performSearch() {
    // TODO: Implement search functionality
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Searching for "$_searchQuery"...')),
    );
  }
}
