import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'dart:convert';
import 'package:file_picker/file_picker.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../widgets/common/screen_header.dart';

/// Training Screen - Upload documents to improve AI analysis
/// Users can upload insurance documents, loss runs, policies to train the AI
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
    {'id': 'all', 'name': 'All Documents', 'icon': Icons.folder},
    {'id': 'policy', 'name': 'Insurance Policies', 'icon': Icons.policy},
    {'id': 'loss_run', 'name': 'Loss Runs', 'icon': Icons.assessment},
    {'id': 'claims', 'name': 'Claims Data', 'icon': Icons.report_problem},
    {'id': 'underwriting', 'name': 'Underwriting Guidelines', 'icon': Icons.rule},
    {'id': 'regulatory', 'name': 'Regulatory Documents', 'icon': Icons.gavel},
    {'id': 'market', 'name': 'Market Data', 'icon': Icons.trending_up},
    {'id': 'slip_template', 'name': 'Slip Templates', 'icon': Icons.receipt_long},
    {'id': 'endorsement', 'name': 'Endorsements', 'icon': Icons.post_add},
    {'id': 'clause_library', 'name': 'Clause Libraries', 'icon': Icons.library_books},
  ];

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
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('${file.name} uploaded successfully'),
              backgroundColor: AppTheme.success,
            ),
          );
        }
      }

      await _loadTrainingDocuments();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Upload failed: $e'),
          backgroundColor: AppTheme.error,
        ),
      );
    } finally {
      setState(() => _isUploading = false);
    }
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      body: Column(
        children: [
          ScreenHeader(
            title: 'AI Training',
            subtitle: 'Upload documents to improve AI',
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
          // Header with stats
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [AppTheme.primaryDark, AppTheme.primaryLight],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
            child: Column(
              children: [
                Row(
                  children: [
                    const Icon(Icons.model_training, color: Colors.white, size: 32),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Train Your AI',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 24,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          Text(
                            'Your docs are used by AI in document generation',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.8),
                              fontSize: 14,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _StatCard(
                      icon: Icons.description,
                      value: '${_uploadedDocuments.length}',
                      label: 'Documents',
                    ),
                    _StatCard(
                      icon: Icons.category,
                      value: '${_categories.length - 1}',
                      label: 'Categories',
                    ),
                    _StatCard(
                      icon: Icons.check_circle,
                      value: '${_uploadedDocuments.where((d) => d['processed'] == true).length}',
                      label: 'Processed',
                    ),
                  ],
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
                hintText: 'Search training documents...',
                prefixIcon: const Icon(Icons.search, size: 20),
                suffixIcon: _searchQuery.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, size: 18),
                        onPressed: () {
                          _searchController.clear();
                          setState(() => _searchQuery = '');
                        },
                      )
                    : null,
                filled: true,
                fillColor: AppTheme.surface,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide(color: AppTheme.borderOf(context)),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide(color: AppTheme.borderOf(context)),
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                isDense: true,
              ),
            ),
          ),

          // Category filter
          Container(
            height: 50,
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: _categories.length,
              itemBuilder: (ctx, index) {
                final cat = _categories[index];
                final isSelected = _selectedCategory == cat['id'];
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
                  child: FilterChip(
                    label: Text(cat['name']),
                    selected: isSelected,
                    onSelected: (_) => setState(() => _selectedCategory = cat['id']),
                    avatar: Icon(cat['icon'], size: 18),
                    selectedColor: AppTheme.primaryDark.withOpacity(0.2),
                  ),
                );
              },
            ),
          ),

          const Divider(height: 1),

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
                          );
                        },
                      ),
          ),
        ],
      ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _isUploading ? null : _uploadDocument,
        icon: _isUploading
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              )
            : const Icon(Icons.upload_file),
        label: Text(_isUploading ? 'Uploading...' : 'Upload Documents'),
        backgroundColor: AppTheme.primaryDark,
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final IconData icon;
  final String value;
  final String label;

  const _StatCard({
    required this.icon,
    required this.value,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Icon(icon, color: Colors.white, size: 24),
        const SizedBox(height: 4),
        Text(
          value,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 24,
            fontWeight: FontWeight.bold,
          ),
        ),
        Text(
          label,
          style: TextStyle(
            color: Colors.white.withOpacity(0.8),
            fontSize: 12,
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
            size: 80,
            color: AppTheme.textH(context),
          ),
          const SizedBox(height: 16),
          Text(
            'No Training Documents Yet',
            style: TextStyle(
              fontSize: 20,
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

class _DocumentCard extends StatelessWidget {
  final Map<String, dynamic> document;
  final VoidCallback onDelete;

  const _DocumentCard({
    required this.document,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final processed = document['processed'] == true;
    final category = document['category'] ?? 'policy';

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: processed
              ? AppTheme.success.withOpacity(0.1)
              : AppTheme.warning.withOpacity(0.1),
          child: Icon(
            processed ? Icons.check_circle : Icons.pending,
            color: processed ? AppTheme.success : AppTheme.warning,
          ),
        ),
        title: Text(
          document['filename'] ?? 'Unknown',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Row(
          children: [
            Chip(
              label: Text(category),
              labelStyle: const TextStyle(fontSize: 10),
              padding: EdgeInsets.zero,
              visualDensity: VisualDensity.compact,
            ),
            const SizedBox(width: 8),
            Text(
              processed ? 'Processed' : 'Processing...',
              style: TextStyle(
                fontSize: 12,
                color: processed ? AppTheme.success : AppTheme.warning,
              ),
            ),
          ],
        ),
        trailing: IconButton(
          icon: const Icon(Icons.delete_outline),
          onPressed: onDelete,
          color: AppTheme.error,
        ),
      ),
    );
  }
}
