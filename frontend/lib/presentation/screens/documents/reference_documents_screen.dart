import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import 'package:file_picker/file_picker.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Reference Documents Screen - Training Documents for AI/RAG
class ReferenceDocumentsScreen extends StatefulWidget {
  const ReferenceDocumentsScreen({super.key});

  @override
  State<ReferenceDocumentsScreen> createState() => _ReferenceDocumentsScreenState();
}

class _ReferenceDocumentsScreenState extends State<ReferenceDocumentsScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  List<Map<String, dynamic>> _documents = [];
  List<Map<String, dynamic>> _categories = [];
  bool _isLoading = true;
  String? _selectedCategory;
  bool _isUploading = false;

  final List<String> _categoryTabs = [
    'All',
    'Policy Wordings',
    'Guidelines',
    'Previous Contracts',
    'Market Data',
    'Regulatory',
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _categoryTabs.length, vsync: this);
    _tabController.addListener(_onTabChanged);
    _loadDocuments();
  }

  void _onTabChanged() {
    if (_tabController.indexIsChanging) return;
    final index = _tabController.index;
    setState(() {
      _selectedCategory = index == 0 ? null : _getCategoryKey(index);
    });
    _loadDocuments();
  }

  String _getCategoryKey(int index) {
    switch (index) {
      case 1: return 'policy_wording';
      case 2: return 'guidelines';
      case 3: return 'previous_contracts';
      case 4: return 'market_data';
      case 5: return 'regulatory';
      default: return '';
    }
  }

  Future<void> _loadDocuments() async {
    try {
      setState(() => _isLoading = true);

      String url = '/reference-documents/';
      if (_selectedCategory != null) {
        url += '?category=$_selectedCategory';
      }

      final response = await authService.get(url);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _documents = List<Map<String, dynamic>>.from(data['items'] ?? []);
      }

      // Load categories
      final catResponse = await authService.get('/reference-documents/categories');
      if (catResponse.statusCode == 200) {
        _categories = List<Map<String, dynamic>>.from(jsonDecode(catResponse.body));
      }

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

  Future<void> _uploadDocument() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf', 'doc', 'docx', 'txt'],
      );

      if (result == null) return;

      setState(() => _isUploading = true);

      // Show upload dialog
      final metadata = await _showUploadDialog(result.files.first.name);
      if (metadata == null) {
        setState(() => _isUploading = false);
        return;
      }

      // Upload file
      final filePath = result.files.first.path!;
      final uploadResponse = await authService.uploadFile(
        '/reference-documents/upload',
        filePath,
        'file',
        fields: metadata,
      );

      setState(() => _isUploading = false);

      if (uploadResponse.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Document uploaded successfully')),
        );
        _loadDocuments();
      } else {
        throw Exception('Upload failed');
      }
    } catch (e) {
      setState(() => _isUploading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Upload failed: $e')),
      );
    }
  }

  Future<Map<String, String>?> _showUploadDialog(String fileName) async {
    final titleController = TextEditingController(text: fileName.replaceAll(RegExp(r'\.[^.]+$'), ''));
    final descController = TextEditingController();
    final tagsController = TextEditingController();
    String selectedCategory = 'other';

    return showDialog<Map<String, String>>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Upload Reference Document'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: titleController,
                decoration: const InputDecoration(
                  labelText: 'Title',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: descController,
                decoration: const InputDecoration(
                  labelText: 'Description (optional)',
                  border: OutlineInputBorder(),
                ),
                maxLines: 2,
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                value: selectedCategory,
                decoration: const InputDecoration(
                  labelText: 'Category',
                  border: OutlineInputBorder(),
                ),
                items: const [
                  DropdownMenuItem(value: 'policy_wording', child: Text('Policy Wording')),
                  DropdownMenuItem(value: 'guidelines', child: Text('Guidelines')),
                  DropdownMenuItem(value: 'previous_contracts', child: Text('Previous Contracts')),
                  DropdownMenuItem(value: 'market_data', child: Text('Market Data')),
                  DropdownMenuItem(value: 'regulatory', child: Text('Regulatory')),
                  DropdownMenuItem(value: 'clauses', child: Text('Clauses')),
                  DropdownMenuItem(value: 'other', child: Text('Other')),
                ],
                onChanged: (value) => selectedCategory = value!,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: tagsController,
                decoration: const InputDecoration(
                  labelText: 'Tags (comma separated)',
                  border: OutlineInputBorder(),
                  hintText: 'e.g., cyber, property, marine',
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, {
              'title': titleController.text,
              'description': descController.text,
              'category': selectedCategory,
              'tags': tagsController.text,
            }),
            child: const Text('Upload'),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: AppTheme.surface,
        elevation: 0,
        title: const Text(
          'Reference Documents',
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: AppTheme.textPrimary,
            fontFamily: 'Inter',
          ),
        ),
        centerTitle: true,
        actions: [
          IconButton(
            onPressed: _loadDocuments,
            icon: const Icon(Icons.refresh),
            color: AppTheme.textSecondary,
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          indicatorColor: AppTheme.primaryDark,
          labelColor: AppTheme.primaryDark,
          unselectedLabelColor: AppTheme.textSecondary,
          tabs: _categoryTabs.map((t) => Tab(text: t)).toList(),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _documents.isEmpty
              ? _buildEmptyState()
              : _buildDocumentsList(),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _isUploading ? null : _uploadDocument,
        backgroundColor: AppTheme.primaryDark,
        icon: _isUploading
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              )
            : const Icon(Icons.upload_file, color: Colors.white),
        label: Text(
          _isUploading ? 'Uploading...' : 'Upload Document',
          style: const TextStyle(color: Colors.white),
        ),
      ),
    );
  }

  Widget _buildDocumentsList() {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _documents.length,
      itemBuilder: (context, index) => _buildDocumentCard(_documents[index]),
    );
  }

  Widget _buildDocumentCard(Map<String, dynamic> doc) {
    final status = doc['status'] as String? ?? 'pending';
    final category = doc['category'] as String? ?? 'other';

    Color statusColor;
    IconData statusIcon;
    switch (status) {
      case 'vectorized':
        statusColor = Colors.green;
        statusIcon = Icons.check_circle;
        break;
      case 'processing':
        statusColor = Colors.orange;
        statusIcon = Icons.sync;
        break;
      case 'failed':
        statusColor = Colors.red;
        statusIcon = Icons.error;
        break;
      default:
        statusColor = Colors.grey;
        statusIcon = Icons.hourglass_empty;
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: AppTheme.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                // Document Icon
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: AppTheme.primaryDark.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(
                    Icons.description_outlined,
                    color: AppTheme.primaryDark,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 12),

                // Title and status
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        doc['title'] as String? ?? 'Untitled',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                          fontFamily: 'Inter',
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Icon(statusIcon, size: 14, color: statusColor),
                          const SizedBox(width: 4),
                          Text(
                            status.toUpperCase(),
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: statusColor,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: AppTheme.border,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              category.replaceAll('_', ' ').toUpperCase(),
                              style: const TextStyle(
                                fontSize: 10,
                                color: AppTheme.textSecondary,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),

                // Delete button
                IconButton(
                  onPressed: () => _confirmDelete(doc),
                  icon: const Icon(Icons.delete_outline),
                  color: AppTheme.textHint,
                ),
              ],
            ),

            if (doc['description'] != null && (doc['description'] as String).isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(
                doc['description'] as String,
                style: const TextStyle(
                  fontSize: 13,
                  color: AppTheme.textSecondary,
                  height: 1.4,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],

            const SizedBox(height: 12),

            // Tags and info
            Row(
              children: [
                if (doc['chunk_count'] != null && (doc['chunk_count'] as int) > 0) ...[
                  Icon(Icons.layers_outlined, size: 14, color: AppTheme.textHint),
                  const SizedBox(width: 4),
                  Text(
                    '${doc['chunk_count']} chunks',
                    style: const TextStyle(fontSize: 12, color: AppTheme.textHint),
                  ),
                  const SizedBox(width: 16),
                ],
                Icon(Icons.insert_drive_file_outlined, size: 14, color: AppTheme.textHint),
                const SizedBox(width: 4),
                Text(
                  doc['file_name'] as String? ?? '',
                  style: const TextStyle(fontSize: 12, color: AppTheme.textHint),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),

            // Tags
            if (doc['tags'] != null && (doc['tags'] as List).isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: (doc['tags'] as List).map((tag) => Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryDark.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    tag.toString(),
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppTheme.primaryDark,
                    ),
                  ),
                )).toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _confirmDelete(Map<String, dynamic> doc) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Document?'),
        content: Text('Are you sure you want to delete "${doc['title']}"? This cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(context);
              try {
                final response = await authService.delete('/reference-documents/${doc['id']}');
                if (response.statusCode == 200) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Document deleted')),
                  );
                  _loadDocuments();
                }
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Delete failed: $e')),
                );
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.folder_open_outlined,
            size: 80,
            color: AppTheme.textHint.withOpacity(0.5),
          ),
          const SizedBox(height: 24),
          const Text(
            'No Reference Documents',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w600,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 48),
            child: Text(
              'Upload policy wordings, guidelines, and other documents to enhance InstantRisk Engine document generation.',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                color: AppTheme.textHint,
                height: 1.5,
              ),
            ),
          ),
          const SizedBox(height: 32),
          ElevatedButton.icon(
            onPressed: _uploadDocument,
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryDark,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            icon: const Icon(Icons.upload_file, color: Colors.white),
            label: const Text(
              'Upload First Document',
              style: TextStyle(color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }
}
