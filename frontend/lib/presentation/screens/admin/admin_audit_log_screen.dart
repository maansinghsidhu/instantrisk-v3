import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../core/services/admin_panel_service.dart';

/// Admin audit log viewer. Shows admin actions (approve, reject, tier
/// change, deactivate, reactivate) across the platform.
class AdminAuditLogScreen extends StatefulWidget {
  const AdminAuditLogScreen({super.key});

  @override
  State<AdminAuditLogScreen> createState() => _AdminAuditLogScreenState();
}

class _AdminAuditLogScreenState extends State<AdminAuditLogScreen> {
  final AdminPanelService _svc = AdminPanelService();
  List<Map<String, dynamic>> _entries = [];
  bool _isLoading = true;
  String? _error;
  String? _actionFilter;
  DateTimeRange? _dateRange;
  int _offset = 0;
  int _total = 0;
  static const int _limit = 50;

  static const Map<String, String> _actionLabels = {
    'user.approve': 'Approved user',
    'user.reject': 'Rejected user',
    'user.deactivate': 'Deactivated user',
    'user.reactivate': 'Reactivated user',
    'user.tier_change': 'Changed tier',
    'user.role_change': 'Changed role',
    'user.two_fa_reset': 'Reset 2FA',
  };

  @override
  void initState() {
    super.initState();
    _load(reset: true);
  }

  Future<void> _load({bool reset = false}) async {
    if (reset) {
      _offset = 0;
      _entries = [];
    }
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final r = await _svc.listAuditLog(
        action: _actionFilter,
        since: _dateRange?.start,
        limit: _limit,
        offset: _offset,
      );
      if (!mounted) return;
      setState(() {
        _entries = List<Map<String, dynamic>>.from(r['entries'] ?? []);
        _total = r['total'] as int? ?? 0;
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

  Future<void> _pickDateRange() async {
    final now = DateTime.now();
    final picked = await showDateRangePicker(
      context: context,
      firstDate: now.subtract(const Duration(days: 365)),
      lastDate: now,
      initialDateRange: _dateRange,
    );
    if (picked != null) {
      setState(() => _dateRange = picked);
      _load(reset: true);
    }
  }

  void _clearFilters() {
    setState(() {
      _actionFilter = null;
      _dateRange = null;
    });
    _load(reset: true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Audit log'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: () => _load(reset: true)),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<String?>(
                    value: _actionFilter,
                    decoration: const InputDecoration(
                      labelText: 'Action',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    items: [
                      const DropdownMenuItem(value: null, child: Text('All actions')),
                      ..._actionLabels.entries.map(
                        (e) => DropdownMenuItem(value: e.key, child: Text('${e.value}  (${e.key})')),
                      ),
                    ],
                    onChanged: (v) {
                      setState(() => _actionFilter = v);
                      _load(reset: true);
                    },
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon: const Icon(Icons.date_range),
                  tooltip: 'Date range',
                  onPressed: _pickDateRange,
                ),
                IconButton(
                  icon: const Icon(Icons.clear),
                  tooltip: 'Clear filters',
                  onPressed: _clearFilters,
                ),
              ],
            ),
          ),
          if (_dateRange != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Chip(
                  label: Text(
                    '${DateFormat.yMMMd().format(_dateRange!.start)} – ${DateFormat.yMMMd().format(_dateRange!.end)}',
                    style: const TextStyle(fontSize: 12),
                  ),
                  onDeleted: () {
                    setState(() => _dateRange = null);
                    _load(reset: true);
                  },
                ),
              ),
            ),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            child: Row(
              children: [
                Text('$_total entries',
                    style: TextStyle(color: Colors.grey[700], fontSize: 12)),
                const Spacer(),
                if (_offset > 0)
                  TextButton(
                    onPressed: () {
                      setState(() => _offset -= _limit);
                      _load();
                    },
                    child: const Text('Prev'),
                  ),
                if (_entries.length == _limit)
                  TextButton(
                    onPressed: () {
                      setState(() => _offset += _limit);
                      _load();
                    },
                    child: const Text('Next'),
                  ),
              ],
            ),
          ),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(child: Text(_error!))
                    : _entries.isEmpty
                        ? const Center(child: Text('No entries match.'))
                        : ListView.separated(
                            itemCount: _entries.length,
                            separatorBuilder: (_, __) => const Divider(height: 1),
                            itemBuilder: (_, i) => _entryTile(_entries[i]),
                          ),
          ),
        ],
      ),
    );
  }

  Widget _entryTile(Map<String, dynamic> e) {
    final action = e['action']?.toString() ?? '-';
    final label = _actionLabels[action] ?? action;
    final fmt = DateFormat.yMMMd().add_jms();
    final ts = e['created_at'] != null
        ? fmt.format(DateTime.parse(e['created_at']).toLocal())
        : '-';
    final details = e['details'] as Map<String, dynamic>?;
    final adminEmail = e['admin_email']?.toString() ?? 'unknown';
    final targetEmail = e['target_user_email']?.toString();

    return ExpansionTile(
      leading: Icon(_actionIcon(action), color: _actionColor(action)),
      title: Text(label, style: const TextStyle(fontWeight: FontWeight.bold)),
      subtitle: Text('$ts · $adminEmail'),
      childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      children: [
        if (targetEmail != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: Row(
              children: [
                const SizedBox(width: 100, child: Text('Target:')),
                Expanded(child: Text(targetEmail, style: const TextStyle(fontWeight: FontWeight.w500))),
              ],
            ),
          ),
        if (e['ip_address'] != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: Row(
              children: [
                const SizedBox(width: 100, child: Text('IP:')),
                Expanded(child: Text(e['ip_address'].toString(), style: const TextStyle(fontFamily: 'monospace'))),
              ],
            ),
          ),
        if (details != null && details.isNotEmpty) ...[
          const SizedBox(height: 8),
          const Text('Details:', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.grey[100],
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              const JsonEncoder.withIndent('  ').convert(details),
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
            ),
          ),
        ],
      ],
    );
  }

  IconData _actionIcon(String action) {
    if (action == 'user.approve') return Icons.check_circle;
    if (action == 'user.reject') return Icons.cancel;
    if (action == 'user.deactivate') return Icons.block;
    if (action == 'user.reactivate') return Icons.check;
    if (action == 'user.tier_change') return Icons.workspace_premium;
    if (action == 'user.role_change') return Icons.swap_horiz;
    if (action == 'user.two_fa_reset') return Icons.security;
    return Icons.history;
  }

  Color _actionColor(String action) {
    if (action == 'user.approve' || action == 'user.reactivate') return Colors.green;
    if (action == 'user.reject' || action == 'user.deactivate') return Colors.red;
    if (action == 'user.tier_change' || action == 'user.role_change') return Colors.purple;
    if (action == 'user.two_fa_reset') return Colors.orange;
    return Colors.grey;
  }
}
