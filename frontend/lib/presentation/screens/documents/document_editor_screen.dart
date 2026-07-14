import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Document Editor Screen
/// Section-based editing with LMA clause integration
class DocumentEditorScreen extends StatefulWidget {
  final String documentId;
  final String? assessmentId;

  const DocumentEditorScreen({
    super.key,
    required this.documentId,
    this.assessmentId,
  });

  @override
  State<DocumentEditorScreen> createState() => _DocumentEditorScreenState();
}

class _DocumentEditorScreenState extends State<DocumentEditorScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  late TextEditingController _contentController;
  bool _isLoading = true;
  bool _isSaving = false;
  bool _hasChanges = false;
  bool _isPreviewMode = false;
  String? _error;

  Map<String, dynamic> _document = {};
  List<Map<String, dynamic>> _sections = [];
  List<Map<String, dynamic>> _versions = [];
  int _selectedSectionIndex = 0;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _contentController = TextEditingController();
    _contentController.addListener(_onContentChanged);
    _loadDocument();
  }

  void _onContentChanged() {
    if (!_hasChanges) {
      setState(() => _hasChanges = true);
    }
  }

  Future<void> _loadDocument() async {
    try {
      setState(() {
        _isLoading = true;
        _error = null;
      });

      // Try generated-documents endpoint first, fall back to documents
      var response = await authService.get('/generated-documents/${widget.documentId}');

      if (response.statusCode == 404) {
        // Fall back to regular documents endpoint
        response = await authService.get('/documents/${widget.documentId}');
      }

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _document = data;
          // Handle generated documents which have sections in draft_content or final_content
          final draftContent = data['draft_content'] as Map<String, dynamic>?;
          final finalContent = data['final_content'] as Map<String, dynamic>?;
          final contentToUse = finalContent?.isNotEmpty == true ? finalContent : draftContent;

          if (contentToUse != null && contentToUse['sections'] != null) {
            // Generated document with sections
            _sections = List<Map<String, dynamic>>.from(contentToUse['sections'] ?? []);
          } else if (data['content'] != null) {
            // Regular document with content string
            _sections = _parseSections(data['content'] ?? '');
          } else {
            _sections = [];
          }

          _versions = List<Map<String, dynamic>>.from(data['versions'] ?? []);
          if (_sections.isNotEmpty) {
            _contentController.text = _sections[0]['content'] ?? '';
          }
        });
      }

      setState(() => _isLoading = false);
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  List<Map<String, dynamic>> _parseSections(String content) {
    // Parse document content into sections
    final sections = <Map<String, dynamic>>[];
    final lines = content.split('\n');
    String currentSection = 'General';
    String currentContent = '';

    for (final line in lines) {
      // Look for section headers (e.g., ## Section Name)
      if (line.startsWith('## ') || line.startsWith('# ')) {
        if (currentContent.isNotEmpty) {
          sections.add({
            'title': currentSection,
            'content': currentContent.trim(),
          });
        }
        currentSection = line.replaceAll(RegExp(r'^#+\s*'), '');
        currentContent = '';
      } else {
        currentContent += '$line\n';
      }
    }

    // Add the last section
    if (currentContent.isNotEmpty || sections.isEmpty) {
      sections.add({
        'title': currentSection,
        'content': currentContent.trim(),
      });
    }

    return sections;
  }

  Future<void> _saveDocument({bool finalize = false}) async {
    if (!_hasChanges && !finalize) return;

    setState(() => _isSaving = true);

    try {
      // Update current section content
      if (_selectedSectionIndex < _sections.length) {
        _sections[_selectedSectionIndex]['content'] = _contentController.text;
      }

      // Rebuild full content
      final fullContent = _sections.map((s) {
        return '## ${s['title']}\n\n${s['content']}';
      }).join('\n\n');

      final response = await authService.put(
        '/documents/${widget.documentId}',
        body: {
          'content': fullContent,
          'status': finalize ? 'finalized' : 'draft',
        },
      );

      if (response.statusCode == 200) {
        setState(() => _hasChanges = false);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(finalize ? 'Document finalized' : 'Draft saved'),
              backgroundColor: const Color(0xFF059669),
            ),
          );
          if (finalize) {
            context.pop();
          }
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error saving: $e')),
        );
      }
    } finally {
      setState(() => _isSaving = false);
    }
  }

  void _selectSection(int index) {
    // Save current section content first
    if (_selectedSectionIndex < _sections.length) {
      _sections[_selectedSectionIndex]['content'] = _contentController.text;
    }

    setState(() {
      _selectedSectionIndex = index;
      _contentController.text = _sections[index]['content'] ?? '';
    });
  }

  void _addSection() {
    showDialog(
      context: context,
      builder: (context) {
        final controller = TextEditingController();
        return AlertDialog(
          title: const Text('Add Section'),
          content: TextField(
            controller: controller,
            decoration: const InputDecoration(
              labelText: 'Section Title',
              hintText: 'e.g., Special Conditions',
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () {
                if (controller.text.isNotEmpty) {
                  setState(() {
                    _sections.add({
                      'title': controller.text,
                      'content': '',
                    });
                    _hasChanges = true;
                  });
                  Navigator.pop(context);
                }
              },
              child: const Text('Add'),
            ),
          ],
        );
      },
    );
  }

  @override
  void dispose() {
    _tabController.dispose();
    _contentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return WillPopScope(
      onWillPop: () async {
        if (_hasChanges) {
          final result = await _showUnsavedChangesDialog();
          return result ?? false;
        }
        return true;
      },
      child: Scaffold(
        backgroundColor: AppTheme.background,
        appBar: AppBar(
          backgroundColor: AppTheme.surface,
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back, color: AppTheme.textPrimary),
            onPressed: () async {
              if (_hasChanges) {
                final result = await _showUnsavedChangesDialog();
                if (result == true && mounted) context.pop();
              } else {
                context.pop();
              }
            },
          ),
          title: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _document['name'] ?? 'Document Editor',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                ),
              ),
              if (_hasChanges)
                const Text(
                  'Unsaved changes',
                  style: TextStyle(
                    fontSize: 11,
                    color: Color(0xFFF59E0B),
                  ),
                ),
            ],
          ),
          actions: [
            // Preview toggle
            IconButton(
              icon: Icon(
                _isPreviewMode ? Icons.edit : Icons.visibility,
                color: AppTheme.textSecondary,
              ),
              onPressed: () => setState(() => _isPreviewMode = !_isPreviewMode),
              tooltip: _isPreviewMode ? 'Edit' : 'Preview',
            ),
            // Save button
            if (_hasChanges)
              TextButton(
                onPressed: _isSaving ? null : () => _saveDocument(),
                child: _isSaving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Save Draft'),
              ),
          ],
          bottom: TabBar(
            controller: _tabController,
            labelColor: AppTheme.primaryDark,
            unselectedLabelColor: AppTheme.textSecondary,
            indicatorColor: AppTheme.primaryDark,
            tabs: const [
              Tab(text: 'Content'),
              Tab(text: 'Clauses'),
              Tab(text: 'History'),
            ],
          ),
        ),
        body: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? _buildErrorState()
                : TabBarView(
                    controller: _tabController,
                    children: [
                      _buildContentTab(),
                      _buildClausesTab(),
                      _buildHistoryTab(),
                    ],
                  ),
        bottomNavigationBar: _buildBottomBar(),
      ),
    );
  }

  Widget _buildContentTab() {
    return Row(
      children: [
        // Sections sidebar
        Container(
          width: 200,
          decoration: BoxDecoration(
            color: AppTheme.surface,
            border: Border(right: BorderSide(color: AppTheme.border)),
          ),
          child: Column(
            children: [
              // Sections header
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  border: Border(bottom: BorderSide(color: AppTheme.border)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.list, size: 18, color: AppTheme.textSecondary),
                    const SizedBox(width: 8),
                    const Text(
                      'Sections',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const Spacer(),
                    IconButton(
                      icon: const Icon(Icons.add, size: 18),
                      onPressed: _addSection,
                      tooltip: 'Add Section',
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                  ],
                ),
              ),
              // Sections list
              Expanded(
                child: ListView.builder(
                  itemCount: _sections.length,
                  itemBuilder: (context, index) {
                    final section = _sections[index];
                    final isSelected = _selectedSectionIndex == index;
                    return ListTile(
                      dense: true,
                      selected: isSelected,
                      selectedTileColor: AppTheme.primaryDark.withOpacity(0.1),
                      leading: Icon(
                        Icons.article_outlined,
                        size: 18,
                        color: isSelected ? AppTheme.primaryDark : AppTheme.textSecondary,
                      ),
                      title: Text(
                        section['title'] ?? 'Section ${index + 1}',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                          color: isSelected ? AppTheme.primaryDark : AppTheme.textPrimary,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      onTap: () => _selectSection(index),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
        // Editor area
        Expanded(
          child: _isPreviewMode ? _buildPreview() : _buildEditor(),
        ),
      ],
    );
  }

  Widget _buildEditor() {
    return Container(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section title
          if (_selectedSectionIndex < _sections.length) ...[
            Text(
              _sections[_selectedSectionIndex]['title'] ?? 'Section',
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 16),
          ],
          // Text editor
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: const Color(0xFFFFFFF8),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.border),
              ),
              child: TextField(
                controller: _contentController,
                maxLines: null,
                expands: true,
                style: const TextStyle(
                  fontSize: 14,
                  fontFamily: 'Courier',
                  height: 1.6,
                  color: Color(0xFF1F2937),
                ),
                decoration: const InputDecoration(
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.all(16),
                  hintText: 'Start typing...',
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPreview() {
    // Combine all sections for preview
    final fullContent = _sections.map((s) {
      return '## ${s['title']}\n\n${s['content']}';
    }).join('\n\n');

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(8),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.05),
              blurRadius: 10,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: SelectableText(
          fullContent,
          style: const TextStyle(
            fontSize: 13,
            height: 1.6,
            color: Color(0xFF1F2937),
          ),
        ),
      ),
    );
  }

  Widget _buildClausesTab() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.article_outlined,
            size: 64,
            color: AppTheme.textHint,
          ),
          const SizedBox(height: 16),
          const Text(
            'LMA Clause Library',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 48),
            child: Text(
              'Browse and insert LMA clauses directly into your document',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                color: AppTheme.textHint,
              ),
            ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: () {
              // Navigate to templates screen
              context.go('/templates');
            },
            icon: const Icon(Icons.library_books),
            label: const Text('Browse LMA Clauses'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryDark,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHistoryTab() {
    if (_versions.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.history,
              size: 64,
              color: AppTheme.textHint,
            ),
            const SizedBox(height: 16),
            const Text(
              'No version history yet',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Versions are created when you save the document',
              style: TextStyle(
                fontSize: 14,
                color: AppTheme.textHint,
              ),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _versions.length,
      itemBuilder: (context, index) {
        final version = _versions[index];
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: AppTheme.primaryDark.withOpacity(0.1),
              child: Text(
                'v${_versions.length - index}',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.primaryDark,
                ),
              ),
            ),
            title: Text(
              version['created_at'] ?? 'Unknown date',
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
            subtitle: Text(
              version['note'] ?? 'Auto-saved',
              style: const TextStyle(fontSize: 12),
            ),
            trailing: TextButton(
              onPressed: () {
                // Restore this version
              },
              child: const Text('Restore'),
            ),
          ),
        );
      },
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.error_outline, size: 64, color: Colors.red),
          const SizedBox(height: 16),
          Text(
            _error ?? 'Error loading document',
            style: const TextStyle(color: Colors.red),
          ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: _loadDocument,
            child: const Text('Retry'),
          ),
        ],
      ),
    );
  }

  Widget _buildBottomBar() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        border: Border(top: BorderSide(color: AppTheme.border)),
      ),
      child: SafeArea(
        child: Row(
          children: [
            // Status indicator
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: (_document['status'] == 'finalized')
                    ? const Color(0xFF059669).withOpacity(0.1)
                    : const Color(0xFFF59E0B).withOpacity(0.1),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    (_document['status'] == 'finalized')
                        ? Icons.check_circle
                        : Icons.edit_note,
                    size: 16,
                    color: (_document['status'] == 'finalized')
                        ? const Color(0xFF059669)
                        : const Color(0xFFF59E0B),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    (_document['status'] == 'finalized') ? 'Finalized' : 'Draft',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: (_document['status'] == 'finalized')
                          ? const Color(0xFF059669)
                          : const Color(0xFFF59E0B),
                    ),
                  ),
                ],
              ),
            ),
            const Spacer(),
            // Finalize button
            if (_document['status'] != 'finalized')
              ElevatedButton.icon(
                onPressed: _isSaving ? null : () => _saveDocument(finalize: true),
                icon: const Icon(Icons.check, size: 18),
                label: const Text('Finalize'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF059669),
                  foregroundColor: Colors.white,
                ),
              ),
          ],
        ),
      ),
    );
  }

  Future<bool?> _showUnsavedChangesDialog() {
    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Unsaved Changes'),
        content: const Text('You have unsaved changes. What would you like to do?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Discard'),
          ),
          TextButton(
            onPressed: () async {
              await _saveDocument();
              if (mounted) Navigator.pop(context, true);
            },
            child: const Text('Save & Exit'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Continue Editing'),
          ),
        ],
      ),
    );
  }
}
