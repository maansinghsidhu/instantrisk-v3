import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/monitoring_service.dart';
import '../../widgets/monitoring/risk_alerts_panel.dart';
import '../../widgets/common/screen_header.dart';

/// RiskMonitorDashboard - 24/7 real-time risk monitoring dashboard.
/// Shows alert counts by severity, recent alerts, and news monitoring.
class RiskMonitorDashboard extends StatefulWidget {
  const RiskMonitorDashboard({super.key});

  @override
  State<RiskMonitorDashboard> createState() => _RiskMonitorDashboardState();
}

class _RiskMonitorDashboardState extends State<RiskMonitorDashboard>
    with SingleTickerProviderStateMixin {
  Map<String, dynamic> _summary = {};
  List<Map<String, dynamic>> _newsAlerts = [];
  bool _isLoading = true;
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    final summaryFuture = monitoringService.getDashboardSummary();
    final newsFuture = monitoringService.getNewsAlerts(limit: 10);

    final results = await Future.wait([summaryFuture, newsFuture]);

    if (mounted) {
      setState(() {
        _summary = results[0] as Map<String, dynamic>;
        _newsAlerts = results[1] as List<Map<String, dynamic>>;
        _isLoading = false;
      });
    }
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
        title: Text(
          'Risk Monitor',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.text1(context),
          ),
        ),
        actions: [
          IconButton(
            icon: Icon(Icons.refresh, color: AppTheme.text1(context)),
            onPressed: _loadData,
            tooltip: 'Refresh',
          ),
          const SizedBox(width: 8),
        ],
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppTheme.primaryDark,
          unselectedLabelColor: AppTheme.text2(context),
          indicatorColor: AppTheme.primaryDark,
          labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
          tabs: const [
            Tab(text: 'Alerts'),
            Tab(text: 'News'),
            Tab(text: 'Breaches'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                // Summary bar
                _SummaryBar(summary: _summary),

                // Tab content
                Expanded(
                  child: TabBarView(
                    controller: _tabController,
                    children: [
                      // Alerts tab
                      _buildAlertsTab(),

                      // News tab
                      _buildNewsTab(),

                      // Breaches tab
                      _buildBreachesTab(),
                    ],
                  ),
                ),
              ],
            ),
    );
  }

  Widget _buildAlertsTab() {
    return RefreshIndicator(
      onRefresh: _loadData,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: RiskAlertsPanel(
          showHeader: true,
          maxAlerts: 50,
        ),
      ),
    );
  }

  Widget _buildNewsTab() {
    if (_newsAlerts.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.newspaper_outlined,
                size: 48, color: AppTheme.textH(context)),
            const SizedBox(height: 12),
            Text(
              'No news alerts',
              style: TextStyle(
                fontSize: 16,
                color: AppTheme.text2(context),
              ),
            ),
          ],
        ),
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: _newsAlerts.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (context, index) {
        final article = _newsAlerts[index];
        return _NewsCard(article: article);
      },
    );
  }

  Widget _buildBreachesTab() {
    final alerts = (_summary['recent_breaches'] as List<dynamic>?) ?? [];
    final totalBreaches = _summary['total_breaches'] ?? 0;

    return RefreshIndicator(
      onRefresh: _loadData,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Status header
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.surfaceOf(context),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.borderOf(context)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AppTheme.danger.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(Icons.security, color: AppTheme.danger, size: 20),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'HIBP Breach Monitoring',
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w600,
                                color: AppTheme.text1(context),
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              'Continuous monitoring via Have I Been Pwned',
                              style: TextStyle(fontSize: 12, color: AppTheme.text2(context)),
                            ),
                          ],
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppTheme.success.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              width: 6, height: 6,
                              decoration: const BoxDecoration(
                                color: AppTheme.success,
                                shape: BoxShape.circle,
                              ),
                            ),
                            const SizedBox(width: 4),
                            Text('Active', style: TextStyle(fontSize: 11, color: AppTheme.success, fontWeight: FontWeight.w600)),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: AppTheme.danger.withOpacity(0.05),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Column(
                            children: [
                              Text('$totalBreaches', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: AppTheme.danger)),
                              Text('Total Breaches', style: TextStyle(fontSize: 11, color: AppTheme.text2(context))),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: AppTheme.warning.withOpacity(0.05),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Column(
                            children: [
                              Text('${alerts.length}', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: AppTheme.warning)),
                              Text('Recent Alerts', style: TextStyle(fontSize: 11, color: AppTheme.text2(context))),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Breach alerts list
            if (alerts.isEmpty)
              Container(
                padding: const EdgeInsets.all(24),
                width: double.infinity,
                decoration: BoxDecoration(
                  color: AppTheme.surfaceOf(context),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.borderOf(context)),
                ),
                child: Column(
                  children: [
                    Icon(Icons.verified_user, size: 40, color: AppTheme.success.withOpacity(0.5)),
                    const SizedBox(height: 12),
                    Text('No breach alerts detected', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: AppTheme.text1(context))),
                    const SizedBox(height: 4),
                    Text('Portfolio entities are clean', style: TextStyle(fontSize: 12, color: AppTheme.text2(context))),
                  ],
                ),
              )
            else
              ...alerts.map((alert) {
                final a = alert as Map<String, dynamic>;
                return Container(
                  margin: const EdgeInsets.only(bottom: 10),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceOf(context),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppTheme.danger.withOpacity(0.2)),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.warning_amber_rounded, color: AppTheme.danger, size: 18),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              a['message'] ?? 'Breach detected',
                              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: AppTheme.text1(context)),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Source: ${a['source'] ?? 'HIBP'} | Severity: ${a['severity'] ?? 'unknown'}',
                              style: TextStyle(fontSize: 11, color: AppTheme.text2(context)),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                );
              }),

            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () => context.go('/reports'),
                icon: const Icon(Icons.assessment_outlined, size: 16),
                label: const Text('View All in Reports'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SummaryBar extends StatelessWidget {
  final Map<String, dynamic> summary;

  const _SummaryBar({required this.summary});

  @override
  Widget build(BuildContext context) {
    final critical = summary['critical'] ?? 0;
    final high = summary['high'] ?? 0;
    final medium = summary['medium'] ?? 0;
    final low = summary['low'] ?? 0;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      color: AppTheme.surfaceOf(context),
      child: Row(
        children: [
          _SummaryChip(
            label: 'Critical',
            count: critical,
            color: const Color(0xFF7C3AED),
            context: context,
          ),
          const SizedBox(width: 8),
          _SummaryChip(
            label: 'High',
            count: high,
            color: AppTheme.danger,
            context: context,
          ),
          const SizedBox(width: 8),
          _SummaryChip(
            label: 'Medium',
            count: medium,
            color: AppTheme.warning,
            context: context,
          ),
          const SizedBox(width: 8),
          _SummaryChip(
            label: 'Low',
            count: low,
            color: AppTheme.info,
            context: context,
          ),
        ],
      ),
    );
  }
}

class _SummaryChip extends StatelessWidget {
  final String label;
  final dynamic count;
  final Color color;
  final BuildContext context;

  const _SummaryChip({
    required this.label,
    required this.count,
    required this.color,
    required this.context,
  });

  @override
  Widget build(BuildContext ctx) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withOpacity(0.2)),
        ),
        child: Column(
          children: [
            Text(
              '$count',
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w700,
                color: color,
              ),
            ),
            Text(
              label,
              style: TextStyle(
                fontSize: 10,
                color: color,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NewsCard extends StatelessWidget {
  final Map<String, dynamic> article;

  const _NewsCard({required this.article});

  @override
  Widget build(BuildContext context) {
    final title = article['title']?.toString() ?? 'News Article';
    final source = article['source']?.toString() ?? '';
    final summary = article['summary']?.toString() ?? article['description']?.toString() ?? '';
    final sentiment = article['sentiment']?.toString() ?? 'neutral';
    final publishedAt = article['published_at']?.toString() ?? '';

    Color sentimentColor;
    String sentimentLabel;
    switch (sentiment.toLowerCase()) {
      case 'negative':
        sentimentColor = AppTheme.danger;
        sentimentLabel = 'Negative';
        break;
      case 'positive':
        sentimentColor = AppTheme.success;
        sentimentLabel = 'Positive';
        break;
      default:
        sentimentColor = AppTheme.textSecondary;
        sentimentLabel = 'Neutral';
    }

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.text1(context),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                decoration: BoxDecoration(
                  color: sentimentColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  sentimentLabel,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    color: sentimentColor,
                  ),
                ),
              ),
            ],
          ),
          if (summary.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                summary,
                style: TextStyle(
                  fontSize: 13,
                  color: AppTheme.text2(context),
                  height: 1.4,
                ),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          const SizedBox(height: 6),
          Row(
            children: [
              if (source.isNotEmpty) ...[
                Icon(Icons.source_outlined, size: 12, color: AppTheme.textH(context)),
                const SizedBox(width: 4),
                Text(
                  source,
                  style: TextStyle(fontSize: 11, color: AppTheme.textH(context)),
                ),
                const SizedBox(width: 8),
              ],
              if (publishedAt.isNotEmpty)
                Text(
                  publishedAt.length > 10 ? publishedAt.substring(0, 10) : publishedAt,
                  style: TextStyle(fontSize: 11, color: AppTheme.textH(context)),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
