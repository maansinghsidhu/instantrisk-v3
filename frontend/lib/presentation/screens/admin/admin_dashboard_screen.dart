import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../core/services/admin_panel_service.dart';

/// Admin panel dashboard: stats, user list, billing tile, audit log link.
class AdminDashboardScreen extends StatefulWidget {
  const AdminDashboardScreen({super.key});

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen>
    with SingleTickerProviderStateMixin {
  final AdminPanelService _svc = AdminPanelService();
  late TabController _tabController;

  Map<String, dynamic>? _stats;
  Map<String, dynamic>? _billing;
  List<Map<String, dynamic>> _users = [];
  bool _isLoading = true;
  String? _error;
  String _search = '';
  String? _statusFilter;
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadAll();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadAll() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        _svc.getStats(),
        _svc.getBillingSummary(),
        _svc.listUsers(statusFilter: _statusFilter, search: _search),
      ]);
      if (!mounted) return;
      setState(() {
        _stats = results[0];
        _billing = results[1];
        _users = List<Map<String, dynamic>>.from(results[2]['users'] ?? []);
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _error = e.toString();
      });
    }
  }

  Future<void> _reloadUsers() async {
    try {
      final r = await _svc.listUsers(
        statusFilter: _statusFilter,
        search: _search,
      );
      if (!mounted) return;
      setState(() {
        _users = List<Map<String, dynamic>>.from(r['users'] ?? []);
      });
    } catch (e) {
      if (!mounted) return;
      _showSnack('Failed to load users: $e', isError: true);
    }
  }

  void _showSnack(String msg, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: isError ? Colors.red : Colors.green,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Admin Panel'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadAll,
            tooltip: 'Refresh',
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(icon: Icon(Icons.dashboard), text: 'Overview'),
            Tab(icon: Icon(Icons.people), text: 'Users'),
            Tab(icon: Icon(Icons.attach_money), text: 'Billing'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.error_outline, size: 64, color: Colors.red),
                        const SizedBox(height: 16),
                        Text(_error!, textAlign: TextAlign.center),
                        const SizedBox(height: 16),
                        ElevatedButton.icon(
                          onPressed: _loadAll,
                          icon: const Icon(Icons.refresh),
                          label: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildOverviewTab(),
                    _buildUsersTab(),
                    _buildBillingTab(),
                  ],
                ),
    );
  }

  Widget _buildOverviewTab() {
    final s = _stats ?? {};
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _statCard('Total users', s['total_users']?.toString() ?? '0', Icons.people, Colors.blue),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(child: _statCard('Active', s['active_users']?.toString() ?? '0', Icons.check_circle, Colors.green)),
            const SizedBox(width: 12),
            Expanded(child: _statCard('Pending', s['pending_approvals']?.toString() ?? '0', Icons.hourglass_top, Colors.orange)),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(child: _statCard('Rejected', s['rejected_users']?.toString() ?? '0', Icons.cancel, Colors.red)),
            const SizedBox(width: 12),
            Expanded(child: _statCard('2FA enabled', s['users_with_2fa']?.toString() ?? '0', Icons.security, Colors.purple)),
          ],
        ),
        const SizedBox(height: 24),
        const Text('Users by role', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        ..._buildRoleList((s['users_by_role'] as Map?)?.cast<String, dynamic>() ?? {}),
        const SizedBox(height: 24),
        const Text('Users by tier', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        ..._buildTierList((s['users_by_tier'] as Map?)?.cast<String, dynamic>() ?? {}),
        const SizedBox(height: 24),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => context.push('/admin/audit-log'),
                icon: const Icon(Icons.history),
                label: const Text('Audit log'),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildUsersTab() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            controller: _searchController,
            decoration: InputDecoration(
              hintText: 'Search email or name...',
              prefixIcon: const Icon(Icons.search),
              border: const OutlineInputBorder(),
              suffixIcon: _search.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear),
                      onPressed: () {
                        _searchController.clear();
                        setState(() => _search = '');
                        _reloadUsers();
                      },
                    )
                  : null,
            ),
            onSubmitted: (v) {
              setState(() => _search = v);
              _reloadUsers();
            },
          ),
        ),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Row(
            children: [
              _filterChip(null, 'All'),
              _filterChip('pending', 'Pending'),
              _filterChip('approved', 'Approved'),
              _filterChip('rejected', 'Rejected'),
              _filterChip('active', 'Active'),
              _filterChip('inactive', 'Inactive'),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: _users.isEmpty
              ? const Center(child: Text('No users match.'))
              : RefreshIndicator(
                  onRefresh: _reloadUsers,
                  child: ListView.separated(
                    itemCount: _users.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (_, i) => _userTile(_users[i]),
                  ),
                ),
        ),
      ],
    );
  }

  Widget _filterChip(String? value, String label) {
    final selected = _statusFilter == value;
    return Padding(
      padding: const EdgeInsets.only(right: 6),
      child: FilterChip(
        label: Text(label),
        selected: selected,
        onSelected: (_) {
          setState(() => _statusFilter = value);
          _reloadUsers();
        },
      ),
    );
  }

  Widget _userTile(Map<String, dynamic> u) {
    final status = u['approval_status'] as String? ?? 'unknown';
    final isActive = u['is_active'] == true;
    final tier = u['subscription_tier'] as String? ?? '-';
    return ListTile(
      leading: CircleAvatar(
        backgroundColor: isActive ? Colors.green[100] : Colors.grey[300],
        child: Text(
          (() {
            final n = u['full_name'] as String?;
            return (n != null && n.isNotEmpty) ? n.substring(0, 1).toUpperCase() : '?';
          })(),
        ),
      ),
      title: Text(u['full_name']?.toString() ?? '?', style: const TextStyle(fontWeight: FontWeight.bold)),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(u['email']?.toString() ?? '?'),
          const SizedBox(height: 2),
          Row(
            children: [
              _statusBadge(status, isActive),
              const SizedBox(width: 6),
              _tierBadge(tier),
              const SizedBox(width: 6),
              _roleBadge(u['role']?.toString() ?? '-'),
            ],
          ),
        ],
      ),
      trailing: const Icon(Icons.chevron_right),
      onTap: () async {
        await context.push('/admin/user/${u['id']}');
        _loadAll();
      },
    );
  }

  Widget _buildBillingTab() {
    final b = _billing ?? {};
    final mrr = b['monthly_recurring_revenue_usd'] as int? ?? 0;
    final arr = b['annual_recurring_revenue_usd'] as int? ?? 0;
    final tiers = (b['users_by_tier'] as Map?)?.cast<String, dynamic>() ?? {};
    final statuses = (b['users_by_status'] as Map?)?.cast<String, dynamic>() ?? {};
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _statCard('MRR', '\$$mrr', Icons.trending_up, Colors.green),
        const SizedBox(height: 12),
        _statCard('ARR', '\$$arr', Icons.bar_chart, Colors.blue),
        const SizedBox(height: 12),
        _statCard('Trialing', '${b['trialing_users'] ?? 0}', Icons.timer, Colors.orange),
        const SizedBox(height: 12),
        _statCard('Payment failures', '${b['pending_payment_failures'] ?? 0}', Icons.warning, Colors.red),
        const SizedBox(height: 24),
        const Text('Users by tier', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        ..._buildTierList(tiers),
        const SizedBox(height: 24),
        const Text('Users by approval status', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        ..._buildStatusList(statuses),
        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.blue[50],
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: Colors.blue[200]!),
          ),
          child: const Row(
            children: [
              Icon(Icons.info_outline, color: Colors.blue),
              SizedBox(width: 12),
              Expanded(
                child: Text(
                  'Payment failures: requires Stripe (or equivalent) webhook integration. See W2 / W3-39 in the audit.',
                  style: TextStyle(fontSize: 12),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  // ===========================================================================
  // Small helpers
  // ===========================================================================

  Widget _statCard(String label, String value, IconData icon, Color color) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            CircleAvatar(
              backgroundColor: color.withOpacity(0.15),
              child: Icon(icon, color: color),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: TextStyle(color: Colors.grey[700], fontSize: 12)),
                  Text(value, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _buildRoleList(Map<String, dynamic> roles) {
    if (roles.isEmpty) return [const Text('No role data')];
    return roles.entries.map((e) {
      return ListTile(
        dense: true,
        title: Text(e.key),
        trailing: Text('${e.value}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
      );
    }).toList();
  }

  List<Widget> _buildTierList(Map<String, dynamic> tiers) {
    if (tiers.isEmpty) return [const Text('No subscription data')];
    return tiers.entries.map((e) {
      return ListTile(
        dense: true,
        title: Text(e.key),
        trailing: Text('${e.value}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
      );
    }).toList();
  }

  List<Widget> _buildStatusList(Map<String, dynamic> statuses) {
    if (statuses.isEmpty) return [const Text('No status data')];
    return statuses.entries.map((e) {
      return ListTile(
        dense: true,
        title: Text(e.key),
        trailing: Text('${e.value}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
      );
    }).toList();
  }

  Widget _statusBadge(String status, bool isActive) {
    Color color;
    switch (status) {
      case 'approved':
        color = Colors.green;
        break;
      case 'pending':
        color = Colors.orange;
        break;
      case 'rejected':
        color = Colors.red;
        break;
      default:
        color = Colors.grey;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        isActive ? status : '$status (inactive)',
        style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.bold),
      ),
    );
  }

  Widget _tierBadge(String tier) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: Colors.purple.withOpacity(0.15),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        tier,
        style: const TextStyle(color: Colors.purple, fontSize: 10, fontWeight: FontWeight.bold),
      ),
    );
  }

  Widget _roleBadge(String role) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: Colors.blue.withOpacity(0.15),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        role,
        style: const TextStyle(color: Colors.blue, fontSize: 10, fontWeight: FontWeight.bold),
      ),
    );
  }
}
