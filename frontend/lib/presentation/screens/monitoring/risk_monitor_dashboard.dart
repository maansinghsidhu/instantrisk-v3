import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/monitoring_service.dart';
import '../../../core/services/auth_service.dart';
import 'dart:convert';

/// RiskMonitorDashboard - Comprehensive 24/7 risk monitoring with expandable alerts,
/// LOB breakdown, top risks, news, and breach monitoring.
class RiskMonitorDashboard extends StatefulWidget {
  const RiskMonitorDashboard({super.key});

  @override
  State<RiskMonitorDashboard> createState() => _RiskMonitorDashboardState();
}

class _RiskMonitorDashboardState extends State<RiskMonitorDashboard>
    with SingleTickerProviderStateMixin {
  Map<String, dynamic> _summary = {};
  List<Map<String, dynamic>> _alerts = [];
  List<Map<String, dynamic>> _newsAlerts = [];
  List<Map<String, dynamic>> _assessments = [];
  bool _isLoading = true;
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 5, vsync: this);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    try {
      final results = await Future.wait([
        monitoringService.getDashboardSummary(),
        monitoringService.getAlerts(limit: 50),
        monitoringService.getNewsAlerts(limit: 20),
        _fetchAssessments(),
      ]);
      if (mounted) {
        setState(() {
          _summary = results[0] as Map<String, dynamic>;
          _alerts = results[1] as List<Map<String, dynamic>>;
          _newsAlerts = results[2] as List<Map<String, dynamic>>;
          _assessments = results[3] as List<Map<String, dynamic>>;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<List<Map<String, dynamic>>> _fetchAssessments() async {
    try {
      final r = await authService.get('/assessments/?page=1&page_size=100');
      if (r.statusCode == 200) {
        final data = jsonDecode(r.body);
        final items = data['items'] ?? data;
        return List<Map<String, dynamic>>.from(items is List ? items : []);
      }
    } catch (_) {}
    return [];
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceOf(context),
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: AppTheme.text1(context)),
          onPressed: () => context.go('/home'),
        ),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                color: AppTheme.danger.withOpacity(0.1),
                borderRadius: BorderRadius.circular(6),
              ),
              child: const Icon(Icons.shield, size: 18, color: AppTheme.danger),
            ),
            const SizedBox(width: 8),
            Text('Risk Monitor',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: AppTheme.text1(context)),
            ),
            const SizedBox(width: 8),
            Container(
              width: 8, height: 8,
              decoration: const BoxDecoration(color: AppTheme.success, shape: BoxShape.circle),
            ),
          ],
        ),
        actions: [
          IconButton(icon: Icon(Icons.refresh, color: AppTheme.text1(context)), onPressed: _loadData, tooltip: 'Refresh'),
          const SizedBox(width: 8),
        ],
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          labelColor: AppTheme.primaryDark,
          unselectedLabelColor: AppTheme.text2(context),
          indicatorColor: AppTheme.primaryDark,
          labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
          tabs: const [
            Tab(text: 'Overview'),
            Tab(text: 'Alerts'),
            Tab(text: 'By LOB'),
            Tab(text: 'News'),
            Tab(text: 'Breaches'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                _SummaryBar(summary: _summary),
                Expanded(
                  child: TabBarView(
                    controller: _tabController,
                    children: [
                      _OverviewTab(summary: _summary, alerts: _alerts, assessments: _assessments),
                      _AlertsTab(alerts: _alerts, onRefresh: _loadData),
                      _LobTab(alerts: _alerts, assessments: _assessments),
                      _NewsTab(newsAlerts: _newsAlerts),
                      _BreachesTab(summary: _summary, assessments: _assessments),
                    ],
                  ),
                ),
              ],
            ),
    );
  }
}

// ─── SUMMARY BAR ───
class _SummaryBar extends StatelessWidget {
  final Map<String, dynamic> summary;
  const _SummaryBar({required this.summary});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      color: AppTheme.surfaceOf(context),
      child: Row(
        children: [
          _Chip('Critical', summary['critical'] ?? 0, const Color(0xFF7C3AED), context),
          const SizedBox(width: 6),
          _Chip('High', summary['high'] ?? 0, AppTheme.danger, context),
          const SizedBox(width: 6),
          _Chip('Medium', summary['medium'] ?? 0, AppTheme.warning, context),
          const SizedBox(width: 6),
          _Chip('Low', summary['low'] ?? 0, AppTheme.info, context),
          const SizedBox(width: 6),
          _Chip('Total', summary['total'] ?? 0, AppTheme.primaryDark, context),
        ],
      ),
    );
  }

  Widget _Chip(String label, dynamic count, Color color, BuildContext ctx) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withOpacity(0.2)),
        ),
        child: Column(
          children: [
            Text('$count', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: color)),
            Text(label, style: TextStyle(fontSize: 9, color: color, fontWeight: FontWeight.w500)),
          ],
        ),
      ),
    );
  }
}

// ─── OVERVIEW TAB ───
class _OverviewTab extends StatelessWidget {
  final Map<String, dynamic> summary;
  final List<Map<String, dynamic>> alerts;
  final List<Map<String, dynamic>> assessments;
  const _OverviewTab({required this.summary, required this.alerts, required this.assessments});

  @override
  Widget build(BuildContext context) {
    // Top risks = critical + high alerts
    final topRisks = alerts.where((a) {
      final sev = (a['severity'] ?? '').toString().toLowerCase();
      return sev == 'critical' || sev == 'high';
    }).take(5).toList();

    // Alert type breakdown
    final typeBreakdown = <String, int>{};
    for (final a in alerts) {
      final type = _formatAlertType(a['alert_type']?.toString() ?? 'unknown');
      typeBreakdown[type] = (typeBreakdown[type] ?? 0) + 1;
    }
    final sortedTypes = typeBreakdown.entries.toList()..sort((a, b) => b.value.compareTo(a.value));

    return RefreshIndicator(
      onRefresh: () async {},
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Overview explanation
          _SectionCard(
            context: context,
            icon: Icons.info_outline,
            iconColor: AppTheme.info,
            title: 'Risk Monitoring Overview',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'InstantRisk continuously monitors your portfolio against global threats including cyber breaches (HIBP), '
                  'natural disasters (USGS, NOAA), regulatory changes (FCA, PRA), sanctions (OFAC), and emerging risks.',
                  style: TextStyle(fontSize: 13, color: AppTheme.text2(context), height: 1.5),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    _StatPill(context, 'Assessments', '${assessments.length}', AppTheme.primaryDark),
                    const SizedBox(width: 8),
                    _StatPill(context, 'Active Alerts', '${alerts.length}', AppTheme.danger),
                    const SizedBox(width: 8),
                    _StatPill(context, 'Monitoring', summary['monitoring_active'] == true ? 'Active' : 'Paused', AppTheme.success),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Top Risks
          _SectionCard(
            context: context,
            icon: Icons.warning_amber_rounded,
            iconColor: AppTheme.danger,
            title: 'Top Risks (${topRisks.length})',
            child: topRisks.isEmpty
              ? Text('No critical or high-severity risks detected.', style: TextStyle(fontSize: 13, color: AppTheme.text2(context)))
              : Column(
                  children: topRisks.map((alert) => _ExpandableRisk(alert: alert)).toList(),
                ),
          ),
          const SizedBox(height: 16),

          // Alert Type Breakdown
          _SectionCard(
            context: context,
            icon: Icons.pie_chart_outline,
            iconColor: AppTheme.warning,
            title: 'Alert Breakdown by Type',
            child: Column(
              children: sortedTypes.take(8).map((entry) {
                final pct = alerts.isNotEmpty ? (entry.value / alerts.length * 100).toStringAsFixed(1) : '0';
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    children: [
                      Expanded(flex: 3, child: Text(entry.key, style: TextStyle(fontSize: 12, color: AppTheme.text1(context)))),
                      Expanded(
                        flex: 5,
                        child: LinearProgressIndicator(
                          value: alerts.isNotEmpty ? entry.value / alerts.length : 0,
                          backgroundColor: AppTheme.borderOf(context),
                          valueColor: AlwaysStoppedAnimation(AppTheme.primaryDark),
                          minHeight: 6,
                          borderRadius: BorderRadius.circular(3),
                        ),
                      ),
                      const SizedBox(width: 8),
                      SizedBox(
                        width: 50,
                        child: Text('${entry.value} ($pct%)', style: TextStyle(fontSize: 11, color: AppTheme.text2(context))),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _StatPill(BuildContext ctx, String label, String value, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 6),
        decoration: BoxDecoration(color: color.withOpacity(0.08), borderRadius: BorderRadius.circular(8)),
        child: Column(
          children: [
            Text(value, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: color)),
            Text(label, style: TextStyle(fontSize: 10, color: color)),
          ],
        ),
      ),
    );
  }
}

// ─── EXPANDABLE RISK ITEM ───
class _ExpandableRisk extends StatelessWidget {
  final Map<String, dynamic> alert;
  const _ExpandableRisk({required this.alert});

  @override
  Widget build(BuildContext context) {
    final severity = (alert['severity'] ?? 'medium').toString().toLowerCase();
    final color = _severityColor(severity);
    final type = _formatAlertType(alert['alert_type']?.toString() ?? '');
    final message = alert['message']?.toString() ?? 'Risk alert';
    final source = alert['source']?.toString() ?? '';
    final companyName = alert['company_name']?.toString() ?? '';
    final detected = alert['detected_at']?.toString() ?? alert['created_at']?.toString() ?? '';

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(color: color.withOpacity(0.3)),
      ),
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 0),
        childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
        leading: Container(
          padding: const EdgeInsets.all(6),
          decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(8)),
          child: Icon(_alertTypeIcon(alert['alert_type']?.toString() ?? ''), size: 16, color: color),
        ),
        title: Text(
          companyName.isNotEmpty ? '$type - $companyName' : type,
          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.text1(context)),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(severity.toUpperCase(), style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: color)),
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: color.withOpacity(0.03), borderRadius: BorderRadius.circular(8)),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(message, style: TextStyle(fontSize: 13, color: AppTheme.text1(context), height: 1.5)),
                const SizedBox(height: 10),
                if (companyName.isNotEmpty) _DetailRow(context, 'Company', companyName),
                _DetailRow(context, 'Source', source),
                _DetailRow(context, 'Severity', severity.toUpperCase()),
                _DetailRow(context, 'Type', type),
                if (detected.isNotEmpty) _DetailRow(context, 'Detected', detected.length > 19 ? detected.substring(0, 19).replaceAll('T', ' ') : detected),
                const SizedBox(height: 8),
                Text(
                  _getRiskExplanation(alert['alert_type']?.toString() ?? ''),
                  style: TextStyle(fontSize: 12, color: AppTheme.text2(context), fontStyle: FontStyle.italic, height: 1.4),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _DetailRow(BuildContext ctx, String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 70, child: Text(label, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppTheme.textH(ctx)))),
          Expanded(child: Text(value, style: TextStyle(fontSize: 12, color: AppTheme.text1(ctx)))),
        ],
      ),
    );
  }
}

// ─── ALERTS TAB (expandable with search) ───
class _AlertsTab extends StatefulWidget {
  final List<Map<String, dynamic>> alerts;
  final VoidCallback onRefresh;
  const _AlertsTab({required this.alerts, required this.onRefresh});

  @override
  State<_AlertsTab> createState() => _AlertsTabState();
}

class _AlertsTabState extends State<_AlertsTab> {
  String _searchQuery = '';
  String? _severityFilter;

  List<Map<String, dynamic>> get _filtered {
    var list = widget.alerts;
    if (_searchQuery.isNotEmpty) {
      final q = _searchQuery.toLowerCase();
      list = list.where((a) {
        final msg = (a['message'] ?? '').toString().toLowerCase();
        final company = (a['company_name'] ?? '').toString().toLowerCase();
        final source = (a['source'] ?? '').toString().toLowerCase();
        return msg.contains(q) || company.contains(q) || source.contains(q);
      }).toList();
    }
    if (_severityFilter != null) {
      list = list.where((a) => a['severity']?.toString().toLowerCase() == _severityFilter).toList();
    }
    return list;
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _filtered;

    return Column(
      children: [
        // Search bar + severity filter
        Container(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
          color: AppTheme.surfaceOf(context),
          child: Column(
            children: [
              TextField(
                onChanged: (v) => setState(() => _searchQuery = v),
                decoration: InputDecoration(
                  hintText: 'Search alerts by company, message, or source...',
                  hintStyle: TextStyle(fontSize: 13, color: AppTheme.textH(context)),
                  prefixIcon: Icon(Icons.search, size: 20, color: AppTheme.textH(context)),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: AppTheme.borderOf(context))),
                  enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: AppTheme.borderOf(context))),
                  contentPadding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
                  isDense: true,
                ),
                style: TextStyle(fontSize: 13, color: AppTheme.text1(context)),
              ),
              const SizedBox(height: 6),
              Row(
                children: [
                  _FilterChip('All', null),
                  const SizedBox(width: 4),
                  _FilterChip('Critical', 'critical'),
                  const SizedBox(width: 4),
                  _FilterChip('High', 'high'),
                  const SizedBox(width: 4),
                  _FilterChip('Medium', 'medium'),
                  const SizedBox(width: 4),
                  _FilterChip('Low', 'low'),
                  const Spacer(),
                  Text('${filtered.length} alerts', style: TextStyle(fontSize: 11, color: AppTheme.text2(context))),
                ],
              ),
            ],
          ),
        ),
        // Alert list
        Expanded(
          child: filtered.isEmpty
              ? Center(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    Icon(Icons.check_circle_outline, size: 48, color: AppTheme.success),
                    const SizedBox(height: 12),
                    Text(
                      _searchQuery.isNotEmpty ? 'No alerts matching "$_searchQuery"' : 'No active alerts',
                      style: TextStyle(fontSize: 16, color: AppTheme.text2(context)),
                    ),
                  ]),
                )
              : RefreshIndicator(
                  onRefresh: () async => widget.onRefresh(),
                  child: ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: filtered.length,
                    itemBuilder: (ctx, i) => _ExpandableRisk(alert: filtered[i]),
                  ),
                ),
        ),
      ],
    );
  }

  Widget _FilterChip(String label, String? value) {
    final active = _severityFilter == value;
    final color = value == 'critical' ? const Color(0xFF7C3AED)
        : value == 'high' ? AppTheme.danger
        : value == 'medium' ? AppTheme.warning
        : value == 'low' ? AppTheme.info
        : AppTheme.primaryDark;
    return GestureDetector(
      onTap: () => setState(() => _severityFilter = value),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: active ? color.withOpacity(0.15) : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: active ? color : AppTheme.borderOf(context)),
        ),
        child: Text(label, style: TextStyle(fontSize: 11, fontWeight: active ? FontWeight.w600 : FontWeight.w400, color: active ? color : AppTheme.text2(context))),
      ),
    );
  }
}

// ─── BY LOB TAB ───
class _LobTab extends StatelessWidget {
  final List<Map<String, dynamic>> alerts;
  final List<Map<String, dynamic>> assessments;
  const _LobTab({required this.alerts, required this.assessments});

  @override
  Widget build(BuildContext context) {
    // Group assessments by risk category (LOB)
    final lobMap = <String, List<Map<String, dynamic>>>{};
    for (final a in assessments) {
      final lob = a['risk_category']?.toString() ?? a['lob']?.toString() ?? 'Other';
      lobMap.putIfAbsent(lob, () => []).add(a);
    }

    // Count alerts per LOB by matching assessment IDs
    final alertsByLob = <String, List<Map<String, dynamic>>>{};
    final assessmentIds = <String, String>{}; // assessment_id -> lob
    for (final entry in lobMap.entries) {
      for (final a in entry.value) {
        final id = a['id']?.toString() ?? '';
        if (id.isNotEmpty) assessmentIds[id] = entry.key;
      }
    }
    for (final alert in alerts) {
      final aid = alert['assessment_id']?.toString() ?? '';
      final lob = assessmentIds[aid] ?? 'Unlinked';
      alertsByLob.putIfAbsent(lob, () => []).add(alert);
    }

    final sortedLobs = lobMap.keys.toList()..sort();

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // LOB explanation
        Container(
          padding: const EdgeInsets.all(12),
          margin: const EdgeInsets.only(bottom: 16),
          decoration: BoxDecoration(
            color: AppTheme.info.withOpacity(0.05),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AppTheme.info.withOpacity(0.2)),
          ),
          child: Row(
            children: [
              Icon(Icons.category_outlined, size: 18, color: AppTheme.info),
              const SizedBox(width: 8),
              Expanded(child: Text(
                'Alerts and risks grouped by Line of Business (LOB) for portfolio-level visibility.',
                style: TextStyle(fontSize: 12, color: AppTheme.text2(context)),
              )),
            ],
          ),
        ),

        ...sortedLobs.map((lob) {
          final lobAssessments = lobMap[lob] ?? [];
          final lobAlerts = alertsByLob[lob] ?? [];
          final critCount = lobAlerts.where((a) => a['severity']?.toString().toLowerCase() == 'critical').length;
          final highCount = lobAlerts.where((a) => a['severity']?.toString().toLowerCase() == 'high').length;

          return Card(
            margin: const EdgeInsets.only(bottom: 10),
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
              side: BorderSide(color: AppTheme.borderOf(context)),
            ),
            child: ExpansionTile(
              tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              leading: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(color: AppTheme.primaryDark.withOpacity(0.1), borderRadius: BorderRadius.circular(8)),
                child: Icon(_lobIcon(lob), size: 18, color: AppTheme.primaryDark),
              ),
              title: Text(lob.toUpperCase(), style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppTheme.text1(context))),
              subtitle: Text(
                '${lobAssessments.length} assessments | ${lobAlerts.length} alerts${critCount > 0 ? ' | $critCount critical' : ''}${highCount > 0 ? ' | $highCount high' : ''}',
                style: TextStyle(fontSize: 11, color: AppTheme.text2(context)),
              ),
              children: [
                // LOB summary
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(color: AppTheme.bg(context), borderRadius: BorderRadius.circular(8)),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Risk Profile for $lob', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.text1(context))),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          _MiniStat(context, 'Assessments', '${lobAssessments.length}', AppTheme.primaryDark),
                          _MiniStat(context, 'Alerts', '${lobAlerts.length}', AppTheme.warning),
                          _MiniStat(context, 'Critical', '$critCount', const Color(0xFF7C3AED)),
                          _MiniStat(context, 'High', '$highCount', AppTheme.danger),
                        ],
                      ),
                      if (lobAlerts.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        Text('Recent Alerts:', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppTheme.text2(context))),
                        const SizedBox(height: 6),
                        ...lobAlerts.take(5).map((alert) {
                          final sev = alert['severity']?.toString().toLowerCase() ?? 'low';
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 4),
                            child: Row(
                              children: [
                                Container(width: 8, height: 8, decoration: BoxDecoration(color: _severityColor(sev), shape: BoxShape.circle)),
                                const SizedBox(width: 8),
                                Expanded(child: Text(
                                  alert['message']?.toString() ?? '',
                                  style: TextStyle(fontSize: 11, color: AppTheme.text1(context)),
                                  maxLines: 1, overflow: TextOverflow.ellipsis,
                                )),
                              ],
                            ),
                          );
                        }),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          );
        }),

        // Unlinked alerts
        if ((alertsByLob['Unlinked'] ?? []).isNotEmpty)
          Card(
            margin: const EdgeInsets.only(bottom: 10),
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
              side: BorderSide(color: AppTheme.borderOf(context)),
            ),
            child: ExpansionTile(
              tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              leading: Icon(Icons.link_off, color: AppTheme.textH(context)),
              title: Text('PORTFOLIO-WIDE', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppTheme.text1(context))),
              subtitle: Text('${alertsByLob['Unlinked']!.length} alerts across all LOBs', style: TextStyle(fontSize: 11, color: AppTheme.text2(context))),
              children: alertsByLob['Unlinked']!.take(10).map((alert) => _ExpandableRisk(alert: alert)).toList(),
            ),
          ),
      ],
    );
  }

  Widget _MiniStat(BuildContext ctx, String label, String value, Color color) {
    return Expanded(child: Column(children: [
      Text(value, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: color)),
      Text(label, style: TextStyle(fontSize: 9, color: AppTheme.text2(ctx))),
    ]));
  }
}

// ─── NEWS TAB (expandable) ───
class _NewsTab extends StatelessWidget {
  final List<Map<String, dynamic>> newsAlerts;
  const _NewsTab({required this.newsAlerts});

  @override
  Widget build(BuildContext context) {
    if (newsAlerts.isEmpty) {
      return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        Icon(Icons.newspaper_outlined, size: 48, color: AppTheme.textH(context)),
        const SizedBox(height: 12),
        Text('No news alerts', style: TextStyle(fontSize: 16, color: AppTheme.text2(context))),
      ]));
    }

    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: newsAlerts.length,
      itemBuilder: (ctx, i) {
        final article = newsAlerts[i];
        final title = article['title']?.toString() ?? 'News';
        final source = article['source']?.toString() ?? '';
        final summary = article['summary']?.toString() ?? article['description']?.toString() ?? '';
        final sentiment = article['sentiment']?.toString() ?? 'neutral';
        final impact = article['impact']?.toString() ?? article['relevance']?.toString() ?? '';
        final published = article['published_at']?.toString() ?? '';
        final category = article['category']?.toString() ?? '';

        Color sentColor;
        switch (sentiment.toLowerCase()) {
          case 'negative': sentColor = AppTheme.danger; break;
          case 'positive': sentColor = AppTheme.success; break;
          default: sentColor = AppTheme.textSecondary;
        }

        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
            side: BorderSide(color: AppTheme.borderOf(context)),
          ),
          child: ExpansionTile(
            tilePadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
            childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
            leading: Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(color: sentColor.withOpacity(0.1), borderRadius: BorderRadius.circular(8)),
              child: Icon(Icons.article_outlined, size: 16, color: sentColor),
            ),
            title: Text(title, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.text1(context)), maxLines: 2),
            subtitle: Row(
              children: [
                if (source.isNotEmpty) Text(source, style: TextStyle(fontSize: 10, color: AppTheme.textH(context))),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                  decoration: BoxDecoration(color: sentColor.withOpacity(0.1), borderRadius: BorderRadius.circular(4)),
                  child: Text(sentiment, style: TextStyle(fontSize: 9, fontWeight: FontWeight.w600, color: sentColor)),
                ),
              ],
            ),
            children: [
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(color: AppTheme.bg(context), borderRadius: BorderRadius.circular(8)),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (summary.isNotEmpty) ...[
                      Text('Summary', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppTheme.textH(context))),
                      const SizedBox(height: 4),
                      Text(summary, style: TextStyle(fontSize: 13, color: AppTheme.text1(context), height: 1.5)),
                    ],
                    if (impact.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Text('Portfolio Impact', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppTheme.textH(context))),
                      const SizedBox(height: 4),
                      Text(impact, style: TextStyle(fontSize: 12, color: AppTheme.text2(context), height: 1.4)),
                    ],
                    if (category.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Row(children: [
                        Icon(Icons.label_outline, size: 12, color: AppTheme.textH(context)),
                        const SizedBox(width: 4),
                        Text('Category: $category', style: TextStyle(fontSize: 11, color: AppTheme.textH(context))),
                      ]),
                    ],
                    if (published.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Row(children: [
                        Icon(Icons.access_time, size: 12, color: AppTheme.textH(context)),
                        const SizedBox(width: 4),
                        Text(published.length > 10 ? published.substring(0, 10) : published,
                          style: TextStyle(fontSize: 11, color: AppTheme.textH(context))),
                      ]),
                    ],
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

// ─── BREACHES TAB (expandable) ───
class _BreachesTab extends StatelessWidget {
  final Map<String, dynamic> summary;
  final List<Map<String, dynamic>> assessments;
  const _BreachesTab({required this.summary, required this.assessments});

  @override
  Widget build(BuildContext context) {
    final recentBreaches = (summary['recent_breaches'] as List<dynamic>?) ?? [];
    final totalBreaches = summary['total_breaches'] ?? 0;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // HIBP Status Card
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.surfaceOf(context),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.borderOf(context)),
          ),
          child: Column(
            children: [
              Row(children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(color: AppTheme.danger.withOpacity(0.1), borderRadius: BorderRadius.circular(8)),
                  child: const Icon(Icons.security, color: AppTheme.danger, size: 20),
                ),
                const SizedBox(width: 10),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('HIBP Breach Monitoring', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: AppTheme.text1(context))),
                  Text('Continuous monitoring via Have I Been Pwned API', style: TextStyle(fontSize: 11, color: AppTheme.text2(context))),
                ])),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(color: AppTheme.success.withOpacity(0.1), borderRadius: BorderRadius.circular(20)),
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    Container(width: 6, height: 6, decoration: const BoxDecoration(color: AppTheme.success, shape: BoxShape.circle)),
                    const SizedBox(width: 4),
                    Text('Active', style: TextStyle(fontSize: 11, color: AppTheme.success, fontWeight: FontWeight.w600)),
                  ]),
                ),
              ]),
              const SizedBox(height: 12),
              Row(children: [
                _BreachStat(context, '$totalBreaches', 'Total Breaches', AppTheme.danger),
                const SizedBox(width: 12),
                _BreachStat(context, '${recentBreaches.length}', 'Recent Alerts', AppTheme.warning),
                const SizedBox(width: 12),
                _BreachStat(context, '${assessments.length}', 'Monitored Entities', AppTheme.info),
              ]),
            ],
          ),
        ),
        const SizedBox(height: 16),

        // How it works
        ExpansionTile(
          tilePadding: EdgeInsets.zero,
          childrenPadding: const EdgeInsets.only(bottom: 12),
          title: Text('How HIBP Monitoring Works', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.text1(context))),
          leading: Icon(Icons.help_outline, size: 18, color: AppTheme.info),
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: AppTheme.info.withOpacity(0.05), borderRadius: BorderRadius.circular(8)),
              child: Text(
                'InstantRisk monitors all insured entity email domains against the Have I Been Pwned database. '
                'When a breach is detected that affects your portfolio, alerts are generated with severity ratings '
                'based on the type of data exposed (credentials, PII, financial data) and the number of records compromised. '
                'Breaches are automatically linked to relevant assessments in your portfolio.',
                style: TextStyle(fontSize: 12, color: AppTheme.text2(context), height: 1.5),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),

        // Breach alerts (expandable)
        if (recentBreaches.isEmpty)
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: AppTheme.surfaceOf(context),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.borderOf(context)),
            ),
            child: Column(children: [
              Icon(Icons.verified_user, size: 40, color: AppTheme.success.withOpacity(0.5)),
              const SizedBox(height: 12),
              Text('No breach alerts detected', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: AppTheme.text1(context))),
              const SizedBox(height: 4),
              Text('All monitored entities are clean', style: TextStyle(fontSize: 12, color: AppTheme.text2(context))),
            ]),
          )
        else
          ...recentBreaches.map((breach) {
            final b = breach as Map<String, dynamic>;
            return _ExpandableRisk(alert: b);
          }),
      ],
    );
  }

  Widget _BreachStat(BuildContext ctx, String value, String label, Color color) {
    return Expanded(child: Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: color.withOpacity(0.05), borderRadius: BorderRadius.circular(8)),
      child: Column(children: [
        Text(value, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: color)),
        Text(label, style: TextStyle(fontSize: 10, color: AppTheme.text2(ctx))),
      ]),
    ));
  }
}

// ─── SECTION CARD HELPER ───
class _SectionCard extends StatelessWidget {
  final BuildContext context;
  final IconData icon;
  final Color iconColor;
  final String title;
  final Widget child;
  const _SectionCard({required this.context, required this.icon, required this.iconColor, required this.title, required this.child});

  @override
  Widget build(BuildContext ctx) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(ctx),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(ctx)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(color: iconColor.withOpacity(0.1), borderRadius: BorderRadius.circular(8)),
              child: Icon(icon, size: 16, color: iconColor),
            ),
            const SizedBox(width: 8),
            Text(title, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppTheme.text1(ctx))),
          ]),
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }
}

// ─── HELPERS ───
String _formatAlertType(String type) {
  return type
      .replaceAll('global_event_', '')
      .replaceAll('_', ' ')
      .split(' ')
      .map((w) => w.isEmpty ? '' : w[0].toUpperCase() + w.substring(1))
      .join(' ');
}

Color _severityColor(String severity) {
  switch (severity.toLowerCase()) {
    case 'critical': return const Color(0xFF7C3AED);
    case 'high': return const Color(0xFFDC2626);
    case 'medium': return const Color(0xFFF59E0B);
    case 'low': return const Color(0xFF3B82F6);
    default: return const Color(0xFF6B7280);
  }
}

IconData _alertTypeIcon(String type) {
  final t = type.toLowerCase();
  if (t.contains('breach') || t.contains('hibp')) return Icons.security;
  if (t.contains('earthquake')) return Icons.public;
  if (t.contains('storm') || t.contains('weather') || t.contains('noaa')) return Icons.thunderstorm;
  if (t.contains('ransomware') || t.contains('cyber')) return Icons.bug_report;
  if (t.contains('sanctions') || t.contains('regulatory')) return Icons.gavel;
  if (t.contains('vulnerability') || t.contains('cve')) return Icons.warning_amber;
  if (t.contains('financial')) return Icons.trending_down;
  if (t.contains('geopolitical')) return Icons.language;
  if (t.contains('wildfire') || t.contains('fire')) return Icons.local_fire_department;
  return Icons.notifications_outlined;
}

IconData _lobIcon(String lob) {
  final l = lob.toLowerCase();
  if (l.contains('cyber')) return Icons.security;
  if (l.contains('property')) return Icons.home_work;
  if (l.contains('marine') || l.contains('cargo')) return Icons.directions_boat;
  if (l.contains('aviation')) return Icons.flight;
  if (l.contains('liability') || l.contains('casualty')) return Icons.account_balance;
  if (l.contains('motor') || l.contains('auto')) return Icons.directions_car;
  if (l.contains('health') || l.contains('life')) return Icons.health_and_safety;
  if (l.contains('energy')) return Icons.bolt;
  return Icons.category;
}

String _getRiskExplanation(String alertType) {
  final t = alertType.toLowerCase();
  if (t.contains('earthquake')) return 'Earthquakes can cause direct property damage, business interruption, and supply chain disruption. Monitor USGS for aftershock risk and updated magnitude assessments.';
  if (t.contains('storm') || t.contains('weather')) return 'Severe weather events impact property, marine, and energy portfolios. Review exposure concentrations in affected territories and activate catastrophe response protocols.';
  if (t.contains('breach') || t.contains('hibp')) return 'Data breaches expose policyholders to regulatory fines, class action lawsuits, and reputational damage. HIBP monitoring provides early warning for cyber claims.';
  if (t.contains('ransomware')) return 'Ransomware attacks are the #1 cyber insurance claim driver. Average ransom payments exceed $1M. Check policy sub-limits and notification requirements.';
  if (t.contains('vulnerability') || t.contains('cve')) return 'Critical vulnerabilities with public exploits indicate imminent attack risk. Verify patching timelines and check if affected software is in policyholder tech stacks.';
  if (t.contains('sanctions')) return 'Sanctions violations carry severe penalties. Verify all insured entities and beneficial owners against updated OFAC/EU/UN sanctions lists.';
  if (t.contains('regulatory')) return 'Regulatory changes may affect coverage terms, compliance requirements, and capital reserves. Review policy wordings for regulatory exclusions.';
  if (t.contains('financial')) return 'Credit downgrades increase counterparty default risk. Review exposure to affected sectors and consider premium adjustments.';
  if (t.contains('geopolitical')) return 'Geopolitical events affect trade credit, political risk, and marine cargo portfolios. Monitor for sanctions escalation and territory restrictions.';
  if (t.contains('wildfire') || t.contains('fire')) return 'Wildfires threaten property portfolios with increasing frequency. Review aggregate exposure in fire-prone territories.';
  return 'This alert requires underwriter review. Assess potential impact on affected portfolio segments and consider risk mitigation actions.';
}
