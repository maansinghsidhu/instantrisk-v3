import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Document Library Screen - 20GB Insurance Knowledge Base
/// Provides access to all insurance documents, clauses, training data with:
/// - Category browsing
/// - Search & filter
/// - Favorites
/// - AI chat integration
class TemplatesScreen extends ConsumerStatefulWidget {
  const TemplatesScreen({super.key});

  @override
  ConsumerState<TemplatesScreen> createState() => _TemplatesScreenState();
}

class _TemplatesScreenState extends ConsumerState<TemplatesScreen> {
  List<Map<String, dynamic>> _categories = [];
  Set<String> _favorites = {};
  bool _isLoading = true;
  String _searchQuery = '';
  String _selectedFilter = 'all'; // all, insurance, training, favorites

  // Stats
  int _totalDocuments = 0;
  double _totalSizeGb = 0;
  int _insuranceCount = 0;
  int _trainingCount = 0;

  @override
  void initState() {
    super.initState();
    _loadDocumentLibrary();
  }

  Future<void> _loadDocumentLibrary() async {
    setState(() => _isLoading = true);

    try {
      final response = await authService.get('/templates/library/categories');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _categories = List<Map<String, dynamic>>.from(data['categories'] ?? []);
          _totalDocuments = data['total_documents'] ?? 0;
          _totalSizeGb = (data['total_size_gb'] ?? 0).toDouble();
          _insuranceCount = data['insurance_categories'] ?? 0;
          _trainingCount = data['training_categories'] ?? 0;
          _isLoading = false;
        });
      } else {
        setState(() => _isLoading = false);
      }
    } catch (e) {
      setState(() => _isLoading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load document library: $e')),
        );
      }
    }
  }

  List<Map<String, dynamic>> get _filteredCategories {
    var cats = _categories;

    // Apply type filter
    if (_selectedFilter == 'insurance') {
      cats = cats.where((c) => c['type'] == 'insurance').toList();
    } else if (_selectedFilter == 'training') {
      cats = cats.where((c) => c['type'] == 'training').toList();
    } else if (_selectedFilter == 'favorites') {
      cats = cats.where((c) => _favorites.contains(c['id'])).toList();
    }

    // Apply search
    if (_searchQuery.isNotEmpty) {
      final query = _searchQuery.toLowerCase();
      cats = cats.where((c) =>
        (c['name']?.toString().toLowerCase().contains(query) ?? false) ||
        (c['description']?.toString().toLowerCase().contains(query) ?? false) ||
        (c['id']?.toString().toLowerCase().contains(query) ?? false)
      ).toList();
    }

    return cats;
  }

  void _toggleFavorite(String categoryId) {
    setState(() {
      if (_favorites.contains(categoryId)) {
        _favorites.remove(categoryId);
      } else {
        _favorites.add(categoryId);
      }
    });
  }

  IconData _getIconForCategory(String iconName) {
    final iconMap = {
      'pricing': Icons.attach_money,
      'automobile': Icons.directions_car,
      'disaster': Icons.warning_amber,
      'legal_document': Icons.description,
      'clause': Icons.format_quote,
      'contract': Icons.handshake,
      'security': Icons.security,
      'world': Icons.public,
      'medical': Icons.local_hospital,
      'gavel': Icons.gavel,
      'lloyds': Icons.account_balance,
      'verified': Icons.verified,
      'database': Icons.storage,
      'policy': Icons.policy,
      'calculator': Icons.calculate,
      'legal': Icons.balance,
      'aus': Icons.flag,
      'judge': Icons.account_balance_wallet,
      'chat': Icons.chat,
      'inference': Icons.psychology,
      'contracts': Icons.folder_open,
      'europe': Icons.euro,
      'benchmark': Icons.speed,
      'eu': Icons.stars,
      'document': Icons.article,
      'qa': Icons.question_answer,
      'ledgar': Icons.library_books,
      'test': Icons.quiz,
      'contract_alt': Icons.receipt_long,
      'merger': Icons.merge_type,
    };
    return iconMap[iconName] ?? Icons.folder;
  }

  Color _getColorForType(String type) {
    return type == 'insurance'
        ? const Color(0xFF2563EB) // Blue for insurance
        : const Color(0xFF7C3AED); // Purple for training
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      body: CustomScrollView(
        slivers: [
          // App Bar
          SliverAppBar(
            backgroundColor: AppTheme.surfaceOf(context),
            elevation: 0,
            pinned: true,
            expandedHeight: 200,
            flexibleSpace: FlexibleSpaceBar(
              background: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      const Color(0xFF1E3A5F),
                      const Color(0xFF2563EB),
                    ],
                  ),
                ),
                child: SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SizedBox(height: 40),
                        const Text(
                          'Document Library',
                          style: TextStyle(
                            fontSize: 28,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                            fontFamily: 'Inter',
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Insurance Knowledge Base',
                          style: TextStyle(
                            fontSize: 16,
                            color: Colors.white.withOpacity(0.8),
                          ),
                        ),
                        const Spacer(),
                        // Stats Row
                        Row(
                          children: [
                            _buildStatBadge(
                              Icons.description,
                              '${_formatNumber(_totalDocuments)}',
                              'Documents',
                            ),
                            const SizedBox(width: 16),
                            _buildStatBadge(
                              Icons.storage,
                              '${_totalSizeGb.toStringAsFixed(1)}GB',
                              'Data',
                            ),
                            const SizedBox(width: 16),
                            _buildStatBadge(
                              Icons.category,
                              '${_insuranceCount + _trainingCount}',
                              'Categories',
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),

          // Search Bar
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: TextField(
                onChanged: (value) => setState(() => _searchQuery = value),
                decoration: InputDecoration(
                  hintText: 'Search documents, clauses, policies...',
                  prefixIcon: Icon(Icons.search),
                  suffixIcon: _searchQuery.isNotEmpty
                      ? IconButton(
                          icon: Icon(Icons.clear),
                          onPressed: () => setState(() => _searchQuery = ''),
                        )
                      : null,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: AppTheme.borderOf(context)),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: AppTheme.borderOf(context)),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: Color(0xFF2563EB), width: 2),
                  ),
                  filled: true,
                  fillColor: AppTheme.surfaceOf(context),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                ),
              ),
            ),
          ),

          // Filter Chips
          SliverToBoxAdapter(
            child: Container(
              height: 50,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: ListView(
                scrollDirection: Axis.horizontal,
                children: [
                  _buildFilterChip('all', 'All', Icons.apps),
                  const SizedBox(width: 8),
                  _buildFilterChip('insurance', 'Insurance', Icons.shield),
                  const SizedBox(width: 8),
                  _buildFilterChip('training', 'Training', Icons.model_training),
                  const SizedBox(width: 8),
                  _buildFilterChip('favorites', 'Favorites', Icons.star),
                ],
              ),
            ),
          ),

          const SliverToBoxAdapter(child: SizedBox(height: 8)),

          // Categories Grid
          _isLoading
              ? const SliverFillRemaining(
                  child: Center(child: CircularProgressIndicator()),
                )
              : _filteredCategories.isEmpty
                  ? SliverFillRemaining(
                      child: _buildEmptyState(),
                    )
                  : SliverPadding(
                      padding: const EdgeInsets.all(16),
                      sliver: SliverLayoutBuilder(
                        builder: (context, constraints) {
                          final width = constraints.crossAxisExtent;
                          int crossAxisCount;
                          double childAspectRatio;

                          if (width > 1200) {
                            crossAxisCount = 5;
                            childAspectRatio = 1.0;
                          } else if (width > 900) {
                            crossAxisCount = 4;
                            childAspectRatio = 0.95;
                          } else if (width > 600) {
                            crossAxisCount = 3;
                            childAspectRatio = 0.9;
                          } else {
                            crossAxisCount = 2;
                            childAspectRatio = 0.85;
                          }

                          return SliverGrid(
                            gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                              crossAxisCount: crossAxisCount,
                              mainAxisSpacing: 12,
                              crossAxisSpacing: 12,
                              childAspectRatio: childAspectRatio,
                            ),
                            delegate: SliverChildBuilderDelegate(
                              (context, index) => _buildCategoryCard(_filteredCategories[index]),
                              childCount: _filteredCategories.length,
                            ),
                          );
                        },
                      ),
                    ),
        ],
      ),
    );
  }

  Widget _buildStatBadge(IconData icon, String value, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.15),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: Colors.white, size: 18),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                value,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                ),
              ),
              Text(
                label,
                style: TextStyle(
                  fontSize: 10,
                  color: Colors.white.withOpacity(0.7),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String filter, String label, IconData icon) {
    final isSelected = _selectedFilter == filter;
    return FilterChip(
      label: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            icon,
            size: 16,
            color: isSelected ? Colors.white : AppTheme.text2(context),
          ),
          SizedBox(width: 6),
          Text(label),
        ],
      ),
      selected: isSelected,
      onSelected: (selected) {
        setState(() => _selectedFilter = filter);
      },
      backgroundColor: AppTheme.surfaceOf(context),
      selectedColor: const Color(0xFF2563EB),
      labelStyle: TextStyle(
        color: isSelected ? Colors.white : AppTheme.text2(context),
        fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
      ),
      side: BorderSide(
        color: isSelected ? Color(0xFF2563EB) : AppTheme.borderOf(context),
      ),
      showCheckmark: false,
    );
  }

  Widget _buildCategoryCard(Map<String, dynamic> category) {
    final categoryId = category['id']?.toString() ?? '';
    final isFavorite = _favorites.contains(categoryId);
    final type = category['type']?.toString() ?? 'insurance';
    final color = _getColorForType(type);
    final docCount = category['document_count'] ?? 0;
    final sizeMb = (category['size_mb'] ?? 0).toDouble();

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: AppTheme.borderOf(context)),
      ),
      child: InkWell(
        onTap: () => _showCategoryDetails(category),
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  // Icon
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      _getIconForCategory(category['icon']?.toString() ?? ''),
                      color: color,
                      size: 24,
                    ),
                  ),
                  const Spacer(),
                  // Favorite button
                  IconButton(
                    onPressed: () => _toggleFavorite(categoryId),
                    icon: Icon(
                      isFavorite ? Icons.star : Icons.star_border,
                      color: isFavorite ? Colors.amber : AppTheme.textH(context),
                      size: 22,
                    ),
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              // Name
              Text(
                category['name']?.toString() ?? 'Unknown',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.text1(context),
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 4),
              // Description
              Expanded(
                child: Text(
                  category['description']?.toString() ?? '',
                  style: TextStyle(
                    fontSize: 12,
                    color: AppTheme.text2(context),
                    height: 1.3,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(height: 8),
              // Stats row
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      type == 'insurance' ? 'Insurance' : 'Training',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                        color: color,
                      ),
                    ),
                  ),
                  const Spacer(),
                  Text(
                    '${_formatNumber(docCount)} docs',
                    style: TextStyle(
                      fontSize: 11,
                      color: AppTheme.text2(context),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              // Size indicator
              Row(
                children: [
                  Expanded(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(2),
                      child: LinearProgressIndicator(
                        value: (sizeMb / 1000).clamp(0.0, 1.0),
                        backgroundColor: AppTheme.borderOf(context),
                        valueColor: AlwaysStoppedAnimation<Color>(color.withOpacity(0.6)),
                        minHeight: 3,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    sizeMb >= 1000
                        ? '${(sizeMb / 1024).toStringAsFixed(1)}GB'
                        : '${sizeMb.toStringAsFixed(0)}MB',
                    style: TextStyle(
                      fontSize: 10,
                      color: AppTheme.textH(context),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showCategoryDetails(Map<String, dynamic> category) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => _CategoryDetailSheet(
        category: category,
        onAskAI: () {
          Navigator.pop(context);
          // Navigate to chat with context
          context.go('/home/chat', extra: {
            'initialMessage': 'Tell me about ${category['name']} documents and how they are used in insurance.',
          });
        },
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            _selectedFilter == 'favorites' ? Icons.star_border : Icons.search_off,
            size: 64,
            color: AppTheme.textH(context),
          ),
          const SizedBox(height: 16),
          Text(
            _selectedFilter == 'favorites'
                ? 'No favorites yet'
                : 'No documents found',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: AppTheme.text2(context),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            _selectedFilter == 'favorites'
                ? 'Tap the star icon on any category to add it to favorites'
                : 'Try adjusting your search or filter',
            style: TextStyle(
              fontSize: 14,
              color: AppTheme.textH(context),
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  String _formatNumber(int num) {
    if (num >= 1000000) {
      return '${(num / 1000000).toStringAsFixed(1)}M';
    } else if (num >= 1000) {
      return '${(num / 1000).toStringAsFixed(1)}K';
    }
    return num.toString();
  }
}


/// Category Detail Bottom Sheet
class _CategoryDetailSheet extends StatefulWidget {
  final Map<String, dynamic> category;
  final VoidCallback onAskAI;

  const _CategoryDetailSheet({
    required this.category,
    required this.onAskAI,
  });

  @override
  State<_CategoryDetailSheet> createState() => _CategoryDetailSheetState();
}

class _CategoryDetailSheetState extends State<_CategoryDetailSheet> {
  List<Map<String, dynamic>> _documents = [];
  bool _isLoading = true;
  String _searchQuery = '';
  int _totalDocs = 0;

  @override
  void initState() {
    super.initState();
    _loadDocuments();
  }

  Future<void> _loadDocuments() async {
    setState(() => _isLoading = true);

    try {
      final categoryId = widget.category['id'];
      final response = await authService.get('/templates/library/category/$categoryId?limit=100');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _documents = List<Map<String, dynamic>>.from(data['documents'] ?? []);
          _totalDocs = data['total'] ?? 0;
          _isLoading = false;
        });
      } else {
        setState(() => _isLoading = false);
      }
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  List<Map<String, dynamic>> get _filteredDocuments {
    if (_searchQuery.isEmpty) return _documents;
    final query = _searchQuery.toLowerCase();
    return _documents.where((d) =>
      d['name']?.toString().toLowerCase().contains(query) ?? false
    ).toList();
  }

  IconData _getFileIcon(String extension) {
    switch (extension.toLowerCase()) {
      case '.json':
      case '.jsonl':
        return Icons.data_object;
      case '.csv':
        return Icons.table_chart;
      case '.txt':
        return Icons.text_snippet;
      case '.md':
        return Icons.article;
      case '.pdf':
        return Icons.picture_as_pdf;
      default:
        return Icons.insert_drive_file;
    }
  }

  @override
  Widget build(BuildContext context) {
    final type = widget.category['type']?.toString() ?? 'insurance';
    final color = type == 'insurance'
        ? const Color(0xFF2563EB)
        : const Color(0xFF7C3AED);

    return Container(
      height: MediaQuery.of(context).size.height * 0.85,
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        children: [
          // Handle
          Container(
            margin: const EdgeInsets.symmetric(vertical: 12),
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: AppTheme.borderOf(context),
              borderRadius: BorderRadius.circular(2),
            ),
          ),

          // Header
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(
              children: [
                Container(
                  width: 50,
                  height: 50,
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(Icons.folder, color: color, size: 28),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        widget.category['name']?.toString() ?? 'Category',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.text1(context),
                        ),
                      ),
                      Text(
                        '$_totalDocs documents',
                        style: TextStyle(
                          fontSize: 14,
                          color: AppTheme.text2(context),
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
          ),

          const SizedBox(height: 12),

          // Description
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Text(
              widget.category['description']?.toString() ?? '',
              style: TextStyle(
                fontSize: 14,
                color: AppTheme.text2(context),
                height: 1.4,
              ),
            ),
          ),

          const SizedBox(height: 16),

          // Ask AI Button
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: widget.onAskAI,
                icon: const Icon(Icons.auto_awesome, size: 20),
                label: const Text('Ask AI About This Category'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: color,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
            ),
          ),

          const SizedBox(height: 16),
          const Divider(height: 1),

          // Search
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              onChanged: (value) => setState(() => _searchQuery = value),
              decoration: InputDecoration(
                hintText: 'Search in this category...',
                prefixIcon: const Icon(Icons.search, size: 20),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: BorderSide(color: AppTheme.borderOf(context)),
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                isDense: true,
              ),
            ),
          ),

          // Documents List
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _filteredDocuments.isEmpty
                    ? Center(
                        child: Text(
                          _searchQuery.isNotEmpty
                              ? 'No documents match your search'
                              : 'No documents in this category',
                          style: TextStyle(color: AppTheme.text2(context)),
                        ),
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        itemCount: _filteredDocuments.length,
                        itemBuilder: (context, index) {
                          final doc = _filteredDocuments[index];
                          return _buildDocumentItem(doc);
                        },
                      ),
          ),
        ],
      ),
    );
  }

  Widget _buildDocumentItem(Map<String, dynamic> doc) {
    final extension = doc['extension']?.toString() ?? '';
    final sizeKb = (doc['size_kb'] ?? 0).toDouble();

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(color: AppTheme.borderOf(context)),
      ),
      child: ListTile(
        leading: Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: AppTheme.bg(context),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(
            _getFileIcon(extension),
            color: AppTheme.text2(context),
            size: 22,
          ),
        ),
        title: Text(
          doc['name']?.toString() ?? 'Unknown',
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(
          sizeKb >= 1024
              ? '${(sizeKb / 1024).toStringAsFixed(1)} MB'
              : '${sizeKb.toStringAsFixed(0)} KB',
          style: const TextStyle(fontSize: 12),
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              icon: const Icon(Icons.visibility, size: 20),
              onPressed: () => _previewDocument(doc),
              tooltip: 'Preview',
            ),
            IconButton(
              icon: const Icon(Icons.copy, size: 20),
              onPressed: () => _copyDocumentPath(doc),
              tooltip: 'Copy path',
            ),
          ],
        ),
        onTap: () => _previewDocument(doc),
      ),
    );
  }

  Future<void> _previewDocument(Map<String, dynamic> doc) async {
    final path = doc['path']?.toString() ?? '';

    try {
      final response = await authService.get('/templates/library/document?path=${Uri.encodeComponent(path)}&preview=true');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (mounted) {
          showDialog(
            context: context,
            builder: (context) => _DocumentPreviewDialog(
              name: doc['name']?.toString() ?? 'Document',
              content: data['content']?.toString() ?? 'No content',
              isPreview: data['is_preview'] ?? true,
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error loading document: $e')),
        );
      }
    }
  }

  void _copyDocumentPath(Map<String, dynamic> doc) {
    final path = doc['path']?.toString() ?? '';
    Clipboard.setData(ClipboardData(text: path));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Path copied to clipboard'),
        duration: Duration(seconds: 2),
      ),
    );
  }
}


/// Document Preview Dialog
class _DocumentPreviewDialog extends StatelessWidget {
  final String name;
  final String content;
  final bool isPreview;

  const _DocumentPreviewDialog({
    required this.name,
    required this.content,
    required this.isPreview,
  });

  @override
  Widget build(BuildContext context) {
    return Dialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Container(
        width: MediaQuery.of(context).size.width * 0.9,
        height: MediaQuery.of(context).size.height * 0.7,
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    name,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (isPreview)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.orange.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Text(
                      'Preview',
                      style: TextStyle(
                        fontSize: 11,
                        color: Colors.orange,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                const SizedBox(width: 8),
                IconButton(
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
            const Divider(),
            Expanded(
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Color(0xFFF8FAFC),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppTheme.borderOf(context)),
                ),
                child: SingleChildScrollView(
                  child: SelectableText(
                    content,
                    style: const TextStyle(
                      fontSize: 12,
                      fontFamily: 'Courier',
                      height: 1.5,
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton.icon(
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: content));
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Content copied')),
                    );
                  },
                  icon: const Icon(Icons.copy, size: 18),
                  label: const Text('Copy'),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: () => Navigator.pop(context),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF2563EB),
                  ),
                  child: const Text('Close', style: TextStyle(color: Colors.white)),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
