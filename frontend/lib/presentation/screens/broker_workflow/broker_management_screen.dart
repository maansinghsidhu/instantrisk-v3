import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/services/auth_service.dart';
import '../../../core/theme/app_theme.dart';

/// Broker directory/management screen for underwriters.
/// Lists all brokers with tabs for Active and Pending Approval,
/// and provides approve/reject actions for pending brokers.
class BrokerManagementScreen extends StatefulWidget {
  const BrokerManagementScreen({super.key});

  @override
  State<BrokerManagementScreen> createState() =>
      _BrokerManagementScreenState();
}

class _BrokerManagementScreenState extends State<BrokerManagementScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  List<dynamic> _brokers = [];
  bool _isLoading = true;
  String? _error;

  // Track in-flight approve/reject per broker ID
  final Set<String> _processingIds = {};

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadBrokers();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  // ── Data loading ──

  Future<void> _loadBrokers() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final response = await authService.get('/broker-portal/brokers');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _brokers = data is List ? data : (data['items'] ?? data['brokers'] ?? []);
          _isLoading = false;
        });
      } else {
        setState(() {
          _error = 'Failed to load brokers (${response.statusCode}).';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Connection error: $e';
        _isLoading = false;
      });
    }
  }

  Future<void> _onRefresh() async {
    await _loadBrokers();
  }

  // ── Filtered lists ──

  List<dynamic> get _activeBrokers => _brokers
      .where((b) =>
          (b['approval_status'] ?? '').toString().toLowerCase() == 'approved' ||
          (b['approval_status'] ?? '').toString().toLowerCase() == 'active')
      .toList();

  List<dynamic> get _pendingBrokers => _brokers
      .where((b) =>
          (b['approval_status'] ?? '').toString().toLowerCase() == 'pending')
      .toList();

  // ── Actions ──

  Future<void> _approveBroker(dynamic broker) async {
    final brokerId = (broker['id'] ?? broker['broker_id'] ?? '').toString();
    if (brokerId.isEmpty) return;

    setState(() => _processingIds.add(brokerId));

    try {
      final response = await authService.put(
        '/broker-portal/brokers/$brokerId/approve',
      );

      if (response.statusCode == 200) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
                'Broker ${broker['full_name'] ?? 'Unknown'} approved.'),
            backgroundColor: AppTheme.success,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
          ),
        );
        await _loadBrokers();
      } else {
        final detail = _parseError(response.body);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(detail),
            backgroundColor: AppTheme.danger,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error: $e'),
          backgroundColor: AppTheme.danger,
          behavior: SnackBarBehavior.floating,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      );
    } finally {
      if (mounted) setState(() => _processingIds.remove(brokerId));
    }
  }

  Future<void> _rejectBroker(dynamic broker) async {
    final brokerId = (broker['id'] ?? broker['broker_id'] ?? '').toString();
    if (brokerId.isEmpty) return;

    setState(() => _processingIds.add(brokerId));

    try {
      final response = await authService.put(
        '/broker-portal/brokers/$brokerId/reject',
      );

      if (response.statusCode == 200) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
                'Broker ${broker['full_name'] ?? 'Unknown'} rejected.'),
            backgroundColor: AppTheme.warning,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
          ),
        );
        await _loadBrokers();
      } else {
        final detail = _parseError(response.body);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(detail),
            backgroundColor: AppTheme.danger,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error: $e'),
          backgroundColor: AppTheme.danger,
          behavior: SnackBarBehavior.floating,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      );
    } finally {
      if (mounted) setState(() => _processingIds.remove(brokerId));
    }
  }

  String _parseError(String body) {
    try {
      final data = jsonDecode(body);
      return (data['detail'] ?? 'Operation failed.').toString();
    } catch (_) {
      return 'Operation failed.';
    }
  }

  // ── Helpers ──

  Color _statusColor(String status) {
    switch (status.toLowerCase()) {
      case 'approved':
      case 'active':
        return AppTheme.success;
      case 'pending':
        return Colors.orange;
      case 'rejected':
        return AppTheme.danger;
      default:
        return Colors.grey;
    }
  }

  String _statusLabel(String status) {
    switch (status.toLowerCase()) {
      case 'approved':
        return 'Approved';
      case 'active':
        return 'Active';
      case 'pending':
        return 'Pending';
      case 'rejected':
        return 'Rejected';
      default:
        return status.replaceAll('_', ' ');
    }
  }

  // ── Build ──

  @override
  Widget build(BuildContext context) {
    final pendingCount = _pendingBrokers.length;

    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceOf(context),
        elevation: 0,
        title: Text(
          'Broker Management',
          style: TextStyle(
            color: AppTheme.text1(context),
            fontWeight: FontWeight.w600,
            fontSize: 17,
            letterSpacing: -0.2,
          ),
        ),
        iconTheme: IconThemeData(color: AppTheme.text1(context)),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadBrokers,
            tooltip: 'Refresh',
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(49),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TabBar(
                controller: _tabController,
                labelColor: AppTheme.primaryDark,
                unselectedLabelColor: AppTheme.text2(context),
                indicatorColor: AppTheme.primaryDark,
                indicatorWeight: 2.5,
                labelStyle: const TextStyle(
                  fontFamily: 'Inter',
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
                unselectedLabelStyle: const TextStyle(
                  fontFamily: 'Inter',
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                ),
                tabs: [
                  const Tab(text: 'Active Brokers'),
                  Tab(
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text('Pending Approval'),
                        if (pendingCount > 0) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 7, vertical: 2),
                            decoration: BoxDecoration(
                              color: Colors.orange,
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Text(
                              pendingCount.toString(),
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
              Container(
                height: 1,
                color: AppTheme.borderOf(context),
              ),
            ],
          ),
        ),
      ),
      body: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_isLoading) {
      return Center(
        child: CircularProgressIndicator(
          color: AppTheme.primaryDark,
          strokeWidth: 2.5,
        ),
      );
    }

    if (_error != null) {
      return _buildErrorState(context);
    }

    return TabBarView(
      controller: _tabController,
      children: [
        _buildBrokerList(context, _activeBrokers, isActive: true),
        _buildBrokerList(context, _pendingBrokers, isActive: false),
      ],
    );
  }

  // ── Error state ──

  Widget _buildErrorState(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 56, color: AppTheme.danger),
            const SizedBox(height: 16),
            Text(
              'Something went wrong',
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w600,
                color: AppTheme.text1(context),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              _error ?? '',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 14, color: AppTheme.text2(context)),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _loadBrokers,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  // ── Broker list (shared for both tabs) ──

  Widget _buildBrokerList(BuildContext context, List<dynamic> brokers,
      {required bool isActive}) {
    if (brokers.isEmpty) {
      return _buildEmptyState(
        context,
        icon: isActive ? Icons.people_outline : Icons.hourglass_empty,
        title: isActive ? 'No Active Brokers' : 'No Pending Approvals',
        subtitle: isActive
            ? 'There are no approved brokers yet.'
            : 'All broker registrations have been processed.',
      );
    }

    return RefreshIndicator(
      color: AppTheme.primaryDark,
      backgroundColor: AppTheme.surfaceOf(context),
      onRefresh: _onRefresh,
      child: ListView.builder(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        itemCount: brokers.length,
        itemBuilder: (ctx, index) =>
            _buildBrokerCard(context, brokers[index]),
      ),
    );
  }

  // ── Empty state ──

  Widget _buildEmptyState(BuildContext context,
      {required IconData icon,
      required String title,
      required String subtitle}) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 64,
              color: AppTheme.text2(context).withOpacity(0.4),
            ),
            const SizedBox(height: 16),
            Text(
              title,
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w600,
                color: AppTheme.text1(context),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              subtitle,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                color: AppTheme.text2(context),
              ),
            ),
            const SizedBox(height: 24),
            OutlinedButton.icon(
              onPressed: _onRefresh,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('Refresh'),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppTheme.text1(context),
                side: BorderSide(color: AppTheme.borderOf(context)),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Broker card ──

  Widget _buildBrokerCard(BuildContext context, dynamic broker) {
    final String brokerId =
        (broker['id'] ?? broker['broker_id'] ?? '').toString();
    final String fullName =
        (broker['full_name'] ?? 'Unknown Broker').toString();
    final String email = (broker['email'] ?? '').toString();
    final String approvalStatus =
        (broker['approval_status'] ?? 'pending').toString();
    final int submissionCount =
        (broker['submission_count'] ?? 0) is int
            ? broker['submission_count'] ?? 0
            : int.tryParse(broker['submission_count'].toString()) ?? 0;
    final int boundCount =
        (broker['bound_count'] ?? 0) is int
            ? broker['bound_count'] ?? 0
            : int.tryParse(broker['bound_count'].toString()) ?? 0;

    final bool isPending = approvalStatus.toLowerCase() == 'pending';
    final bool isProcessing = _processingIds.contains(brokerId);
    final Color sColor = _statusColor(approvalStatus);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: AppTheme.borderOf(context),
          width: 0.5,
        ),
        boxShadow: AppTheme.isDark(context) ? null : AppTheme.subtleShadow,
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Row 1: Avatar + name + status badge ──
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CircleAvatar(
                  radius: 20,
                  backgroundColor: sColor.withOpacity(0.15),
                  child: Text(
                    fullName.isNotEmpty ? fullName[0].toUpperCase() : 'B',
                    style: TextStyle(
                      color: sColor,
                      fontWeight: FontWeight.w700,
                      fontSize: 16,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        fullName,
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text1(context),
                          letterSpacing: -0.1,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      if (email.isNotEmpty) ...[
                        const SizedBox(height: 2),
                        Text(
                          email,
                          style: TextStyle(
                            fontSize: 13,
                            color: AppTheme.text2(context),
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: sColor.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _statusLabel(approvalStatus),
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: sColor,
                    ),
                  ),
                ),
              ],
            ),

            const SizedBox(height: 12),

            // ── Row 2: Stats chips ──
            Row(
              children: [
                _buildStatChip(
                  context,
                  icon: Icons.description_outlined,
                  label: '$submissionCount submissions',
                ),
                const SizedBox(width: 10),
                _buildStatChip(
                  context,
                  icon: Icons.check_circle_outline,
                  label: '$boundCount bound',
                  color: boundCount > 0 ? AppTheme.success : null,
                ),
              ],
            ),

            // ── Row 3: Approve / Reject buttons for pending ──
            if (isPending) ...[
              const SizedBox(height: 14),
              Divider(color: AppTheme.borderOf(context), height: 1),
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed:
                          isProcessing ? null : () => _rejectBroker(broker),
                      icon: isProcessing
                          ? SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: AppTheme.danger,
                              ),
                            )
                          : Icon(Icons.close, size: 16, color: AppTheme.danger),
                      label: Text(
                        'Reject',
                        style: TextStyle(color: AppTheme.danger),
                      ),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppTheme.danger,
                        side: BorderSide(color: AppTheme.danger.withOpacity(0.5)),
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed:
                          isProcessing ? null : () => _approveBroker(broker),
                      icon: isProcessing
                          ? const SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Icon(Icons.check, size: 16),
                      label: const Text('Approve'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.success,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10),
                        ),
                        textStyle: const TextStyle(
                          fontFamily: 'Inter',
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  // ── Stat chip ──

  Widget _buildStatChip(BuildContext context,
      {required IconData icon, required String label, Color? color}) {
    final c = color ?? AppTheme.text2(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: AppTheme.isDark(context)
            ? AppTheme.darkCard
            : AppTheme.surfaceVariant,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: c),
          const SizedBox(width: 5),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: c,
            ),
          ),
        ],
      ),
    );
  }
}
