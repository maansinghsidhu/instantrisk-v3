import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';

/// PortfolioDashboard - DuckDB-powered portfolio analytics dashboard.
/// Shows aggregated underwriting statistics, LOB distribution, decision trends,
/// premium exposure by category, and portfolio health metrics.
class PortfolioDashboard extends StatefulWidget {
  const PortfolioDashboard({super.key});

  @override
  State<PortfolioDashboard> createState() => _PortfolioDashboardState();
}

class _PortfolioDashboardState extends State<PortfolioDashboard>
    with SingleTickerProviderStateMixin {
  Map<String, dynamic> _stats = {};
  List<Map<String, dynamic>> _lobBreakdown = [];
  List<Map<String, dynamic>> _decisionTrend = [];
  List<Map<String, dynamic>> _topRisks = [];
  bool _isLoading = true;
  String _selectedPeriod = '30d';
  late TabController _tabController;

  static const List<String> _periods = ['7d', '30d', '90d', '1y'];

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
    try {
      final response = await authService.get(
        '/analytics/portfolio?period=$_selectedPeriod',
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        if (mounted) {
          setState(() {
            _stats = data['summary'] as Map<String, dynamic>? ?? {};
            _lobBreakdown = List<Map<String, dynamic>>.from(
                data['lob_breakdown'] ?? []);
            _decisionTrend = List<Map<String, dynamic>>.from(
                data['decision_trend'] ?? []);
            _topRisks = List<Map<String, dynamic>>.from(data['top_risks'] ?? []);
            _isLoading = false;
          });
          return;
        }
      }
    } catch (_) {}

    // Fallback demo data
    if (mounted) {
      setState(() {
        _stats = {
          'total_assessments': 248,
          'go_rate': 0.67,
          'avg_confidence': 0.82,
          'avg_risk_score': 42.3,
          'total_premium_exposure': 4200000,
        };
        _lobBreakdown = [
          {'lob': 'Cyber', 'count': 82, 'go_rate': 0.61},
          {'lob': 'Property', 'count': 74, 'go_rate': 0.74},
          {'lob': 'Casualty', 'count': 55, 'go_rate': 0.65},
          {'lob': 'Marine', 'count': 22, 'go_rate': 0.72},
          {'lob': 'Financial Lines', 'count': 15, 'go_rate': 0.53},
        ];
        _decisionTrend = [
          {'period': 'Week 1', 'go': 18, 'no_go': 8},
          {'period': 'Week 2', 'go': 22, 'no_go': 10},
          {'period': 'Week 3', 'go': 19, 'no_go': 11},
          {'period': 'Week 4', 'go': 25, 'no_go': 9},
        ];
        _topRisks = [
          {'name': 'Acme Industries', 'score': 78, 'lob': 'Cyber', 'decision': 'NO_GO'},
          {'name': 'BuildRight Corp', 'score': 72, 'lob': 'Property', 'decision': 'NO_GO'},
          {'name': 'TechStart Ltd', 'score': 68, 'lob': 'Cyber', 'decision': 'GO'},
          {'name': 'ShipFast Logistics', 'score': 65, 'lob': 'Marine', 'decision': 'GO'},
          {'name': 'MedSupply Co', 'score': 61, 'lob': 'Casualty', 'decision': 'NO_GO'},
        ];
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
          onPressed: () => context.go('/analytics'),
        ),
        title: Text(
          'Portfolio Analytics',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.text1(context),
          ),
        ),
        actions: [
          // Period selector
          Container(
            margin: const EdgeInsets.symmetric(vertical: 8, horizontal: 8),
            padding: const EdgeInsets.symmetric(horizontal: 8),
            decoration: BoxDecoration(
              color: AppTheme.borderLightOf(context),
              borderRadius: BorderRadius.circular(8),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: _selectedPeriod,
                isDense: true,
                items: _periods.map((p) => DropdownMenuItem(
                  value: p,
                  child: Text(p, style: const TextStyle(fontSize: 13)),
                )).toList(),
                onChanged: (val) {
                  if (val != null) {
                    setState(() => _selectedPeriod = val);
                    _loadData();
                  }
                },
              ),
            ),
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppTheme.primaryDark,
          unselectedLabelColor: AppTheme.text2(context),
          indicatorColor: AppTheme.primaryDark,
          labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
          tabs: const [
            Tab(text: 'Overview'),
            Tab(text: 'By LOB'),
            Tab(text: 'Top Risks'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildOverviewTab(),
                _buildLobTab(),
                _buildTopRisksTab(),
              ],
            ),
    );
  }

  Widget _buildOverviewTab() {
    final total = _stats['total_assessments'] ?? 0;
    final goRate = ((_stats['go_rate'] ?? 0) * 100).toStringAsFixed(1);
    final confidence = ((_stats['avg_confidence'] ?? 0) * 100).toStringAsFixed(1);
    final riskScore = (_stats['avg_risk_score'] ?? 0).toStringAsFixed(1);
    final exposure = _stats['total_premium_exposure'] ?? 0;

    return RefreshIndicator(
      onRefresh: _loadData,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 800),
            child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // KPI Grid - responsive columns for web
            LayoutBuilder(
              builder: (context, constraints) {
                final cols = constraints.maxWidth > 900 ? 4 : constraints.maxWidth > 600 ? 3 : 2;
                return GridView.count(
                  crossAxisCount: cols,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  crossAxisSpacing: 12,
                  mainAxisSpacing: 12,
                  childAspectRatio: cols >= 3 ? 1.8 : 1.6,
                  children: [
                _KpiCard(
                  title: 'Total Assessments',
                  value: '$total',
                  subtitle: 'Last $_selectedPeriod',
                  color: AppTheme.primaryDark,
                  icon: Icons.assessment_outlined,
                ),
                _KpiCard(
                  title: 'GO Rate',
                  value: '$goRate%',
                  subtitle: 'Acceptance rate',
                  color: AppTheme.success,
                  icon: Icons.check_circle_outline,
                ),
                _KpiCard(
                  title: 'Avg Confidence',
                  value: '$confidence%',
                  subtitle: 'AI confidence',
                  color: AppTheme.analysisClassifier,
                  icon: Icons.psychology_outlined,
                ),
                _KpiCard(
                  title: 'Avg Risk Score',
                  value: riskScore,
                  subtitle: 'Portfolio risk',
                  color: AppTheme.warning,
                  icon: Icons.trending_up,
                ),
                  ],
                );
              },
            ),

            const SizedBox(height: 16),

            // Premium Exposure
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    AppTheme.primaryDark,
                    AppTheme.primaryLight,
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'TOTAL PREMIUM EXPOSURE',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      color: Colors.white70,
                      letterSpacing: 1,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '\$${(exposure / 1000000).toStringAsFixed(2)}M',
                    style: const TextStyle(
                      fontSize: 32,
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                      fontFamily: 'Inter',
                    ),
                  ),
                  const Text(
                    'Powered by DuckDB analytics engine',
                    style: TextStyle(fontSize: 11, color: Colors.white54),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 16),

            // Decision Trend
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
                  Text(
                    'DECISION TREND',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.text2(context),
                      letterSpacing: 1,
                    ),
                  ),
                  const SizedBox(height: 12),
                  ..._decisionTrend.map((week) {
                    final go = (week['go'] as num?)?.toInt() ?? 0;
                    final noGo = (week['no_go'] as num?)?.toInt() ?? 0;
                    final total = go + noGo;
                    final goFrac = total > 0 ? go / total : 0.0;
                    return _TrendRow(
                      label: week['period']?.toString() ?? '',
                      goCount: go,
                      noGoCount: noGo,
                      goFraction: goFrac,
                    );
                  }),
                ],
              ),
            ),
          ],
        ),
          ),
        ),
      ),
    );
  }

  Widget _buildLobTab() {
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: _lobBreakdown.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (context, index) {
        final lob = _lobBreakdown[index];
        final name = lob['lob']?.toString() ?? 'Unknown';
        final count = (lob['count'] as num?)?.toInt() ?? 0;
        final goRate = (lob['go_rate'] as num?)?.toDouble() ?? 0;
        final color = AppTheme.lobColors[index % AppTheme.lobColors.length];

        return Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AppTheme.surfaceOf(context),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AppTheme.borderOf(context)),
          ),
          child: Column(
            children: [
              Row(
                children: [
                  Container(
                    width: 14,
                    height: 14,
                    decoration: BoxDecoration(
                      color: color,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      name,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.text1(context),
                      ),
                    ),
                  ),
                  Text(
                    '$count assessments',
                    style: TextStyle(
                      fontSize: 12,
                      color: AppTheme.text2(context),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(
                    '${(goRate * 100).toStringAsFixed(0)}% GO',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: goRate >= 0.6 ? AppTheme.success : AppTheme.danger,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: goRate,
                  backgroundColor: AppTheme.danger.withOpacity(0.2),
                  color: goRate >= 0.6 ? AppTheme.success : AppTheme.warning,
                  minHeight: 8,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildTopRisksTab() {
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: _topRisks.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (context, index) {
        final risk = _topRisks[index];
        final name = risk['name']?.toString() ?? 'Entity $index';
        final score = (risk['score'] as num?)?.toInt() ?? 0;
        final lob = risk['lob']?.toString() ?? 'N/A';
        final decision = risk['decision']?.toString() ?? 'UNKNOWN';
        final isGo = decision == 'GO';

        return Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AppTheme.surfaceOf(context),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: score > 70
                  ? AppTheme.danger.withOpacity(0.3)
                  : AppTheme.borderOf(context),
            ),
          ),
          child: Row(
            children: [
              // Risk score badge
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: (score > 70
                          ? AppTheme.danger
                          : score > 50
                              ? AppTheme.warning
                              : AppTheme.success)
                      .withOpacity(0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                alignment: Alignment.center,
                child: Text(
                  '$score',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: score > 70
                        ? AppTheme.danger
                        : score > 50
                            ? AppTheme.warning
                            : AppTheme.success,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name,
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.text1(context),
                      ),
                    ),
                    Text(
                      lob,
                      style: TextStyle(
                        fontSize: 12,
                        color: AppTheme.text2(context),
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: isGo
                      ? AppTheme.success.withOpacity(0.1)
                      : AppTheme.danger.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  decision.replaceAll('_', ' '),
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: isGo ? AppTheme.success : AppTheme.danger,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _KpiCard extends StatelessWidget {
  final String title;
  final String value;
  final String subtitle;
  final Color color;
  final IconData icon;

  const _KpiCard({
    required this.title,
    required this.value,
    required this.subtitle,
    required this.color,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Icon(icon, size: 16, color: color),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    fontSize: 11,
                    color: AppTheme.text2(context),
                    fontWeight: FontWeight.w500,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          Text(
            value,
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w700,
              color: color,
              fontFamily: 'Inter',
            ),
          ),
          Text(
            subtitle,
            style: TextStyle(
              fontSize: 10,
              color: AppTheme.textH(context),
            ),
          ),
        ],
      ),
    );
  }
}

class _TrendRow extends StatelessWidget {
  final String label;
  final int goCount;
  final int noGoCount;
  final double goFraction;

  const _TrendRow({
    required this.label,
    required this.goCount,
    required this.noGoCount,
    required this.goFraction,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          SizedBox(
            width: 56,
            child: Text(
              label,
              style: TextStyle(fontSize: 12, color: AppTheme.text2(context)),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: Row(
                children: [
                  if (goFraction > 0)
                    Flexible(
                      flex: (goFraction * 100).toInt(),
                      child: Container(
                        height: 20,
                        color: AppTheme.success.withOpacity(0.7),
                        alignment: Alignment.center,
                        child: Text(
                          '$goCount',
                          style: const TextStyle(
                            fontSize: 10,
                            color: Colors.white,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                  if (1 - goFraction > 0)
                    Flexible(
                      flex: ((1 - goFraction) * 100).toInt(),
                      child: Container(
                        height: 20,
                        color: AppTheme.danger.withOpacity(0.6),
                        alignment: Alignment.center,
                        child: Text(
                          '$noGoCount',
                          style: const TextStyle(
                            fontSize: 10,
                            color: Colors.white,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
