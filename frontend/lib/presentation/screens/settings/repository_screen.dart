import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Repository Screen - Document storage management
class RepositoryScreen extends StatefulWidget {
  const RepositoryScreen({super.key});

  @override
  State<RepositoryScreen> createState() => _RepositoryScreenState();
}

class _RepositoryScreenState extends State<RepositoryScreen> {
  String _selectedFilter = 'All';
  final List<String> _filters = ['All', 'Assessments', 'Contracts', 'Reports'];

  // Mock document data
  final List<RepositoryDocument> _documents = [
    RepositoryDocument(
      name: 'Property_Assessment_Acme.pdf',
      type: 'Assessment',
      size: 2.4,
      date: DateTime.now().subtract(const Duration(days: 1)),
    ),
    RepositoryDocument(
      name: 'Insurance_Contract_2026.pdf',
      type: 'Contract',
      size: 1.8,
      date: DateTime.now().subtract(const Duration(days: 3)),
    ),
    RepositoryDocument(
      name: 'Risk_Report_Q1_2026.pdf',
      type: 'Report',
      size: 5.2,
      date: DateTime.now().subtract(const Duration(days: 5)),
    ),
    RepositoryDocument(
      name: 'Liability_Assessment_Tech.pdf',
      type: 'Assessment',
      size: 3.1,
      date: DateTime.now().subtract(const Duration(days: 7)),
    ),
    RepositoryDocument(
      name: 'Motor_Fleet_Contract.pdf',
      type: 'Contract',
      size: 1.5,
      date: DateTime.now().subtract(const Duration(days: 10)),
    ),
    RepositoryDocument(
      name: 'Annual_Portfolio_Report.pdf',
      type: 'Report',
      size: 8.7,
      date: DateTime.now().subtract(const Duration(days: 14)),
    ),
  ];

  List<RepositoryDocument> get _filteredDocuments {
    if (_selectedFilter == 'All') return _documents;
    return _documents.where((d) => d.type + 's' == _selectedFilter).toList();
  }

  double get _totalStorageUsed {
    return _documents.fold(0, (sum, doc) => sum + doc.size);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_ios, color: AppTheme.text1(context)),
          onPressed: () => context.go('/settings'),
        ),
        title: Text(
          l10n.documentRepository,
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.text1(context),
            fontFamily: 'Inter',
          ),
        ),
        centerTitle: true,
        actions: [
          IconButton(
            icon: Icon(Icons.search, color: AppTheme.text1(context)),
            onPressed: () {
              // TODO: Implement search
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // Storage Usage Card
          Padding(
            padding: const EdgeInsets.all(20),
            child: Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.surfaceOf(context),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.borderOf(context)),
              ),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Storage Used',
                            style: TextStyle(
                              fontSize: 14,
                              color: AppTheme.text2(context),
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            '${_totalStorageUsed.toStringAsFixed(1)} GB / 10 GB',
                            style: TextStyle(
                              fontSize: 20,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.text1(context),
                            ),
                          ),
                        ],
                      ),
                      Stack(
                        alignment: Alignment.center,
                        children: [
                          SizedBox(
                            width: 60,
                            height: 60,
                            child: CircularProgressIndicator(
                              value: _totalStorageUsed / 10,
                              strokeWidth: 6,
                              backgroundColor: AppTheme.borderOf(context),
                              valueColor: AlwaysStoppedAnimation<Color>(
                                _totalStorageUsed / 10 > 0.8 ? AppTheme.danger : AppTheme.primaryDark,
                              ),
                            ),
                          ),
                          Text(
                            '${((_totalStorageUsed / 10) * 100).toInt()}%',
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.text1(context),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      _buildStorageIndicator('Assessments', AppTheme.primaryDark),
                      const SizedBox(width: 16),
                      _buildStorageIndicator('Contracts', AppTheme.accent),
                      const SizedBox(width: 16),
                      _buildStorageIndicator('Reports', AppTheme.warning),
                    ],
                  ),
                ],
              ),
            ),
          ),

          // Filter Chips
          SizedBox(
            height: 40,
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              scrollDirection: Axis.horizontal,
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
                    selectedColor: AppTheme.primaryDark,
                    labelStyle: TextStyle(
                      color: isSelected ? Colors.white : AppTheme.text2(context),
                      fontWeight: FontWeight.w500,
                    ),
                    side: BorderSide(
                      color: isSelected ? AppTheme.primaryDark : AppTheme.borderOf(context),
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(20),
                    ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 16),

          // Document Count
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  '${_filteredDocuments.length} documents',
                  style: TextStyle(
                    fontSize: 14,
                    color: AppTheme.text2(context),
                  ),
                ),
                TextButton.icon(
                  onPressed: () {
                    // TODO: Sort documents
                  },
                  icon: const Icon(Icons.sort, size: 18),
                  label: const Text('Sort'),
                  style: TextButton.styleFrom(
                    foregroundColor: AppTheme.text2(context),
                  ),
                ),
              ],
            ),
          ),

          // Document List
          Expanded(
            child: _filteredDocuments.isEmpty
                ? _buildEmptyState(l10n)
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    itemCount: _filteredDocuments.length,
                    itemBuilder: (context, index) {
                      return _buildDocumentItem(_filteredDocuments[index]);
                    },
                  ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          // TODO: Upload new document
        },
        backgroundColor: AppTheme.primaryDark,
        child: const Icon(Icons.add, color: Colors.white),
      ),
    );
  }

  Widget _buildStorageIndicator(String label, Color color) {
    return Row(
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(3),
          ),
        ),
        const SizedBox(width: 6),
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

  Widget _buildDocumentItem(RepositoryDocument doc) {
    IconData iconData;
    Color iconColor;

    switch (doc.type) {
      case 'Assessment':
        iconData = Icons.assessment_outlined;
        iconColor = AppTheme.primaryDark;
        break;
      case 'Contract':
        iconData = Icons.description_outlined;
        iconColor = AppTheme.accent;
        break;
      default:
        iconData = Icons.summarize_outlined;
        iconColor = AppTheme.warning;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () {
            // TODO: Open document
          },
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: iconColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(iconData, color: iconColor, size: 22),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        doc.name,
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                          color: AppTheme.text1(context),
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: iconColor.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              doc.type,
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w600,
                                color: iconColor,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            '${doc.size} MB',
                            style: TextStyle(
                              fontSize: 12,
                              color: AppTheme.textH(context),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            _formatDate(doc.date),
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
                PopupMenuButton<String>(
                  icon: Icon(Icons.more_vert, color: AppTheme.textH(context)),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  itemBuilder: (context) => [
                    const PopupMenuItem(
                      value: 'download',
                      child: Row(
                        children: [
                          Icon(Icons.download_outlined, size: 20),
                          SizedBox(width: 12),
                          Text('Download'),
                        ],
                      ),
                    ),
                    const PopupMenuItem(
                      value: 'share',
                      child: Row(
                        children: [
                          Icon(Icons.share_outlined, size: 20),
                          SizedBox(width: 12),
                          Text('Share'),
                        ],
                      ),
                    ),
                    const PopupMenuItem(
                      value: 'delete',
                      child: Row(
                        children: [
                          Icon(Icons.delete_outline, color: AppTheme.danger, size: 20),
                          SizedBox(width: 12),
                          Text('Delete', style: TextStyle(color: AppTheme.danger)),
                        ],
                      ),
                    ),
                  ],
                  onSelected: (value) {
                    switch (value) {
                      case 'download':
                        // TODO: Download document
                        break;
                      case 'share':
                        // TODO: Share document
                        break;
                      case 'delete':
                        _showDeleteDialog(doc);
                        break;
                    }
                  },
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState(AppLocalizations l10n) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppTheme.primaryDark.withOpacity(0.1),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.folder_open_outlined,
              size: 48,
              color: AppTheme.primaryDark,
            ),
          ),
          const SizedBox(height: 20),
          Text(
            l10n.noData,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: AppTheme.text1(context),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            l10n.uploadDocument,
            style: TextStyle(
              fontSize: 14,
              color: AppTheme.text2(context),
            ),
          ),
        ],
      ),
    );
  }

  void _showDeleteDialog(RepositoryDocument doc) {
    final l10n = AppLocalizations.of(context);
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(l10n.delete),
        content: Text('Are you sure you want to delete "${doc.name}"?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(
              l10n.cancel,
              style: TextStyle(color: AppTheme.text2(context)),
            ),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              setState(() {
                _documents.remove(doc);
              });
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text(l10n.delete),
                  backgroundColor: AppTheme.success,
                  behavior: SnackBarBehavior.floating,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
              );
            },
            child: Text(
              l10n.delete,
              style: const TextStyle(color: AppTheme.danger),
            ),
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final difference = now.difference(date).inDays;
    if (difference == 0) return 'Today';
    if (difference == 1) return 'Yesterday';
    if (difference < 7) return '$difference days ago';
    return '${date.day}/${date.month}/${date.year}';
  }
}

class RepositoryDocument {
  final String name;
  final String type;
  final double size;
  final DateTime date;

  RepositoryDocument({
    required this.name,
    required this.type,
    required this.size,
    required this.date,
  });
}
