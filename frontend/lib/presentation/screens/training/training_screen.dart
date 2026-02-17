import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'dart:convert';
import 'package:file_picker/file_picker.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../widgets/common/screen_header.dart';
// God Mode: Risk alerts panel for fraud detection warnings
import '../../widgets/monitoring/risk_alerts_panel.dart';

/// Training Screen - Upload documents to improve AI analysis
class TrainingScreen extends ConsumerStatefulWidget {
  const TrainingScreen({super.key});

  @override
  ConsumerState<TrainingScreen> createState() => _TrainingScreenState();
}

class _TrainingScreenState extends ConsumerState<TrainingScreen> {
  List<Map<String, dynamic>> _uploadedDocuments = [];
  bool _isLoading = true;
  bool _isUploading = false;
  String _selectedCategory = 'all';

  final TextEditingController _searchController = TextEditingController();
  String _searchQuery = '';

  final List<Map<String, dynamic>> _categories = [
    {'id': 'all', 'name': 'All Documents', 'icon': Icons.folder_outlined},
    {'id': 'policy', 'name': 'Policies', 'icon': Icons.policy_outlined},
    {'id': 'loss_run', 'name': 'Loss Runs', 'icon': Icons.assessment_outlined},
    {'id': 'claims', 'name': 'Claims', 'icon': Icons.report_problem_outlined},
    {'id': 'underwriting', 'name': 'Underwriting', 'icon': Icons.rule_outlined},
    {'id': 'regulatory', 'name': 'Regulatory', 'icon': Icons.gavel_outlined},
    {'id': 'market', 'name': 'Market Data', 'icon': Icons.trending_up_outlined},
    {'id': 'slip_template', 'name': 'Slips', 'icon': Icons.receipt_long_outlined},
    {'id': 'endorsement', 'name': 'Endorsements', 'icon': Icons.post_add_outlined},
    {'id': 'clause_library', 'name': 'Clauses', 'icon': Icons.library_books_outlined},
  ];

  static const Map<String, String> _categoryLabels = {
    'policy': 'Policy',
    'loss_run': 'Loss Run',
    'claims': 'Claims',
    'underwriting': 'Underwriting',
    'regulatory': 'Regulatory',
    'market': 'Market Data',
    'slip_template': 'Slip Template',
    'endorsement': 'Endorsement',
    'clause_library': 'Clause Library',
  };

  @override
  void initState() {
    super.initState();
    _loadTrainingDocuments();
  }

  Future<void> _loadTrainingDocuments() async {
    setState(() => _isLoading = true);

    try {
      final response = await authService.get('/training/documents');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _uploadedDocuments = List<Map<String, dynamic>>.from(data['documents'] ?? []);
          _isLoading = false;
        });
      } else {
        setState(() => _isLoading = false);
      }
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _uploadDocument() async {
    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf', 'doc', 'docx', 'xlsx', 'xls', 'csv', 'txt'],
        allowMultiple: true,
      );

      if (result == null || result.files.isEmpty) return;

      setState(() => _isUploading = true);

      for (var file in result.files) {
        if (file.bytes == null) continue;

        final response = await authService.uploadFileBytes(
          '/training/upload',
          file.bytes!,
          file.name,
          'file',
          fields: {
            'category': _selectedCategory == 'all' ? 'auto' : _selectedCategory,
          },
        );

        if (response.statusCode == 200) {
          // Parse the streamed response body
          final body = await response.stream.bytesToString();
          final data = jsonDecode(body);

          if (mounted) {
            _showClassificationResult(data, file.name);
          }
        } else {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Failed to upload ${file.name}'),
                backgroundColor: AppTheme.error,
              ),
            );
          }
        }
      }

      await _loadTrainingDocuments();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Upload failed: $e'),
            backgroundColor: AppTheme.error,
          ),
        );
      }
    } finally {
      setState(() => _isUploading = false);
    }
  }

  void _showClassificationResult(Map<String, dynamic> data, String filename) {
    final category = data['category'] ?? 'policy';
    final method = data['classification_method'] ?? 'user_selected';
    final keywords = List<String>.from(data['classification_keywords'] ?? []);
    final chunks = data['chunks_created'] ?? 0;
    final impact = data['training_impact'] as Map<String, dynamic>? ?? {};

    String methodLabel;
    IconData methodIcon;
    switch (method) {
      case 'filename':
        methodLabel = 'Detected from filename';
        methodIcon = Icons.text_fields;
        break;
      case 'content':
        methodLabel = 'Detected from document content';
        methodIcon = Icons.document_scanner;
        break;
      case 'user_selected':
        methodLabel = 'You selected this category';
        methodIcon = Icons.touch_app;
        break;
      default:
        methodLabel = 'Default classification';
        methodIcon = Icons.auto_fix_high;
    }

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Row(
          children: [
            Icon(Icons.check_circle, color: AppTheme.success, size: 24),
            const SizedBox(width: 10),
            const Expanded(child: Text('Document Processed')),
          ],
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Filename
              Text(
                filename,
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  color: AppTheme.text1(ctx),
                ),
              ),
              const SizedBox(height: 16),

              // Classification
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.primaryDark.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppTheme.primaryDark.withOpacity(0.2)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'CLASSIFIED AS',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.text2(ctx),
                        letterSpacing: 1,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      _categoryLabels[category] ?? category,
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.text1(ctx),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Icon(methodIcon, size: 14, color: AppTheme.text2(ctx)),
                        const SizedBox(width: 6),
                        Text(
                          methodLabel,
                          style: TextStyle(
                            fontSize: 12,
                            color: AppTheme.text2(ctx),
                          ),
                        ),
                      ],
                    ),
                    if (keywords.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        'Keywords: ${keywords.join(", ")}',
                        style: TextStyle(
                          fontSize: 11,
                          color: AppTheme.textH(ctx),
                          fontStyle: FontStyle.italic,
                        ),
                      ),
                    ],
                  ],
                ),
              ),

              const SizedBox(height: 12),

              // Chunks info
              Row(
                children: [
                  Icon(Icons.data_object, size: 16, color: AppTheme.text2(ctx)),
                  const SizedBox(width: 6),
                  Text(
                    '$chunks text chunks indexed for AI',
                    style: TextStyle(fontSize: 13, color: AppTheme.text2(ctx)),
                  ),
                ],
              ),

              // Training impact
              if (impact.isNotEmpty) ...[
                const SizedBox(height: 16),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.cardAltOf(ctx),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'HOW THIS HELPS YOUR AI',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.text2(ctx),
                          letterSpacing: 1,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        impact['description']?.toString() ?? '',
                        style: TextStyle(
                          fontSize: 13,
                          color: AppTheme.text1(ctx),
                          height: 1.4,
                        ),
                      ),
                      const SizedBox(height: 8),
                      if (impact['appetite_effect'] != null && impact['appetite_effect'] != 'Neutral')
                        _ImpactRow(label: 'Appetite', value: impact['appetite_effect'].toString()),
                      if (impact['pricing_effect'] != null && impact['pricing_effect'] != 'Neutral')
                        _ImpactRow(label: 'Pricing', value: impact['pricing_effect'].toString()),
                      if (impact['rag_effect'] != null)
                        _ImpactRow(label: 'Documents', value: impact['rag_effect'].toString()),
                    ],
                  ),
                ),
              ],

              const SizedBox(height: 8),
              Text(
                'Wrong category? Tap the category label on the document card to change it.',
                style: TextStyle(
                  fontSize: 11,
                  color: AppTheme.textH(ctx),
                  fontStyle: FontStyle.italic,
                ),
              ),
            ],
          ),
        ),
        actions: [
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Got it'),
          ),
        ],
      ),
    );
  }

  Future<void> _updateDocumentCategory(String docId, String newCategory) async {
    try {
      final response = await authService.patch(
        '/training/documents/$docId/category',
        body: {'new_category': newCategory},
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final chunksUpdated = data['chunks_updated'] ?? 0;

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Category changed to ${_categoryLabels[newCategory] ?? newCategory} ($chunksUpdated chunks updated)'),
              backgroundColor: AppTheme.success,
            ),
          );
          _loadTrainingDocuments();
        }
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Failed to update category'),
              backgroundColor: AppTheme.error,
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: AppTheme.error),
        );
      }
    }
  }

  void _showCategoryPicker(String docId, String currentCategory) {
    final validCategories = _categories.where((c) => c['id'] != 'all').toList();

    showModalBottomSheet(
      context: context,
      backgroundColor: AppTheme.surfaceOf(context),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text(
                'Change Category',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.text1(ctx),
                ),
              ),
            ),
            Divider(height: 1, color: AppTheme.borderOf(ctx)),
            ...validCategories.map((cat) {
              final isSelected = cat['id'] == currentCategory;
              return ListTile(
                leading: Icon(
                  cat['icon'] as IconData,
                  color: isSelected ? AppTheme.primaryDark : AppTheme.text2(ctx),
                ),
                title: Text(
                  cat['name'] as String,
                  style: TextStyle(
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                    color: isSelected ? AppTheme.primaryDark : AppTheme.text1(ctx),
                  ),
                ),
                trailing: isSelected
                    ? const Icon(Icons.check, color: AppTheme.primaryDark)
                    : null,
                onTap: () {
                  Navigator.pop(ctx);
                  if (cat['id'] != currentCategory) {
                    _updateDocumentCategory(docId, cat['id'] as String);
                  }
                },
              );
            }),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  Future<void> _deleteDocument(String docId) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Document'),
        content: const Text('Are you sure you want to remove this training document?'),
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
      final response = await authService.delete('/training/documents/$docId');
      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Document removed')),
        );
        _loadTrainingDocuments();
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to delete: $e')),
      );
    }
  }

  List<Map<String, dynamic>> get _filteredDocuments {
    var docs = _uploadedDocuments;
    if (_selectedCategory != 'all') {
      docs = docs.where((doc) => doc['category'] == _selectedCategory).toList();
    }
    if (_searchQuery.isNotEmpty) {
      final query = _searchQuery.toLowerCase();
      docs = docs.where((doc) {
        final name = (doc['filename'] ?? doc['name'] ?? '').toString().toLowerCase();
        final category = (doc['category'] ?? '').toString().toLowerCase();
        return name.contains(query) || category.contains(query);
      }).toList();
    }
    return docs;
  }

  int get _totalChunks {
    int total = 0;
    for (final doc in _uploadedDocuments) {
      total += (doc['chunk_count'] as num?)?.toInt() ?? 0;
    }
    return total;
  }

  @override
  Widget build(BuildContext context) {
    final isDark = AppTheme.isDark(context);

    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      body: Column(
        children: [
          ScreenHeader(
            title: 'Document Training',
            subtitle: 'Improve AI with your documents',
            actions: [
              IconButton(
                icon: const Icon(Icons.refresh, color: Colors.white),
                onPressed: _loadTrainingDocuments,
                tooltip: 'Refresh',
              ),
            ],
          ),
          Expanded(
            child: Column(
              children: [
                // Stats bar - clean corporate look
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceOf(context),
                    border: Border(
                      bottom: BorderSide(color: AppTheme.borderOf(context)),
                    ),
                  ),
                  child: Row(
                    children: [
                      _StatPill(
                        icon: Icons.description_outlined,
                        value: '${_uploadedDocuments.length}',
                        label: 'Documents',
                        context: context,
                      ),
                      const SizedBox(width: 16),
                      _StatPill(
                        icon: Icons.data_object,
                        value: '$_totalChunks',
                        label: 'Chunks',
                        context: context,
                      ),
                      const SizedBox(width: 16),
                      _StatPill(
                        icon: Icons.check_circle_outline,
                        value: '${_uploadedDocuments.where((d) => d['processed'] == true).length}',
                        label: 'Processed',
                        context: context,
                      ),
                      const Spacer(),
                      // Upload button inline
                      ElevatedButton.icon(
                        onPressed: _isUploading ? null : _uploadDocument,
                        icon: _isUploading
                            ? SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: isDark ? AppTheme.darkBg : Colors.white,
                                ),
                              )
                            : const Icon(Icons.upload_file, size: 18),
                        label: Text(_isUploading ? 'Uploading...' : 'Upload'),
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                        ),
                      ),
                    ],
                  ),
                ),

                // Search bar
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: TextField(
                    controller: _searchController,
                    onChanged: (v) => setState(() => _searchQuery = v),
                    decoration: InputDecoration(
                      hintText: 'Search documents...',
                      prefixIcon: Icon(Icons.search, size: 20),
                      suffixIcon: _searchQuery.isNotEmpty
                          ? IconButton(
                              icon: Icon(Icons.clear, size: 18),
                              onPressed: () {
                                _searchController.clear();
                                setState(() => _searchQuery = '');
                              },
                            )
                          : null,
                      filled: true,
                      fillColor: AppTheme.surfaceOf(context),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide(color: AppTheme.borderOf(context)),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide(color: AppTheme.borderOf(context)),
                      ),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      isDense: true,
                    ),
                  ),
                ),

                // Category filter
                Container(
                  height: 46,
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  child: ListView.builder(
                    scrollDirection: Axis.horizontal,
                    itemCount: _categories.length,
                    itemBuilder: (ctx, index) {
                      final cat = _categories[index];
                      final isSelected = _selectedCategory == cat['id'];
                      return Padding(
                        padding: EdgeInsets.symmetric(horizontal: 3, vertical: 6),
                        child: FilterChip(
                          label: Text(
                            cat['name'] as String,
                            style: TextStyle(
                              fontSize: 12,
                              color: isSelected ? AppTheme.primaryDark : AppTheme.text2(context),
                              fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                            ),
                          ),
                          selected: isSelected,
                          onSelected: (_) => setState(() => _selectedCategory = cat['id'] as String),
                          backgroundColor: AppTheme.surfaceOf(context),
                          selectedColor: AppTheme.primaryDark.withOpacity(0.12),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(20),
                            side: BorderSide(
                              color: isSelected ? AppTheme.primaryDark : AppTheme.borderOf(context),
                            ),
                          ),
                          showCheckmark: false,
                          visualDensity: VisualDensity.compact,
                          padding: EdgeInsets.symmetric(horizontal: 8),
                        ),
                      );
                    },
                  ),
                ),

                Divider(height: 1, color: AppTheme.borderOf(context)),

                // God Mode: Fraud detection warnings from monitoring service
                if (_uploadedDocuments.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    child: RiskAlertsPanel(
                      showHeader: true,
                      maxAlerts: 3,
                    ),
                  ),

                // Document list
                Expanded(
                  child: _isLoading
                      ? const Center(child: CircularProgressIndicator())
                      : _filteredDocuments.isEmpty
                          ? _EmptyState(onUpload: _uploadDocument)
                          : ListView.builder(
                              padding: const EdgeInsets.all(16),
                              itemCount: _filteredDocuments.length,
                              itemBuilder: (ctx, index) {
                                final doc = _filteredDocuments[index];
                                return _DocumentCard(
                                  document: doc,
                                  onDelete: () => _deleteDocument(doc['id']),
                                  onCategoryTap: () => _showCategoryPicker(
                                    doc['id'],
                                    doc['category'] ?? 'policy',
                                  ),
                                );
                              },
                            ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _StatPill extends StatelessWidget {
  final IconData icon;
  final String value;
  final String label;
  final BuildContext context;

  const _StatPill({
    required this.icon,
    required this.value,
    required this.label,
    required this.context,
  });

  @override
  Widget build(BuildContext c) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: AppTheme.text2(context)),
        const SizedBox(width: 6),
        Text(
          value,
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w700,
            color: AppTheme.text1(context),
          ),
        ),
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
}

class _EmptyState extends StatelessWidget {
  final VoidCallback onUpload;

  const _EmptyState({required this.onUpload});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.cloud_upload_outlined,
            size: 64,
            color: AppTheme.textH(context),
          ),
          const SizedBox(height: 16),
          Text(
            'No Training Documents Yet',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: AppTheme.text1(context),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Upload insurance documents to train the AI\nand improve analysis accuracy',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 14,
              color: AppTheme.text2(context),
            ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: onUpload,
            icon: const Icon(Icons.upload_file),
            label: const Text('Upload Your First Document'),
          ),
        ],
      ),
    );
  }
}

class _ImpactRow extends StatelessWidget {
  final String label;
  final String value;

  const _ImpactRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 72,
            child: Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: AppTheme.text2(context),
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 11,
                color: AppTheme.text1(context),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DocumentCard extends StatelessWidget {
  final Map<String, dynamic> document;
  final VoidCallback onDelete;
  final VoidCallback onCategoryTap;

  const _DocumentCard({
    required this.document,
    required this.onDelete,
    required this.onCategoryTap,
  });

  static const Map<String, String> _labels = {
    'policy': 'Policy',
    'loss_run': 'Loss Run',
    'claims': 'Claims',
    'underwriting': 'Underwriting',
    'regulatory': 'Regulatory',
    'market': 'Market',
    'slip_template': 'Slip',
    'endorsement': 'Endorsement',
    'clause_library': 'Clauses',
  };

  @override
  Widget build(BuildContext context) {
    final processed = document['processed'] == true;
    final category = document['category'] ?? 'policy';
    final chunkCount = document['chunk_count'] ?? 0;
    final impact = document['training_impact'] as Map<String, dynamic>?;
    final description = impact?['description']?.toString() ?? '';

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Top row: status icon, filename, delete
            Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: processed
                        ? AppTheme.success.withOpacity(0.1)
                        : AppTheme.warning.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(
                    processed ? Icons.check_circle_outline : Icons.pending_outlined,
                    color: processed ? AppTheme.success : AppTheme.warning,
                    size: 18,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    document['filename'] ?? 'Unknown',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.text1(context),
                    ),
                  ),
                ),
                IconButton(
                  icon: Icon(Icons.delete_outline, size: 18, color: AppTheme.textH(context)),
                  onPressed: onDelete,
                  visualDensity: VisualDensity.compact,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                ),
              ],
            ),

            const SizedBox(height: 8),

            // Bottom row: category chip (tappable), chunk count, impact description
            Row(
              children: [
                // Tappable category chip
                GestureDetector(
                  onTap: onCategoryTap,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryDark.withOpacity(0.08),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: AppTheme.primaryDark.withOpacity(0.2)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          _labels[category] ?? category,
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.primaryDark,
                          ),
                        ),
                        const SizedBox(width: 4),
                        Icon(Icons.edit, size: 11, color: AppTheme.primaryDark.withOpacity(0.6)),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Text(
                  '$chunkCount chunks',
                  style: TextStyle(
                    fontSize: 11,
                    color: AppTheme.text2(context),
                  ),
                ),
              ],
            ),

            // Training impact description
            if (description.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                description,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 11,
                  color: AppTheme.textH(context),
                  fontStyle: FontStyle.italic,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
