import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../core/services/auth_service.dart';

/// Admin screen for managing user account approvals
class UserApprovalsScreen extends StatefulWidget {
  const UserApprovalsScreen({super.key});

  @override
  State<UserApprovalsScreen> createState() => _UserApprovalsScreenState();
}

class _UserApprovalsScreenState extends State<UserApprovalsScreen>
    with SingleTickerProviderStateMixin {
  final AuthService _authService = AuthService();
  late TabController _tabController;

  List<Map<String, dynamic>> _pendingUsers = [];
  List<Map<String, dynamic>> _allUsers = [];
  bool _isLoading = true;
  String? _error;
  String _searchQuery = '';
  final TextEditingController _searchController = TextEditingController();

  // Stats
  int _pendingCount = 0;
  int _approvedCount = 0;
  int _rejectedCount = 0;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      // Load pending users
      final pendingResponse = await _authService.get('/admin/pending-approvals');
      if (pendingResponse.statusCode == 200) {
        _pendingUsers = List<Map<String, dynamic>>.from(jsonDecode(pendingResponse.body));
        _pendingCount = _pendingUsers.length;
      }

      // Load all users (with optional email search)
      final searchParam = _searchQuery.trim().isNotEmpty
          ? '?search=${Uri.encodeComponent(_searchQuery.trim())}'
          : '';
      final allResponse = await _authService.get('/admin/users$searchParam');
      if (allResponse.statusCode == 200) {
        _allUsers = List<Map<String, dynamic>>.from(jsonDecode(allResponse.body));
        _approvedCount = _allUsers.where((u) => u['approval_status'] == 'approved').length;
        _rejectedCount = _allUsers.where((u) => u['approval_status'] == 'rejected').length;
      }

      setState(() {
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
        _error = 'Failed to load users: $e';
      });
    }
  }

  Future<void> _approveUser(Map<String, dynamic> user) async {
    final tier = await _showTierSelectionDialog();
    if (tier == null) return;

    try {
      final response = await _authService.post(
        '/admin/approve/${user['id']}?subscription_tier=$tier',
        body: {},
      );

      if (response.statusCode == 200) {
        _showSnackBar('User ${user['email']} approved with $tier tier', Colors.green);
        await _loadData();
      } else {
        final data = jsonDecode(response.body);
        _showSnackBar(data['detail'] ?? 'Failed to approve user', Colors.red);
      }
    } catch (e) {
      _showSnackBar('Error: $e', Colors.red);
    }
  }

  Future<void> _rejectUser(Map<String, dynamic> user) async {
    final reason = await _showRejectDialog();
    if (reason == null) return;

    try {
      final response = await _authService.post(
        '/admin/reject/${user['id']}',
        body: {'reason': reason},
      );

      if (response.statusCode == 200) {
        _showSnackBar('User ${user['email']} rejected', Colors.orange);
        await _loadData();
      } else {
        final data = jsonDecode(response.body);
        _showSnackBar(data['detail'] ?? 'Failed to reject user', Colors.red);
      }
    } catch (e) {
      _showSnackBar('Error: $e', Colors.red);
    }
  }

  Future<String?> _showTierSelectionDialog() async {
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Select Subscription Tier'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildTierOption(
              'basic',
              'Basic',
              'GO/NO-GO decisions, risk analysis, 25 monthly assessments',
              Colors.blue,
            ),
            const SizedBox(height: 12),
            _buildTierOption(
              'premium',
              'Premium',
              'All features including ClaimSense chat, document generation',
              Colors.purple,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
        ],
      ),
    );
  }

  Widget _buildTierOption(String value, String title, String description, Color color) {
    return InkWell(
      onTap: () => Navigator.pop(context, value),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          border: Border.all(color: color.withOpacity(0.3)),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: color.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(
                value == 'premium' ? Icons.workspace_premium : Icons.verified,
                color: color,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: TextStyle(fontWeight: FontWeight.bold, color: color)),
                  Text(description, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<String?> _showRejectDialog() async {
    final controller = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reject User'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Please provide a reason for rejection:'),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              maxLines: 3,
              decoration: const InputDecoration(
                hintText: 'Enter rejection reason...',
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              if (controller.text.trim().isNotEmpty) {
                Navigator.pop(context, controller.text.trim());
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Reject'),
          ),
        ],
      ),
    );
  }

  void _showSnackBar(String message, Color color) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: color,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('User Approvals'),
        actions: [
          IconButton(
            onPressed: _loadData,
            icon: const Icon(Icons.refresh),
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(kTextTabBarHeight + 56),
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                child: TextField(
                  controller: _searchController,
                  decoration: InputDecoration(
                    hintText: 'Search by email...',
                    prefixIcon: const Icon(Icons.search, size: 20),
                    suffixIcon: _searchQuery.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear, size: 18),
                            onPressed: () {
                              _searchController.clear();
                              setState(() => _searchQuery = '');
                              _loadData();
                            },
                          )
                        : null,
                    contentPadding: const EdgeInsets.symmetric(vertical: 8),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(24),
                      borderSide: BorderSide.none,
                    ),
                    filled: true,
                    isDense: true,
                  ),
                  onChanged: (v) {
                    setState(() => _searchQuery = v);
                    if (v.isEmpty || v.length >= 2) _loadData();
                  },
                  onSubmitted: (_) => _loadData(),
                ),
              ),
              TabBar(
                controller: _tabController,
                tabs: [
                  Tab(
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text('Pending'),
                        if (_pendingCount > 0) ...[
                          const SizedBox(width: 8),
                          _buildBadge(_pendingCount, Colors.orange),
                        ],
                      ],
                    ),
                  ),
                  Tab(
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text('Approved'),
                        const SizedBox(width: 8),
                        _buildBadge(_approvedCount, Colors.green),
                      ],
                    ),
                  ),
                  Tab(
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text('Rejected'),
                        if (_rejectedCount > 0) ...[
                          const SizedBox(width: 8),
                          _buildBadge(_rejectedCount, Colors.red),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.error_outline, size: 48, color: Colors.red[300]),
                      const SizedBox(height: 16),
                      Text(_error!, style: TextStyle(color: Colors.red[700])),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: _loadData,
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                )
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildPendingTab(),
                    _buildApprovedTab(),
                    _buildRejectedTab(),
                  ],
                ),
    );
  }

  Widget _buildBadge(int count, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        count.toString(),
        style: const TextStyle(
          color: Colors.white,
          fontSize: 12,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildPendingTab() {
    if (_pendingUsers.isEmpty) {
      return _buildEmptyState(
        Icons.check_circle_outline,
        'No Pending Approvals',
        'All user registrations have been processed.',
        Colors.green,
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _pendingUsers.length,
      itemBuilder: (context, index) {
        final user = _pendingUsers[index];
        return _buildPendingUserCard(user);
      },
    );
  }

  Widget _buildApprovedTab() {
    final approvedUsers = _allUsers.where((u) => u['approval_status'] == 'approved').toList();
    if (approvedUsers.isEmpty) {
      return _buildEmptyState(
        Icons.people_outline,
        'No Approved Users',
        'No users have been approved yet.',
        Colors.grey,
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: approvedUsers.length,
      itemBuilder: (context, index) {
        final user = approvedUsers[index];
        return _buildUserCard(user, Colors.green);
      },
    );
  }

  Widget _buildRejectedTab() {
    final rejectedUsers = _allUsers.where((u) => u['approval_status'] == 'rejected').toList();
    if (rejectedUsers.isEmpty) {
      return _buildEmptyState(
        Icons.block,
        'No Rejected Users',
        'No user registrations have been rejected.',
        Colors.grey,
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: rejectedUsers.length,
      itemBuilder: (context, index) {
        final user = rejectedUsers[index];
        return _buildUserCard(user, Colors.red);
      },
    );
  }

  Widget _buildEmptyState(IconData icon, String title, String subtitle, Color color) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 64, color: color.withOpacity(0.5)),
          const SizedBox(height: 16),
          Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text(subtitle, style: TextStyle(color: Colors.grey[600])),
        ],
      ),
    );
  }

  Widget _buildPendingUserCard(Map<String, dynamic> user) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  backgroundColor: Colors.orange.withOpacity(0.2),
                  child: Text(
                    (user['full_name'] ?? 'U')[0].toUpperCase(),
                    style: const TextStyle(
                      color: Colors.orange,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        user['full_name'] ?? 'Unknown',
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                        ),
                      ),
                      Text(
                        user['email'] ?? '',
                        style: TextStyle(color: Colors.grey[600], fontSize: 14),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.orange.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    user['role']?.toString().toUpperCase() ?? 'BROKER',
                    style: const TextStyle(
                      color: Colors.orange,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Icon(Icons.access_time, size: 16, color: Colors.grey[400]),
                const SizedBox(width: 4),
                Text(
                  'Registered ${_formatDate(user['created_at'])}',
                  style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _rejectUser(user),
                    icon: const Icon(Icons.close, size: 18),
                    label: const Text('Reject'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.red,
                      side: const BorderSide(color: Colors.red),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () => _approveUser(user),
                    icon: const Icon(Icons.check, size: 18),
                    label: const Text('Approve'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green,
                      foregroundColor: Colors.white,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildUserCard(Map<String, dynamic> user, Color statusColor) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: statusColor.withOpacity(0.2),
          child: Text(
            (user['full_name'] ?? 'U')[0].toUpperCase(),
            style: TextStyle(
              color: statusColor,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        title: Text(user['full_name'] ?? 'Unknown'),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(user['email'] ?? ''),
            const SizedBox(height: 4),
            Text(
              'Role: ${user['role']?.toString().toUpperCase() ?? 'BROKER'}',
              style: TextStyle(fontSize: 12, color: Colors.grey[500]),
            ),
          ],
        ),
        trailing: Icon(
          user['approval_status'] == 'approved' ? Icons.check_circle : Icons.cancel,
          color: statusColor,
        ),
        isThreeLine: true,
      ),
    );
  }

  String _formatDate(String? dateStr) {
    if (dateStr == null) return 'Unknown';
    try {
      final date = DateTime.parse(dateStr);
      final now = DateTime.now();
      final diff = now.difference(date);

      if (diff.inDays == 0) {
        return 'today';
      } else if (diff.inDays == 1) {
        return 'yesterday';
      } else if (diff.inDays < 7) {
        return '${diff.inDays} days ago';
      } else {
        return DateFormat('MMM d, yyyy').format(date);
      }
    } catch (e) {
      return dateStr;
    }
  }
}
