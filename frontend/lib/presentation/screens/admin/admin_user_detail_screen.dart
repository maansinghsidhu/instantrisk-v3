import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../core/services/admin_panel_service.dart';

/// Admin user detail: profile, subscription, usage, action buttons.
class AdminUserDetailScreen extends StatefulWidget {
  final String userId;
  const AdminUserDetailScreen({super.key, required this.userId});

  @override
  State<AdminUserDetailScreen> createState() => _AdminUserDetailScreenState();
}

class _AdminUserDetailScreenState extends State<AdminUserDetailScreen> {
  final AdminPanelService _svc = AdminPanelService();

  Map<String, dynamic>? _user;
  Map<String, dynamic>? _usage;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        _svc.getUserDetail(widget.userId),
        _svc.getUserUsage(widget.userId),
      ]);
      if (!mounted) return;
      setState(() {
        _user = results[0];
        _usage = results[1];
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

  void _showSnack(String msg, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: isError ? Colors.red : Colors.green,
      ),
    );
  }

  Future<void> _approve() async {
    final tier = await _showTierDialog();
    if (tier == null) return;
    try {
      await _svc.approveUser(widget.userId, subscriptionTier: tier);
      if (!mounted) return;
      _showSnack('User approved with $tier tier');
      _load();
    } catch (e) {
      if (!mounted) return;
      _showSnack(e.toString(), isError: true);
    }
  }

  Future<void> _reject() async {
    final reason = await _showTextDialog(
      title: 'Reject user',
      label: 'Reason',
      hint: 'Brief reason shown to the user',
    );
    if (reason == null) return;
    try {
      await _svc.rejectUser(widget.userId, reason: reason);
      if (!mounted) return;
      _showSnack('User rejected');
      _load();
    } catch (e) {
      if (!mounted) return;
      _showSnack(e.toString(), isError: true);
    }
  }

  Future<void> _changeTier() async {
    final tier = await _showTierDialog(initial: _user?['subscription_tier'] as String?);
    if (tier == null) return;
    try {
      await _svc.changeTier(widget.userId, subscriptionTier: tier);
      if (!mounted) return;
      _showSnack('Tier changed to $tier');
      _load();
    } catch (e) {
      if (!mounted) return;
      _showSnack(e.toString(), isError: true);
    }
  }

  Future<void> _deactivate() async {
    final reason = await _showTextDialog(
      title: 'Deactivate user',
      label: 'Reason (optional)',
      hint: 'Internal note',
      required: false,
    );
    if (reason == null) return;
    try {
      await _svc.deactivateUser(widget.userId, reason: reason.isEmpty ? null : reason);
      if (!mounted) return;
      _showSnack('User deactivated');
      _load();
    } catch (e) {
      if (!mounted) return;
      _showSnack(e.toString(), isError: true);
    }
  }

  Future<void> _reactivate() async {
    try {
      await _svc.reactivateUser(widget.userId);
      if (!mounted) return;
      _showSnack('User reactivated');
      _load();
    } catch (e) {
      if (!mounted) return;
      _showSnack(e.toString(), isError: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('User detail'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : _user == null
                  ? const Center(child: Text('User not found'))
                  : _buildBody(_user!, _usage),
    );
  }

  Widget _buildBody(Map<String, dynamic> u, Map<String, dynamic>? usage) {
    final isActive = u['is_active'] == true;
    final isPending = u['approval_status'] == 'pending';
    final fmt = DateFormat.yMMMd().add_jm();

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _section('Identity', [
          _row('Name', u['full_name']?.toString() ?? '-'),
          _row('Email', u['email']?.toString() ?? '-'),
          _row('Role', u['role']?.toString() ?? '-'),
          _row('User id', u['id']?.toString() ?? '-', mono: true),
        ]),
        const SizedBox(height: 16),
        _section('Account status', [
          _row('Approval', u['approval_status']?.toString() ?? '-'),
          _row('Active', isActive ? 'Yes' : 'No'),
          _row('Email verified', u['is_verified'] == true ? 'Yes' : 'No'),
          _row('2FA enabled', u['two_fa_enabled'] == true ? 'Yes' : 'No'),
          _row('Created', u['created_at'] != null ? fmt.format(DateTime.parse(u['created_at'])) : '-'),
          _row('Last login', u['last_login'] != null ? fmt.format(DateTime.parse(u['last_login'])) : 'Never'),
          if (u['approved_at'] != null)
            _row('Approved at', fmt.format(DateTime.parse(u['approved_at']))),
          if (u['approved_by'] != null)
            _row('Approved by', u['approved_by'].toString(), mono: true),
          if (u['rejection_reason'] != null)
            _row('Rejection reason', u['rejection_reason'].toString()),
        ]),
        const SizedBox(height: 16),
        _section('Subscription', [
          _row('Tier', u['subscription_tier']?.toString() ?? '-'),
          _row('Status', u['subscription_status']?.toString() ?? '-'),
          if (u['subscription_started_at'] != null)
            _row('Started', fmt.format(DateTime.parse(u['subscription_started_at']))),
          if (u['subscription_expires_at'] != null)
            _row('Expires', fmt.format(DateTime.parse(u['subscription_expires_at']))),
        ]),
        const SizedBox(height: 16),
        if (usage != null) _buildUsage(usage),
        const SizedBox(height: 24),
        _buildActions(u),
      ],
    );
  }

  Widget _buildUsage(Map<String, dynamic> u) {
    int pct(int used, int limit) {
      if (limit <= 0) return 0;
      return ((used / limit) * 100).clamp(0, 100).round();
    }

    Widget bar(String label, int used, int limit) {
      final p = pct(used, limit);
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(label, style: const TextStyle(fontWeight: FontWeight.w500)),
                Text('$used / $limit', style: TextStyle(color: Colors.grey[700])),
              ],
            ),
            const SizedBox(height: 4),
            LinearProgressIndicator(
              value: p / 100.0,
              backgroundColor: Colors.grey[200],
              color: p >= 90 ? Colors.red : p >= 70 ? Colors.orange : Colors.green,
            ),
          ],
        ),
      );
    }

    return _section('Usage (this month)', [
      bar('Assessments', u['monthly_assessments_used'] ?? 0, u['monthly_assessments_limit'] ?? 0),
      bar('Documents generated', u['monthly_documents_generated'] ?? 0, u['monthly_documents_limit'] ?? 0),
      bar('Chat messages', u['monthly_chat_messages_used'] ?? 0, u['monthly_chat_messages_limit'] ?? 0),
      const Divider(),
      _row('Lifetime assessments', '${u['lifetime_assessments'] ?? 0}'),
      _row('Lifetime documents', '${u['lifetime_documents'] ?? 0}'),
      _row('Lifetime chat messages', '${u['lifetime_chat_messages'] ?? 0}'),
      if (u['usage_reset_at'] != null)
        _row('Next reset', DateFormat.yMMMd().format(DateTime.parse(u['usage_reset_at']))),
    ]);
  }

  Widget _buildActions(Map<String, dynamic> u) {
    final isPending = u['approval_status'] == 'pending';
    final isActive = u['is_active'] == true;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (isPending) ...[
          ElevatedButton.icon(
            onPressed: _approve,
            icon: const Icon(Icons.check_circle),
            label: const Text('Approve user'),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: _reject,
            icon: const Icon(Icons.cancel, color: Colors.red),
            label: const Text('Reject user', style: TextStyle(color: Colors.red)),
            style: OutlinedButton.styleFrom(side: const BorderSide(color: Colors.red)),
          ),
          const SizedBox(height: 16),
        ],
        OutlinedButton.icon(
          onPressed: _changeTier,
          icon: const Icon(Icons.workspace_premium),
          label: const Text('Change subscription tier'),
        ),
        const SizedBox(height: 8),
        if (isActive)
          OutlinedButton.icon(
            onPressed: _deactivate,
            icon: const Icon(Icons.block, color: Colors.orange),
            label: const Text('Deactivate', style: TextStyle(color: Colors.orange)),
            style: OutlinedButton.styleFrom(side: const BorderSide(color: Colors.orange)),
          )
        else
          ElevatedButton.icon(
            onPressed: _reactivate,
            icon: const Icon(Icons.check),
            label: const Text('Reactivate'),
          ),
      ],
    );
  }

  // ===========================================================================
  // UI helpers
  // ===========================================================================

  Widget _section(String title, List<Widget> children) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            ...children,
          ],
        ),
      ),
    );
  }

  Widget _row(String label, String value, {bool mono = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 140, child: Text(label, style: TextStyle(color: Colors.grey[700]))),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontFamily: mono ? 'monospace' : null,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<String?> _showTierDialog({String? initial}) async {
    return showDialog<String>(
      context: context,
      builder: (ctx) {
        String selected = initial ?? 'basic';
        return StatefulBuilder(builder: (ctx, setSt) {
          return AlertDialog(
            title: const Text('Select subscription tier'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                _tierOpt(ctx, 'trial', 'Trial', '\$0 — GO/NO-GO only, 5 monthly assessments', selected, setSt),
                _tierOpt(ctx, 'basic', 'Basic', '\$99/mo — GO/NO-GO + details, 25 assessments', selected, setSt),
                _tierOpt(ctx, 'premium', 'Premium', '\$499/mo — All features, 100 assessments', selected, setSt),
              ],
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
              ElevatedButton(
                onPressed: () => Navigator.pop(ctx, selected),
                child: const Text('Apply'),
              ),
            ],
          );
        });
      },
    );
  }

  Widget _tierOpt(BuildContext ctx, String value, String title, String desc, String selected, void Function(void Function()) setSt) {
    final isSel = selected == value;
    return InkWell(
      onTap: () => setSt(() => selected = value),
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          border: Border.all(color: isSel ? Colors.blue : Colors.grey.shade300, width: isSel ? 2 : 1),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          children: [
            Icon(isSel ? Icons.radio_button_checked : Icons.radio_button_unchecked,
                color: isSel ? Colors.blue : Colors.grey),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
                  Text(desc, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<String?> _showTextDialog({
    required String title,
    required String label,
    required String hint,
    bool required = true,
  }) async {
    final controller = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: TextField(
          controller: controller,
          decoration: InputDecoration(labelText: label, hintText: hint),
          maxLines: 3,
          autofocus: true,
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () {
              final v = controller.text.trim();
              if (required && v.isEmpty) return;
              Navigator.pop(ctx, v);
            },
            child: const Text('Confirm'),
          ),
        ],
      ),
    );
  }
}
