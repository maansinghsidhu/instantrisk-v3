import 'package:flutter/material.dart';
import 'dart:convert';
import 'dart:async';
import '../../core/theme/app_theme.dart';
import '../../core/services/auth_service.dart';

/// Clause Selector Widget - Browse and select from 102K+ clauses
///
/// Features:
/// - AI-powered recommendations with explanations
/// - Full-text search across all clauses
/// - Category filtering (100+ categories)
/// - Source filtering (LMA, CUAD, LEDGAR, etc.)
/// - Virtual scrolling for large lists
/// - Clause detail modal with full text
class ClauseSelectorWidget extends StatefulWidget {
  final int? assessmentId;
  final Set<String> selectedClauseIds;
  final Function(Set<String>) onSelectionChanged;
  final String? lineOfBusiness;

  const ClauseSelectorWidget({
    super.key,
    this.assessmentId,
    required this.selectedClauseIds,
    required this.onSelectionChanged,
    this.lineOfBusiness,
  });

  @override
  State<ClauseSelectorWidget> createState() => _ClauseSelectorWidgetState();
}

class _ClauseSelectorWidgetState extends State<ClauseSelectorWidget>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  // State
  bool _isLoading = true;
  bool _isLoadingMore = false;
  String _searchQuery = '';
  String? _selectedCategory;
  String? _selectedSource;

  // Data
  List<Map<String, dynamic>> _recommendations = [];
  List<Map<String, dynamic>> _clauses = [];
  List<Map<String, dynamic>> _categories = [];
  int _totalClauses = 0;
  int _currentPage = 1;
  final int _pageSize = 50;

  // Controllers
  final TextEditingController _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  Timer? _debounceTimer;

  // Statistics
  Map<String, int> _sourceStats = {};

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _scrollController.addListener(_onScroll);
    _loadInitialData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchController.dispose();
    _scrollController.dispose();
    _debounceTimer?.cancel();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 200) {
      _loadMoreClauses();
    }
  }

  Future<void> _loadInitialData() async {
    setState(() => _isLoading = true);

    await Future.wait([
      _loadCategories(),
      _loadStatistics(),
      if (widget.assessmentId != null) _loadRecommendations(),
      _loadClauses(),
    ]);

    setState(() => _isLoading = false);
  }

  Future<void> _loadCategories() async {
    try {
      final response = await authService.get('/clauses/categories');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _categories = List<Map<String, dynamic>>.from(data['categories'] ?? []);
      }
    } catch (e) {
      debugPrint('Error loading categories: $e');
    }
  }

  Future<void> _loadStatistics() async {
    try {
      final response = await authService.get('/clauses/statistics');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _sourceStats = Map<String, int>.from(data['sources'] ?? {});
        _totalClauses = data['total_clauses'] ?? 0;
      }
    } catch (e) {
      debugPrint('Error loading statistics: $e');
    }
  }

  Future<void> _loadRecommendations() async {
    if (widget.assessmentId == null) return;

    try {
      final response = await authService.post(
        '/clauses/recommend/${widget.assessmentId}',
        body: {},
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _recommendations = List<Map<String, dynamic>>.from(
          data['recommended_clauses'] ?? [],
        );

        // Auto-select mandatory clauses
        for (final rec in _recommendations) {
          if (rec['is_mandatory'] == true) {
            final clauseId = rec['clause']?['id']?.toString();
            if (clauseId != null) {
              widget.selectedClauseIds.add(clauseId);
            }
          }
        }
        widget.onSelectionChanged(widget.selectedClauseIds);
      }
    } catch (e) {
      debugPrint('Error loading recommendations: $e');
    }
  }

  Future<void> _loadClauses({bool reset = true}) async {
    if (reset) {
      _currentPage = 1;
      _clauses = [];
    }

    try {
      String url = '/clauses/library?page=$_currentPage&page_size=$_pageSize';

      if (_searchQuery.isNotEmpty) {
        url += '&search=${Uri.encodeComponent(_searchQuery)}';
      }
      if (_selectedCategory != null) {
        url += '&category=${Uri.encodeComponent(_selectedCategory!)}';
      }
      if (_selectedSource != null) {
        url += '&source=${Uri.encodeComponent(_selectedSource!)}';
      }
      if (widget.lineOfBusiness != null) {
        url += '&line_of_business=${Uri.encodeComponent(widget.lineOfBusiness!)}';
      }

      final response = await authService.get(url);
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final newClauses = List<Map<String, dynamic>>.from(data['items'] ?? []);

        setState(() {
          if (reset) {
            _clauses = newClauses;
          } else {
            _clauses.addAll(newClauses);
          }
          _totalClauses = data['total'] ?? _totalClauses;
        });
      }
    } catch (e) {
      debugPrint('Error loading clauses: $e');
    }
  }

  Future<void> _loadMoreClauses() async {
    if (_isLoadingMore || _clauses.length >= _totalClauses) return;

    setState(() => _isLoadingMore = true);
    _currentPage++;
    await _loadClauses(reset: false);
    setState(() => _isLoadingMore = false);
  }

  void _onSearchChanged(String value) {
    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(milliseconds: 500), () {
      setState(() => _searchQuery = value);
      _loadClauses();
    });
  }

  void _toggleClause(String clauseId) {
    setState(() {
      if (widget.selectedClauseIds.contains(clauseId)) {
        widget.selectedClauseIds.remove(clauseId);
      } else {
        widget.selectedClauseIds.add(clauseId);
      }
    });
    widget.onSelectionChanged(widget.selectedClauseIds);
  }

  void _showClauseDetail(Map<String, dynamic> clause) async {
    // Load full clause detail
    try {
      final response = await authService.get('/clauses/${clause['id']}');
      if (response.statusCode == 200) {
        final fullClause = jsonDecode(response.body);
        if (mounted) {
          _showClauseDetailSheet(fullClause);
        }
      }
    } catch (e) {
      if (mounted) {
        _showClauseDetailSheet(clause);
      }
    }
  }

  void _showClauseDetailSheet(Map<String, dynamic> clause) {
    final name = clause['name']?.toString() ?? 'Unknown';
    final category = clause['category']?.toString() ?? '';
    final source = clause['source']?.toString() ?? '';
    final text = clause['text'] ?? clause['text_preview'] ?? '';
    final clauseId = clause['id']?.toString() ?? '';
    final isSelected = widget.selectedClauseIds.contains(clauseId);

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        maxChildSize: 0.95,
        minChildSize: 0.5,
        builder: (context, scrollController) => Container(
          decoration: const BoxDecoration(
            color: Colors.white,
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
                  color: Colors.grey[300],
                  borderRadius: BorderRadius.circular(2),
                ),
              ),

              // Header
              Padding(
                padding: const EdgeInsets.all(20),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: AppTheme.primaryDark.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Icon(
                        Icons.description,
                        color: AppTheme.primaryDark,
                        size: 24,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            name,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Row(
                            children: [
                              _buildTag(category.replaceAll('_', ' ').toUpperCase()),
                              const SizedBox(width: 8),
                              _buildTag(source.toUpperCase(), color: AppTheme.info),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

              const Divider(height: 1),

              // Content
              Expanded(
                child: SingleChildScrollView(
                  controller: scrollController,
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'CLAUSE TEXT',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textSecondary,
                          letterSpacing: 1,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: AppTheme.background,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppTheme.border),
                        ),
                        child: SelectableText(
                          text,
                          style: const TextStyle(
                            fontSize: 14,
                            color: AppTheme.textPrimary,
                            height: 1.6,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              // Action buttons
              Container(
                padding: EdgeInsets.fromLTRB(
                  20, 16, 20, 16 + MediaQuery.of(context).padding.bottom,
                ),
                decoration: BoxDecoration(
                  color: Colors.white,
                  border: Border(top: BorderSide(color: AppTheme.border)),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => Navigator.pop(context),
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 14),
                        ),
                        child: const Text('Close'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      flex: 2,
                      child: ElevatedButton.icon(
                        onPressed: () {
                          _toggleClause(clauseId);
                          Navigator.pop(context);
                        },
                        icon: Icon(
                          isSelected ? Icons.remove_circle : Icons.add_circle,
                          size: 20,
                        ),
                        label: Text(isSelected ? 'Remove' : 'Add to Document'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: isSelected ? AppTheme.danger : AppTheme.primaryDark,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 14),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTag(String text, {Color? color}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: (color ?? AppTheme.textSecondary).withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w600,
          color: color ?? AppTheme.textSecondary,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Header with stats
        _buildHeader(),

        // Search and filters
        _buildSearchAndFilters(),

        // Tab bar
        TabBar(
          controller: _tabController,
          labelColor: AppTheme.primaryDark,
          unselectedLabelColor: AppTheme.textSecondary,
          indicatorColor: AppTheme.primaryDark,
          tabs: [
            Tab(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.auto_awesome, size: 16),
                  const SizedBox(width: 6),
                  Text('AI Recommended (${_recommendations.length})'),
                ],
              ),
            ),
            Tab(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.library_books, size: 16),
                  const SizedBox(width: 6),
                  Text('Browse All ($_totalClauses)'),
                ],
              ),
            ),
            Tab(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.check_circle, size: 16),
                  const SizedBox(width: 6),
                  Text('Selected (${widget.selectedClauseIds.length})'),
                ],
              ),
            ),
          ],
        ),

        const Divider(height: 1),

        // Tab content
        Expanded(
          child: _isLoading
              ? const Center(child: CircularProgressIndicator())
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildRecommendationsTab(),
                    _buildBrowseTab(),
                    _buildSelectedTab(),
                  ],
                ),
        ),
      ],
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.primaryDark.withOpacity(0.05),
            Colors.transparent,
          ],
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
        ),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppTheme.primaryDark.withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(
              Icons.library_books,
              color: AppTheme.primaryDark,
              size: 24,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Clauses Library',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                Text(
                  '${_formatNumber(_totalClauses)} clauses • ${_categories.length} categories',
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          // Source chips
          Wrap(
            spacing: 8,
            children: _sourceStats.entries.take(3).map((e) => Chip(
              label: Text('${e.key.toUpperCase()}: ${_formatNumber(e.value)}'),
              labelStyle: const TextStyle(fontSize: 10),
              padding: EdgeInsets.zero,
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            )).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildSearchAndFilters() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      child: Row(
        children: [
          // Search field
          Expanded(
            flex: 3,
            child: TextField(
              controller: _searchController,
              onChanged: _onSearchChanged,
              decoration: InputDecoration(
                hintText: 'Search clauses...',
                prefixIcon: const Icon(Icons.search, size: 20),
                suffixIcon: _searchQuery.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, size: 18),
                        onPressed: () {
                          _searchController.clear();
                          _onSearchChanged('');
                        },
                      )
                    : null,
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: BorderSide(color: AppTheme.border),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: BorderSide(color: AppTheme.border),
                ),
              ),
            ),
          ),

          const SizedBox(width: 12),

          // Category filter
          Expanded(
            flex: 2,
            child: DropdownButtonFormField<String>(
              value: _selectedCategory,
              decoration: InputDecoration(
                labelText: 'Category',
                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
              ),
              items: [
                const DropdownMenuItem(value: null, child: Text('All Categories')),
                ..._categories.take(20).map((cat) => DropdownMenuItem(
                  value: cat['id']?.toString(),
                  child: Text(
                    '${cat['name']} (${cat['count']})',
                    overflow: TextOverflow.ellipsis,
                  ),
                )),
              ],
              onChanged: (value) {
                setState(() => _selectedCategory = value);
                _loadClauses();
              },
            ),
          ),

          const SizedBox(width: 12),

          // Source filter
          Expanded(
            child: DropdownButtonFormField<String>(
              value: _selectedSource,
              decoration: InputDecoration(
                labelText: 'Source',
                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
              ),
              items: [
                const DropdownMenuItem(value: null, child: Text('All')),
                const DropdownMenuItem(value: 'lma', child: Text('LMA')),
                const DropdownMenuItem(value: 'cuad', child: Text('CUAD')),
                const DropdownMenuItem(value: 'ledgar', child: Text('LEDGAR')),
                const DropdownMenuItem(value: 'templates', child: Text('Templates')),
              ],
              onChanged: (value) {
                setState(() => _selectedSource = value);
                _loadClauses();
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecommendationsTab() {
    if (_recommendations.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.auto_awesome, size: 48, color: AppTheme.textHint),
            const SizedBox(height: 16),
            const Text(
              'No recommendations yet',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'AI recommendations will appear based on your assessment',
              style: TextStyle(color: AppTheme.textSecondary),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _recommendations.length,
      itemBuilder: (context, index) {
        final rec = _recommendations[index];
        final clause = rec['clause'] as Map<String, dynamic>? ?? {};
        final reason = rec['reason']?.toString() ?? '';
        final isMandatory = rec['is_mandatory'] == true;
        final relevanceScore = (rec['relevance_score'] as num?)?.toDouble() ?? 0.0;

        return _buildRecommendationCard(clause, reason, isMandatory, relevanceScore);
      },
    );
  }

  Widget _buildRecommendationCard(
    Map<String, dynamic> clause,
    String reason,
    bool isMandatory,
    double relevanceScore,
  ) {
    final clauseId = clause['id']?.toString() ?? '';
    final isSelected = widget.selectedClauseIds.contains(clauseId);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: isMandatory ? AppTheme.warning : (isSelected ? AppTheme.success : AppTheme.border),
          width: isMandatory || isSelected ? 2 : 1,
        ),
      ),
      child: InkWell(
        onTap: isMandatory ? null : () => _toggleClause(clauseId),
        onLongPress: () => _showClauseDetail(clause),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  // Selection indicator (replaces checkbox for better tap target)
                  Container(
                    width: 28,
                    height: 28,
                    margin: const EdgeInsets.only(right: 12),
                    decoration: BoxDecoration(
                      color: isSelected ? AppTheme.success : (isMandatory ? AppTheme.warning : Colors.transparent),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(
                        color: isSelected ? AppTheme.success : (isMandatory ? AppTheme.warning : AppTheme.border),
                        width: 2,
                      ),
                    ),
                    child: isSelected || isMandatory
                        ? Icon(
                            isMandatory ? Icons.lock : Icons.check,
                            size: 16,
                            color: Colors.white,
                          )
                        : null,
                  ),

                  // Relevance score indicator
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: _getScoreColor(relevanceScore).withOpacity(0.1),
                      shape: BoxShape.circle,
                    ),
                    child: Center(
                      child: Text(
                        '${(relevanceScore * 100).toInt()}',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: _getScoreColor(relevanceScore),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),

                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            if (isMandatory)
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                margin: const EdgeInsets.only(right: 8),
                                decoration: BoxDecoration(
                                  color: AppTheme.warning,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: const Text(
                                  'MANDATORY',
                                  style: TextStyle(
                                    fontSize: 9,
                                    fontWeight: FontWeight.w700,
                                    color: Colors.white,
                                  ),
                                ),
                              ),
                            Expanded(
                              child: Text(
                                clause['name']?.toString() ?? '',
                                style: const TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600,
                                  color: AppTheme.textPrimary,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          clause['text_preview']?.toString() ?? '',
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppTheme.textSecondary,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),

                  // Info button to view details
                  IconButton(
                    icon: const Icon(Icons.info_outline, size: 20),
                    color: AppTheme.textSecondary,
                    onPressed: () => _showClauseDetail(clause),
                    tooltip: 'View clause details',
                  ),
                ],
              ),

              // AI reason
              if (reason.isNotEmpty) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppTheme.info.withOpacity(0.05),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppTheme.info.withOpacity(0.2)),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.auto_awesome, size: 14, color: AppTheme.info),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          reason,
                          style: TextStyle(
                            fontSize: 12,
                            color: AppTheme.info,
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBrowseTab() {
    if (_clauses.isEmpty && !_isLoading) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.search_off, size: 48, color: AppTheme.textHint),
            const SizedBox(height: 16),
            const Text(
              'No clauses found',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Try adjusting your search or filters',
              style: TextStyle(color: AppTheme.textSecondary),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.all(16),
      itemCount: _clauses.length + (_isLoadingMore ? 1 : 0),
      itemBuilder: (context, index) {
        if (index >= _clauses.length) {
          return const Center(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: CircularProgressIndicator(),
            ),
          );
        }

        final clause = _clauses[index];
        return _buildClauseCard(clause);
      },
    );
  }

  Widget _buildClauseCard(Map<String, dynamic> clause) {
    final clauseId = clause['id']?.toString() ?? '';
    final isSelected = widget.selectedClauseIds.contains(clauseId);

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(
          color: isSelected ? AppTheme.success : AppTheme.border,
          width: isSelected ? 2 : 1,
        ),
      ),
      child: InkWell(
        onTap: () => _toggleClause(clauseId),
        onLongPress: () => _showClauseDetail(clause),
        borderRadius: BorderRadius.circular(10),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              // Selection indicator
              Container(
                width: 24,
                height: 24,
                margin: const EdgeInsets.only(right: 12),
                decoration: BoxDecoration(
                  color: isSelected ? AppTheme.success : Colors.transparent,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(
                    color: isSelected ? AppTheme.success : AppTheme.border,
                    width: 2,
                  ),
                ),
                child: isSelected
                    ? const Icon(Icons.check, size: 16, color: Colors.white)
                    : null,
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      clause['name']?.toString() ?? '',
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textPrimary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      clause['text_preview']?.toString() ?? '',
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppTheme.textSecondary,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        _buildTag((clause['category']?.toString() ?? '').replaceAll('_', ' ')),
                        const SizedBox(width: 6),
                        _buildTag(clause['source']?.toString().toUpperCase() ?? '', color: AppTheme.info),
                      ],
                    ),
                  ],
                ),
              ),
              // Info button to view details
              IconButton(
                icon: const Icon(Icons.info_outline, size: 20),
                color: AppTheme.textSecondary,
                onPressed: () => _showClauseDetail(clause),
                tooltip: 'View clause details',
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSelectedTab() {
    final selectedClauses = _clauses.where(
      (c) => widget.selectedClauseIds.contains(c['id']?.toString()),
    ).toList();

    // Also include recommended clauses that are selected
    for (final rec in _recommendations) {
      final clause = rec['clause'] as Map<String, dynamic>? ?? {};
      final clauseId = clause['id']?.toString() ?? '';
      if (widget.selectedClauseIds.contains(clauseId) &&
          !selectedClauses.any((c) => c['id']?.toString() == clauseId)) {
        selectedClauses.add(clause);
      }
    }

    if (selectedClauses.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.playlist_add, size: 48, color: AppTheme.textHint),
            const SizedBox(height: 16),
            const Text(
              'No clauses selected',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Browse or use AI recommendations to select clauses',
              style: TextStyle(color: AppTheme.textSecondary),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: selectedClauses.length,
      itemBuilder: (context, index) {
        final clause = selectedClauses[index];
        return _buildClauseCard(clause);
      },
    );
  }

  Color _getScoreColor(double score) {
    if (score >= 0.8) return AppTheme.success;
    if (score >= 0.6) return AppTheme.warning;
    return AppTheme.info;
  }

  String _formatNumber(int number) {
    if (number >= 1000000) {
      return '${(number / 1000000).toStringAsFixed(1)}M';
    } else if (number >= 1000) {
      return '${(number / 1000).toStringAsFixed(0)}K';
    }
    return number.toString();
  }
}
