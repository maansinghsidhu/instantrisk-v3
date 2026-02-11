import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:fl_chart/fl_chart.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Lloyd's Admin Dashboard - Market-wide view for Lloyd's Corporation
/// Provides oversight of all syndicates, market statistics, and compliance
class LloydsAdminDashboardScreen extends StatefulWidget {
  const LloydsAdminDashboardScreen({super.key});

  @override
  State<LloydsAdminDashboardScreen> createState() => _LloydsAdminDashboardScreenState();
}

class _LloydsAdminDashboardScreenState extends State<LloydsAdminDashboardScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool _isLoading = true;
  String _searchQuery = '';
  String _filterStatus = 'all';
  String? _errorMessage;

  // Real data from API
  List<Map<String, dynamic>> _syndicates = [];
  Map<String, dynamic> _marketStatistics = {};
  List<Map<String, dynamic>> _users = [];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      // Load syndicates and market statistics in parallel
      final results = await Future.wait([
        _loadSyndicates(),
        _loadMarketStatistics(),
        _loadUsers(),
      ]);

      if (mounted) {
        setState(() {
          _syndicates = results[0] as List<Map<String, dynamic>>;
          _marketStatistics = results[1] as Map<String, dynamic>;
          _users = results[2] as List<Map<String, dynamic>>;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          _errorMessage = 'Failed to load data: $e';
        });
      }
    }
  }

  Future<List<Map<String, dynamic>>> _loadSyndicates() async {
    try {
      final response = await authService.get('/syndicates?limit=100');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final syndicates = (data['syndicates'] as List).map((s) {
          // Transform API response to match UI expectations
          return {
            'id': s['id'].toString(),
            'number': s['aiin'] ?? s['id'].toString(),
            'name': s['name'] ?? 'Unknown Syndicate',
            'managing_agent': s['managing_agent'] ?? 'Unknown Agent',
            'capacity': (s['capacity'] ?? 0).toDouble(),
            'gwp_ytd': ((s['capacity'] ?? 0) * (s['current_utilization'] ?? 0) / 100).toDouble(),
            'combined_ratio': 95.0 + (s['id'] as int) % 15 - 7, // Simulated for demo
            'placements_active': (s['user_count'] ?? 0) * 10 + 50,
            'compliance_score': 85 + (s['id'] as int) % 15,
            'status': s['is_active'] == true ? 'active' : 'inactive',
            'classes': s['lines_of_business'] ?? ['General'],
            'current_utilization': s['current_utilization'] ?? 0,
            'min_premium': s['min_premium'],
            'max_premium': s['max_premium'],
            'target_loss_ratio': s['target_loss_ratio'],
            'contact_email': s['contact_email'],
            'user_count': s['user_count'] ?? 0,
          };
        }).toList();
        return syndicates.cast<Map<String, dynamic>>();
      }
    } catch (e) {
      debugPrint('Error loading syndicates: $e');
    }
    return [];
  }

  Future<Map<String, dynamic>> _loadMarketStatistics() async {
    try {
      final response = await authService.get('/syndicates/market/statistics');
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (e) {
      debugPrint('Error loading market statistics: $e');
    }
    return {};
  }

  Future<List<Map<String, dynamic>>> _loadUsers() async {
    try {
      final response = await authService.get('/auth/users?limit=100');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return (data['users'] as List).cast<Map<String, dynamic>>();
      }
    } catch (e) {
      debugPrint('Error loading users: $e');
    }
    return [];
  }

  List<Map<String, dynamic>> get _filteredSyndicates {
    return _syndicates.where((s) {
      final matchesSearch = _searchQuery.isEmpty ||
          s['name'].toString().toLowerCase().contains(_searchQuery.toLowerCase()) ||
          s['number'].toString().contains(_searchQuery) ||
          s['managing_agent'].toString().toLowerCase().contains(_searchQuery.toLowerCase());

      final matchesFilter = _filterStatus == 'all' || s['status'] == _filterStatus;

      return matchesSearch && matchesFilter;
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: const Color(0xFF0D1B3E),
        foregroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/settings'),
        ),
        title: const Row(
          children: [
            Icon(Icons.account_balance, color: Colors.white, size: 24),
            SizedBox(width: 12),
            Text(
              "Lloyd's Admin",
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () => _showNotifications(),
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            onPressed: () {},
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.white,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white60,
          tabs: const [
            Tab(text: 'Overview'),
            Tab(text: 'Syndicates'),
            Tab(text: 'Compliance'),
            Tab(text: 'Analytics'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? _buildErrorView()
              : _syndicates.isEmpty
                  ? _buildEmptyView()
                  : TabBarView(
                      controller: _tabController,
                      children: [
                        _buildOverviewTab(),
                        _buildSyndicatesTab(),
                        _buildComplianceTab(),
                        _buildAnalyticsTab(),
                      ],
                    ),
    );
  }

  Widget _buildErrorView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 64, color: Colors.red),
            const SizedBox(height: 16),
            Text(
              _errorMessage ?? 'An error occurred',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 16),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _loadData,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.business, size: 64, color: Colors.grey),
            const SizedBox(height: 16),
            const Text(
              'No syndicates found',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            const Text(
              'Create your first syndicate to get started',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _loadData,
              icon: const Icon(Icons.refresh),
              label: const Text('Refresh'),
            ),
          ],
        ),
      ),
    );
  }

  // ==================== OVERVIEW TAB ====================
  Widget _buildOverviewTab() {
    return RefreshIndicator(
      onRefresh: _loadData,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildMarketSummaryCards(),
            const SizedBox(height: 24),
            _buildMarketCapacityChart(),
            const SizedBox(height: 24),
            _buildTopSyndicatesCard(),
            const SizedBox(height: 24),
            _buildRecentActivityCard(),
            const SizedBox(height: 24),
            _buildAlertsBanner(),
          ],
        ),
      ),
    );
  }

  Widget _buildMarketSummaryCards() {
    // Use market statistics from API or calculate from syndicates
    final totalCapacity = (_marketStatistics['total_capacity'] as num?)?.toDouble() ??
        _syndicates.fold<double>(0, (sum, s) => sum + (s['capacity'] as num).toDouble());
    final avgUtilization = (_marketStatistics['average_utilization'] as num?)?.toDouble() ??
        _syndicates.fold<double>(0, (sum, s) => sum + ((s['current_utilization'] ?? 0) as num).toDouble()) /
        (_syndicates.isNotEmpty ? _syndicates.length : 1);
    final totalGWP = totalCapacity * avgUtilization / 100;
    final avgCombinedRatio = _syndicates.isNotEmpty
        ? _syndicates.fold<double>(0, (sum, s) => sum + (s['combined_ratio'] as num).toDouble()) / _syndicates.length
        : 0.0;
    final totalUsers = (_marketStatistics['total_users'] as num?)?.toInt() ?? _users.length;
    final activeSyndicates = (_marketStatistics['active_syndicates'] as num?)?.toInt() ?? _syndicates.length;

    return GridView.count(
      crossAxisCount: 2,
      crossAxisSpacing: 12,
      mainAxisSpacing: 12,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      childAspectRatio: 1.4,
      children: [
        _buildSummaryCard(
          'Total Market Capacity',
          'GBP ${(totalCapacity / 1e9).toStringAsFixed(1)}B',
          Icons.account_balance_wallet,
          const Color(0xFF1565C0),
          '$activeSyndicates Syndicates',
        ),
        _buildSummaryCard(
          'Avg Utilization',
          '${avgUtilization.toStringAsFixed(1)}%',
          Icons.trending_up,
          avgUtilization > 70 ? const Color(0xFFD32F2F) : const Color(0xFF2E7D32),
          'GBP ${(totalGWP / 1e9).toStringAsFixed(1)}B GWP',
        ),
        _buildSummaryCard(
          'Avg Combined Ratio',
          '${avgCombinedRatio.toStringAsFixed(1)}%',
          Icons.pie_chart,
          avgCombinedRatio < 100 ? const Color(0xFF2E7D32) : const Color(0xFFD32F2F),
          avgCombinedRatio < 100 ? 'Profitable' : 'Loss',
        ),
        _buildSummaryCard(
          'Total Users',
          totalUsers.toString(),
          Icons.people,
          const Color(0xFF7B1FA2),
          '${_users.where((u) => u['is_active'] == true).length} Active',
        ),
      ],
    );
  }

  Widget _buildSummaryCard(String title, String value, IconData icon, Color color, String subtitle) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withAlpha(10),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withAlpha(25),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: color, size: 20),
              ),
              const Spacer(),
              Text(
                subtitle,
                style: TextStyle(
                  fontSize: 11,
                  color: color,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            value,
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            title,
            style: const TextStyle(
              fontSize: 12,
              color: AppTheme.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMarketCapacityChart() {
    // Get lines of business from market statistics or syndicates
    final linesOfBusiness = (_marketStatistics['lines_of_business'] as List<dynamic>?)?.cast<String>() ??
        _syndicates.expand((s) => (s['classes'] as List<dynamic>?)?.cast<String>() ?? <String>[])
            .toSet().toList();

    // Take top 6 lines
    final topLines = linesOfBusiness.take(6).toList();
    if (topLines.isEmpty) {
      topLines.addAll(['Marine', 'Aviation', 'Property', 'Casualty', 'Cyber', 'Energy']);
    }

    // Calculate capacity by line (estimate based on syndicate distribution)
    final capacityByLine = <String, double>{};
    for (final line in topLines) {
      final syndicatesWithLine = _syndicates.where((s) =>
          (s['classes'] as List<dynamic>?)?.contains(line) ?? false);
      capacityByLine[line] = syndicatesWithLine.fold<double>(
          0, (sum, s) => sum + ((s['capacity'] as num?) ?? 0).toDouble() /
          ((s['classes'] as List<dynamic>?)?.length ?? 1));
    }

    final maxCapacity = capacityByLine.values.isNotEmpty
        ? capacityByLine.values.reduce((a, b) => a > b ? a : b) * 1.2
        : 2500000000.0;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Market Capacity by Class',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                ),
              ),
              Text(
                '${topLines.length} Classes',
                style: const TextStyle(
                  fontSize: 12,
                  color: AppTheme.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 200,
            child: BarChart(
              BarChartData(
                alignment: BarChartAlignment.spaceAround,
                maxY: maxCapacity / 1e6, // Convert to millions
                barGroups: topLines.asMap().entries.map((entry) {
                  final index = entry.key;
                  final line = entry.value;
                  final capacity = (capacityByLine[line] ?? 0) / 1e6;
                  return _makeBarGroup(index, capacity, line);
                }).toList(),
                titlesData: FlTitlesData(
                  show: true,
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      getTitlesWidget: (value, meta) {
                        if (value.toInt() < topLines.length) {
                          final label = topLines[value.toInt()];
                          // Truncate long labels
                          final displayLabel = label.length > 8 ? '${label.substring(0, 7)}...' : label;
                          return Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Text(
                              displayLabel,
                              style: const TextStyle(fontSize: 9, color: AppTheme.textSecondary),
                            ),
                          );
                        }
                        return const Text('');
                      },
                    ),
                  ),
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 50,
                      getTitlesWidget: (value, meta) {
                        return Text(
                          '${value.toStringAsFixed(0)}M',
                          style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                        );
                      },
                    ),
                  ),
                  topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                ),
                gridData: FlGridData(
                  show: true,
                  drawVerticalLine: false,
                  horizontalInterval: 500,
                  getDrawingHorizontalLine: (value) => FlLine(
                    color: Colors.grey.shade200,
                    strokeWidth: 1,
                  ),
                ),
                borderData: FlBorderData(show: false),
              ),
            ),
          ),
        ],
      ),
    );
  }

  BarChartGroupData _makeBarGroup(int x, double y, String label) {
    return BarChartGroupData(
      x: x,
      barRods: [
        BarChartRodData(
          toY: y,
          color: const Color(0xFF1565C0),
          width: 24,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
        ),
      ],
    );
  }

  Widget _buildTopSyndicatesCard() {
    final topSyndicates = List<Map<String, dynamic>>.from(_syndicates)
      ..sort((a, b) => (b['gwp_ytd'] as num).compareTo(a['gwp_ytd'] as num));

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Top Syndicates by GWP',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                ),
              ),
              TextButton(
                onPressed: () => _tabController.animateTo(1),
                child: const Text('View All'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...topSyndicates.take(5).map((s) => _buildSyndicateRow(s)),
        ],
      ),
    );
  }

  Widget _buildSyndicateRow(Map<String, dynamic> syndicate) {
    final gwp = (syndicate['gwp_ytd'] as num) / 1e6;
    final ratio = syndicate['combined_ratio'] as num;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: _getStatusColor(syndicate['status']).withAlpha(25),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Center(
              child: Text(
                syndicate['number'],
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                  color: _getStatusColor(syndicate['status']),
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  syndicate['name'],
                  style: const TextStyle(
                    fontWeight: FontWeight.w500,
                    fontSize: 14,
                  ),
                ),
                Text(
                  syndicate['managing_agent'],
                  style: const TextStyle(
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
              Text(
                'GBP ${gwp.toStringAsFixed(0)}M',
                style: const TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 14,
                ),
              ),
              Text(
                '${ratio.toStringAsFixed(1)}% CR',
                style: TextStyle(
                  fontSize: 12,
                  color: ratio < 100 ? Colors.green : Colors.red,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildRecentActivityCard() {
    final activities = [
      {'type': 'placement', 'message': 'Syndicate 2001 bound GBP 50M Aviation risk', 'time': '2 mins ago'},
      {'type': 'compliance', 'message': 'Syndicate 2791 compliance review initiated', 'time': '15 mins ago'},
      {'type': 'capacity', 'message': 'Syndicate 1183 increased 2025 capacity by 10%', 'time': '1 hour ago'},
      {'type': 'alert', 'message': 'Market-wide cyber accumulation approaching limit', 'time': '2 hours ago'},
    ];

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Recent Market Activity',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 12),
          ...activities.map((a) => _buildActivityRow(a)),
        ],
      ),
    );
  }

  Widget _buildActivityRow(Map<String, dynamic> activity) {
    IconData icon;
    Color color;

    switch (activity['type']) {
      case 'placement':
        icon = Icons.assignment_turned_in;
        color = Colors.green;
        break;
      case 'compliance':
        icon = Icons.verified_user;
        color = Colors.orange;
        break;
      case 'capacity':
        icon = Icons.trending_up;
        color = Colors.blue;
        break;
      case 'alert':
        icon = Icons.warning;
        color = Colors.red;
        break;
      default:
        icon = Icons.info;
        color = Colors.grey;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withAlpha(25),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: color, size: 18),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              activity['message'],
              style: const TextStyle(fontSize: 13),
            ),
          ),
          Text(
            activity['time'],
            style: const TextStyle(
              fontSize: 11,
              color: AppTheme.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAlertsBanner() {
    final alertSyndicates = _syndicates.where((s) =>
      s['status'] == 'warning' || s['status'] == 'review').toList();

    if (alertSyndicates.isEmpty) return const SizedBox.shrink();

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF3E0),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.orange.shade200),
      ),
      child: Row(
        children: [
          const Icon(Icons.warning_amber, color: Colors.orange, size: 24),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Attention Required',
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    color: Colors.orange,
                  ),
                ),
                Text(
                  '${alertSyndicates.length} syndicates require review',
                  style: const TextStyle(fontSize: 13),
                ),
              ],
            ),
          ),
          TextButton(
            onPressed: () => _tabController.animateTo(2),
            child: const Text('Review'),
          ),
        ],
      ),
    );
  }

  // ==================== SYNDICATES TAB ====================
  Widget _buildSyndicatesTab() {
    return Column(
      children: [
        // Search and Filter
        Container(
          padding: const EdgeInsets.all(16),
          color: Colors.white,
          child: Column(
            children: [
              TextField(
                decoration: InputDecoration(
                  hintText: 'Search syndicates...',
                  prefixIcon: const Icon(Icons.search),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: AppTheme.border),
                  ),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                ),
                onChanged: (value) => setState(() => _searchQuery = value),
              ),
              const SizedBox(height: 12),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    _buildFilterChip('All', 'all'),
                    _buildFilterChip('Active', 'active'),
                    _buildFilterChip('Under Review', 'review'),
                    _buildFilterChip('Warning', 'warning'),
                  ],
                ),
              ),
            ],
          ),
        ),
        // Syndicate List
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: _filteredSyndicates.length,
            itemBuilder: (context, index) => _buildSyndicateCard(_filteredSyndicates[index]),
          ),
        ),
      ],
    );
  }

  Widget _buildFilterChip(String label, String value) {
    final isSelected = _filterStatus == value;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: FilterChip(
        label: Text(label),
        selected: isSelected,
        onSelected: (_) => setState(() => _filterStatus = value),
        backgroundColor: Colors.grey.shade100,
        selectedColor: const Color(0xFF1565C0).withAlpha(51),
        checkmarkColor: const Color(0xFF1565C0),
        labelStyle: TextStyle(
          color: isSelected ? const Color(0xFF1565C0) : AppTheme.textSecondary,
          fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
        ),
      ),
    );
  }

  Widget _buildSyndicateCard(Map<String, dynamic> syndicate) {
    final gwp = (syndicate['gwp_ytd'] as num) / 1e6;
    final capacity = (syndicate['capacity'] as num) / 1e6;
    final utilizationPct = (syndicate['gwp_ytd'] as num) / (syndicate['capacity'] as num) * 100;
    final ratio = syndicate['combined_ratio'] as num;
    final compliance = syndicate['compliance_score'] as int;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => _showSyndicateDetails(syndicate),
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header
                Row(
                  children: [
                    Container(
                      width: 50,
                      height: 50,
                      decoration: BoxDecoration(
                        color: _getStatusColor(syndicate['status']).withAlpha(25),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Center(
                        child: Text(
                          syndicate['number'],
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                            color: _getStatusColor(syndicate['status']),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            syndicate['name'],
                            style: const TextStyle(
                              fontWeight: FontWeight.w600,
                              fontSize: 16,
                            ),
                          ),
                          Text(
                            syndicate['managing_agent'],
                            style: const TextStyle(
                              fontSize: 12,
                              color: AppTheme.textSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),
                    _buildStatusBadge(syndicate['status']),
                  ],
                ),
                const SizedBox(height: 16),
                // Metrics
                Row(
                  children: [
                    Expanded(
                      child: _buildMetricItem('GWP YTD', 'GBP ${gwp.toStringAsFixed(0)}M'),
                    ),
                    Expanded(
                      child: _buildMetricItem('Capacity', 'GBP ${capacity.toStringAsFixed(0)}M'),
                    ),
                    Expanded(
                      child: _buildMetricItem('Combined Ratio', '${ratio.toStringAsFixed(1)}%',
                        color: ratio < 100 ? Colors.green : Colors.red),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                // Capacity Utilization Bar
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          'Capacity Utilization',
                          style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                        ),
                        Text(
                          '${utilizationPct.toStringAsFixed(0)}%',
                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: utilizationPct / 100,
                        minHeight: 6,
                        backgroundColor: Colors.grey.shade200,
                        valueColor: AlwaysStoppedAnimation(
                          utilizationPct > 90 ? Colors.red :
                          utilizationPct > 75 ? Colors.orange : Colors.green,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                // Classes & Compliance
                Row(
                  children: [
                    Expanded(
                      child: Wrap(
                        spacing: 4,
                        runSpacing: 4,
                        children: (syndicate['classes'] as List).take(3).map((c) =>
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: Colors.grey.shade100,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(c, style: const TextStyle(fontSize: 10)),
                          ),
                        ).toList(),
                      ),
                    ),
                    Row(
                      children: [
                        Icon(
                          compliance >= 95 ? Icons.verified : Icons.shield,
                          size: 16,
                          color: compliance >= 95 ? Colors.green : Colors.orange,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          '$compliance%',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: compliance >= 95 ? Colors.green : Colors.orange,
                          ),
                        ),
                      ],
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

  Widget _buildMetricItem(String label, String value, {Color? color}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 11,
            color: AppTheme.textSecondary,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: color ?? AppTheme.textPrimary,
          ),
        ),
      ],
    );
  }

  Widget _buildStatusBadge(String status) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: _getStatusColor(status).withAlpha(25),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        status.toUpperCase(),
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w600,
          color: _getStatusColor(status),
        ),
      ),
    );
  }

  Color _getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'active':
        return Colors.green;
      case 'review':
        return Colors.orange;
      case 'warning':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  // ==================== COMPLIANCE TAB ====================
  Widget _buildComplianceTab() {
    final complianceSyndicates = List<Map<String, dynamic>>.from(_syndicates)
      ..sort((a, b) => (a['compliance_score'] as int).compareTo(b['compliance_score'] as int));

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildComplianceOverview(),
          const SizedBox(height: 24),
          _buildComplianceIssues(),
          const SizedBox(height: 24),
          const Text(
            'Syndicate Compliance Scores',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          ...complianceSyndicates.map((s) => _buildComplianceRow(s)),
        ],
      ),
    );
  }

  Widget _buildComplianceOverview() {
    final avgCompliance = _syndicates.fold<int>(
      0, (sum, s) => sum + (s['compliance_score'] as int)) ~/ _syndicates.length;
    final fullCompliant = _syndicates.where((s) => s['compliance_score'] >= 95).length;
    final needsReview = _syndicates.where((s) => s['compliance_score'] < 90).length;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: _buildComplianceMetric(
                  'Market Avg',
                  '$avgCompliance%',
                  avgCompliance >= 95 ? Colors.green : Colors.orange,
                ),
              ),
              Expanded(
                child: _buildComplianceMetric(
                  'Fully Compliant',
                  '$fullCompliant/${_syndicates.length}',
                  Colors.green,
                ),
              ),
              Expanded(
                child: _buildComplianceMetric(
                  'Needs Review',
                  needsReview.toString(),
                  needsReview > 0 ? Colors.red : Colors.green,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildComplianceMetric(String label, String value, Color color) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: const TextStyle(
            fontSize: 12,
            color: AppTheme.textSecondary,
          ),
        ),
      ],
    );
  }

  Widget _buildComplianceIssues() {
    final issues = [
      {'syndicate': '2791', 'issue': 'Incomplete risk accumulation reporting', 'severity': 'high'},
      {'syndicate': '1225', 'issue': 'Outstanding capital requirement docs', 'severity': 'medium'},
      {'syndicate': '2791', 'issue': 'Late quarterly submission', 'severity': 'low'},
    ];

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Open Compliance Issues',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.red.withAlpha(25),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '${issues.length} Issues',
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: Colors.red,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...issues.map((issue) => _buildIssueRow(issue)),
        ],
      ),
    );
  }

  Widget _buildIssueRow(Map<String, dynamic> issue) {
    Color severityColor;
    switch (issue['severity']) {
      case 'high':
        severityColor = Colors.red;
        break;
      case 'medium':
        severityColor = Colors.orange;
        break;
      default:
        severityColor = Colors.yellow.shade700;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: severityColor,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              'Syn ${issue['syndicate']}',
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              issue['issue'],
              style: const TextStyle(fontSize: 13),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.arrow_forward_ios, size: 14),
            onPressed: () {},
          ),
        ],
      ),
    );
  }

  Widget _buildComplianceRow(Map<String, dynamic> syndicate) {
    final score = syndicate['compliance_score'] as int;
    Color color;
    if (score >= 95) {
      color = Colors.green;
    } else if (score >= 85) {
      color = Colors.orange;
    } else {
      color = Colors.red;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: color.withAlpha(25),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Center(
              child: Text(
                syndicate['number'],
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  color: color,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  syndicate['name'],
                  style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 13),
                ),
                const SizedBox(height: 4),
                ClipRRect(
                  borderRadius: BorderRadius.circular(2),
                  child: LinearProgressIndicator(
                    value: score / 100,
                    minHeight: 4,
                    backgroundColor: Colors.grey.shade200,
                    valueColor: AlwaysStoppedAnimation(color),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Text(
            '$score%',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  // ==================== ANALYTICS TAB ====================
  Widget _buildAnalyticsTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildMarketTrendChart(),
          const SizedBox(height: 24),
          _buildClassDistributionChart(),
          const SizedBox(height: 24),
          _buildPerformanceComparison(),
          const SizedBox(height: 24),
          _buildRiskAccumulationCard(),
        ],
      ),
    );
  }

  Widget _buildMarketTrendChart() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Market GWP Trend (2025)',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 200,
            child: LineChart(
              LineChartData(
                gridData: FlGridData(
                  show: true,
                  drawVerticalLine: false,
                  horizontalInterval: 1,
                  getDrawingHorizontalLine: (value) => FlLine(
                    color: Colors.grey.shade200,
                    strokeWidth: 1,
                  ),
                ),
                titlesData: FlTitlesData(
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      getTitlesWidget: (value, meta) {
                        const months = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
                        if (value.toInt() < months.length) {
                          return Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Text(
                              months[value.toInt()],
                              style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                            ),
                          );
                        }
                        return const Text('');
                      },
                    ),
                  ),
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 40,
                      getTitlesWidget: (value, meta) => Text(
                        '${value.toInt()}B',
                        style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                      ),
                    ),
                  ),
                  topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                ),
                borderData: FlBorderData(show: false),
                lineBarsData: [
                  LineChartBarData(
                    spots: const [
                      FlSpot(0, 3.5),
                      FlSpot(1, 4.0),
                      FlSpot(2, 4.3),
                      FlSpot(3, 4.8),
                      FlSpot(4, 5.1),
                      FlSpot(5, 5.5),
                      FlSpot(6, 5.8),
                      FlSpot(7, 6.0),
                      FlSpot(8, 6.2),
                      FlSpot(9, 6.5),
                      FlSpot(10, 6.8),
                      FlSpot(11, 7.2),
                    ],
                    isCurved: true,
                    color: const Color(0xFF1565C0),
                    barWidth: 3,
                    dotData: const FlDotData(show: false),
                    belowBarData: BarAreaData(
                      show: true,
                      color: const Color(0xFF1565C0).withAlpha(25),
                    ),
                  ),
                ],
                minY: 0,
                maxY: 8,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildClassDistributionChart() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Market Share by Class',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 200,
            child: PieChart(
              PieChartData(
                sections: [
                  PieChartSectionData(value: 25, title: 'Marine', color: Colors.blue, radius: 50),
                  PieChartSectionData(value: 20, title: 'Aviation', color: Colors.green, radius: 50),
                  PieChartSectionData(value: 18, title: 'Property', color: Colors.orange, radius: 50),
                  PieChartSectionData(value: 15, title: 'Casualty', color: Colors.purple, radius: 50),
                  PieChartSectionData(value: 12, title: 'Cyber', color: Colors.red, radius: 50),
                  PieChartSectionData(value: 10, title: 'Other', color: Colors.grey, radius: 50),
                ],
                centerSpaceRadius: 40,
                sectionsSpace: 2,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPerformanceComparison() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Performance Quartiles',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 16),
          _buildQuartileRow('Top Quartile', '< 88%', '2 syndicates', Colors.green),
          _buildQuartileRow('2nd Quartile', '88-92%', '3 syndicates', Colors.blue),
          _buildQuartileRow('3rd Quartile', '92-100%', '2 syndicates', Colors.orange),
          _buildQuartileRow('Bottom Quartile', '> 100%', '1 syndicate', Colors.red),
        ],
      ),
    );
  }

  Widget _buildQuartileRow(String quartile, String ratio, String count, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              quartile,
              style: const TextStyle(fontWeight: FontWeight.w500),
            ),
          ),
          Text(
            ratio,
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
          ),
          const SizedBox(width: 16),
          Text(
            count,
            style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _buildRiskAccumulationCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Market Risk Accumulation',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 16),
          _buildAccumulationRow('Cyber - US', 0.85, 'GBP 4.2B'),
          _buildAccumulationRow('Hurricane - Florida', 0.72, 'GBP 3.6B'),
          _buildAccumulationRow('Earthquake - CA', 0.58, 'GBP 2.9B'),
          _buildAccumulationRow('Terrorism - UK', 0.45, 'GBP 2.2B'),
        ],
      ),
    );
  }

  Widget _buildAccumulationRow(String risk, double utilization, String amount) {
    Color color;
    if (utilization > 0.8) {
      color = Colors.red;
    } else if (utilization > 0.6) {
      color = Colors.orange;
    } else {
      color = Colors.green;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(risk, style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 13)),
              Text(amount, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: utilization,
                    minHeight: 8,
                    backgroundColor: Colors.grey.shade200,
                    valueColor: AlwaysStoppedAnimation(color),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Text(
                '${(utilization * 100).toInt()}%',
                style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 12),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ==================== DIALOGS & SHEETS ====================
  void _showSyndicateDetails(Map<String, dynamic> syndicate) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        minChildSize: 0.5,
        maxChildSize: 0.95,
        builder: (context, scrollController) => Container(
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
          ),
          child: SingleChildScrollView(
            controller: scrollController,
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Center(
                    child: Container(
                      width: 40,
                      height: 4,
                      decoration: BoxDecoration(
                        color: Colors.grey.shade300,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Row(
                    children: [
                      Container(
                        width: 60,
                        height: 60,
                        decoration: BoxDecoration(
                          color: _getStatusColor(syndicate['status']).withAlpha(25),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Center(
                          child: Text(
                            syndicate['number'],
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 18,
                              color: _getStatusColor(syndicate['status']),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              syndicate['name'],
                              style: const TextStyle(
                                fontSize: 20,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            Text(
                              syndicate['managing_agent'],
                              style: const TextStyle(
                                fontSize: 14,
                                color: AppTheme.textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),
                  const Text(
                    'Quick Actions',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildActionButton('View Details', Icons.visibility, () {
                          Navigator.pop(context);
                          context.go('/lloyds');
                        }),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildActionButton('Compliance', Icons.verified_user, () {}),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: _buildActionButton('Placements', Icons.assignment, () {}),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildActionButton('Contact', Icons.email, () {}),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),
                  const Text(
                    'Key Metrics',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 12),
                  _buildDetailRow('GWP YTD', 'GBP ${((syndicate['gwp_ytd'] as num) / 1e6).toStringAsFixed(0)}M'),
                  _buildDetailRow('Capacity', 'GBP ${((syndicate['capacity'] as num) / 1e6).toStringAsFixed(0)}M'),
                  _buildDetailRow('Combined Ratio', '${syndicate['combined_ratio']}%'),
                  _buildDetailRow('Active Placements', '${syndicate['placements_active']}'),
                  _buildDetailRow('Compliance Score', '${syndicate['compliance_score']}%'),
                  const SizedBox(height: 24),
                  const Text(
                    'Business Classes',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: (syndicate['classes'] as List).map((c) =>
                      Chip(
                        label: Text(c, style: const TextStyle(fontSize: 12)),
                        backgroundColor: Colors.grey.shade100,
                      ),
                    ).toList(),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildActionButton(String label, IconData icon, VoidCallback onTap) {
    return Material(
      color: Colors.grey.shade100,
      borderRadius: BorderRadius.circular(8),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 18, color: AppTheme.textSecondary),
              const SizedBox(width: 8),
              Text(label, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: AppTheme.textSecondary)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  void _showNotifications() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Notifications',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            _buildNotificationItem(
              'Compliance Alert',
              'Syndicate 2791 compliance score dropped below 80%',
              '5 mins ago',
              Colors.red,
            ),
            _buildNotificationItem(
              'Capacity Update',
              'Market cyber capacity utilization at 85%',
              '1 hour ago',
              Colors.orange,
            ),
            _buildNotificationItem(
              'New Syndicate',
              'Syndicate 4521 application received',
              '3 hours ago',
              Colors.blue,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNotificationItem(String title, String message, String time, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
                Text(message, style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
              ],
            ),
          ),
          Text(time, style: const TextStyle(fontSize: 11, color: AppTheme.textHint)),
        ],
      ),
    );
  }
}
