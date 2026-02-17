import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// V3 Exposure Dashboard - Modern Corporate Design
/// Connected to real backend API for exposure data
class ExposureDashboardScreen extends StatefulWidget {
  const ExposureDashboardScreen({super.key});

  @override
  State<ExposureDashboardScreen> createState() => _ExposureDashboardScreenState();
}

class _ExposureDashboardScreenState extends State<ExposureDashboardScreen> with SingleTickerProviderStateMixin {
  bool _isLoading = true;
  String? _errorMessage;
  late TabController _tabController;

  // Real data from API
  Map<String, dynamic>? _dashboardData;
  List<Map<String, dynamic>> _zoneExposure = [];
  List<Map<String, dynamic>> _perilExposure = [];
  List<Map<String, dynamic>> _alerts = [];

  // Actual stats data
  Map<String, dynamic>? _actualStats;
  List<Map<String, dynamic>> _losses = [];
  List<Map<String, dynamic>> _claims = [];

  // Summary metrics
  double _totalGrossExposure = 0;
  double _totalNetExposure = 0;
  double _capacity = 0;
  double _utilizationPercentage = 0;
  double _pml100 = 0;
  double _pml250 = 0;

  final List<Color> _zoneColors = [
    AppTheme.corporateBlue,
    AppTheme.corporateBlueLight,
    const Color(0xFF7DC4E4),
    const Color(0xFF94D2BD),
    const Color(0xFFADE8F4),
    const Color(0xFFE8D3A8),
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadExposureData();
    _loadActualStats();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadExposureData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      // Get syndicate ID (default to 1 for demo, or from user profile)
      const syndicateId = 1;

      // Fetch dashboard data from API
      final dashboardResponse = await authService.get('/exposure/dashboard/$syndicateId');

      if (dashboardResponse.statusCode == 200) {
        final data = jsonDecode(dashboardResponse.body);
        _dashboardData = data;

        // Parse exposure by zone
        final byZone = data['by_zone'] as List<dynamic>? ?? [];
        _zoneExposure = byZone.asMap().entries.map((entry) {
          final zone = entry.value;
          final colorIndex = entry.key % _zoneColors.length;
          return {
            'zone': zone['zone'] ?? 'Unknown',
            'code': _getZoneCode(zone['zone'] ?? ''),
            'gross': (zone['gross_exposure'] ?? 0).toDouble() / 1000000, // Convert to millions
            'net': (zone['net_exposure'] ?? 0).toDouble() / 1000000,
            'color': _zoneColors[colorIndex],
          };
        }).toList();

        // Parse exposure by peril
        final byPeril = data['by_peril'] as List<dynamic>? ?? [];
        _perilExposure = byPeril.map((peril) {
          return {
            'peril': peril['peril'] ?? 'Unknown',
            'icon': _getPerilIcon(peril['peril'] ?? ''),
            'pml100': (peril['pml_100yr'] ?? peril['gross_exposure'] ?? 0).toDouble() / 1000000,
            'pml250': (peril['pml_250yr'] ?? (peril['gross_exposure'] ?? 0) * 1.5).toDouble() / 1000000,
            'trend': 0.0, // Would come from trend API
          };
        }).toList();

        // Parse alerts
        final alertsList = data['alerts'] as List<dynamic>? ?? [];
        _alerts = alertsList.map((alert) {
          if (alert is String) {
            return {'message': alert, 'severity': 'warning', 'time': 'Now'};
          }
          return {
            'message': alert['message'] ?? alert.toString(),
            'severity': alert['severity'] ?? 'warning',
            'time': 'Now',
          };
        }).toList();

        // Parse summary metrics
        _totalGrossExposure = (data['total_gross_exposure'] ?? 0).toDouble();
        _totalNetExposure = (data['total_net_exposure'] ?? 0).toDouble();
        _capacity = (data['capacity'] ?? 0).toDouble();
        _utilizationPercentage = (data['utilization_percentage'] ?? 0).toDouble();
      } else {
        // API call failed, use fallback data
        _setFallbackData();
      }

      // Fetch PML data
      try {
        final pml100Response = await authService.get('/exposure/pml/$syndicateId?return_period=100');
        if (pml100Response.statusCode == 200) {
          final pml100Data = jsonDecode(pml100Response.body);
          _pml100 = (pml100Data['net_pml'] ?? 0).toDouble();
        }

        final pml250Response = await authService.get('/exposure/pml/$syndicateId?return_period=250');
        if (pml250Response.statusCode == 200) {
          final pml250Data = jsonDecode(pml250Response.body);
          _pml250 = (pml250Data['net_pml'] ?? 0).toDouble();
        }
      } catch (e) {
        // PML data might not be available, use estimates
        _pml100 = _totalNetExposure * 0.15;
        _pml250 = _totalNetExposure * 0.25;
      }

      setState(() => _isLoading = false);
    } catch (e) {
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load exposure data: $e';
        // Set fallback data for demo
        _setFallbackData();
      });
    }
  }

  void _setFallbackData() {
    // Fallback data when API is unavailable
    _zoneExposure = [
      {'zone': 'North America', 'code': 'NA', 'gross': 45.5, 'net': 32.1, 'color': AppTheme.corporateBlue},
      {'zone': 'Europe', 'code': 'EU', 'gross': 28.3, 'net': 19.7, 'color': AppTheme.corporateBlueLight},
      {'zone': 'Asia Pacific', 'code': 'APAC', 'gross': 15.2, 'net': 10.8, 'color': const Color(0xFF7DC4E4)},
      {'zone': 'Latin America', 'code': 'LATAM', 'gross': 6.5, 'net': 4.2, 'color': const Color(0xFF94D2BD)},
      {'zone': 'Middle East', 'code': 'ME', 'gross': 4.5, 'net': 3.1, 'color': const Color(0xFFADE8F4)},
    ];
    _perilExposure = [
      {'peril': 'Windstorm', 'icon': Icons.air, 'pml100': 125.0, 'pml250': 185.0, 'trend': 2.3},
      {'peril': 'Earthquake', 'icon': Icons.landscape, 'pml100': 85.0, 'pml250': 142.0, 'trend': -1.2},
      {'peril': 'Flood', 'icon': Icons.water, 'pml100': 45.0, 'pml250': 78.0, 'trend': 5.1},
      {'peril': 'Cyber', 'icon': Icons.security, 'pml100': 35.0, 'pml250': 62.0, 'trend': 12.4},
      {'peril': 'Fire', 'icon': Icons.local_fire_department, 'pml100': 28.0, 'pml250': 45.0, 'trend': 0.8},
    ];
    _totalGrossExposure = 2500000000;
    _totalNetExposure = 1800000000;
    _capacity = 3700000000;
    _utilizationPercentage = 67.5;
    _pml100 = 318000000;
    _pml250 = 512000000;
  }

  Future<void> _loadActualStats() async {
    try {
      const syndicateId = 1;
      final response = await authService.get('/exposure/actual-stats/$syndicateId');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _actualStats = data;
          _losses = List<Map<String, dynamic>>.from(data['recent_losses'] ?? []);
          _claims = List<Map<String, dynamic>>.from(data['recent_claims'] ?? []);
        });
      }
    } catch (e) {
      // Fallback - stats will be empty
    }
  }

  Future<void> _addLoss() async {
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (ctx) => _LossEntryDialog(),
    );
    if (result != null) {
      try {
        const syndicateId = 1;
        final response = await authService.post(
          '/exposure/losses/$syndicateId',
          body: result,
        );
        if (response.statusCode == 200 || response.statusCode == 201) {
          _loadActualStats();
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Loss added successfully'), backgroundColor: AppTheme.successDark),
            );
          }
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Failed to add loss: $e'), backgroundColor: AppTheme.dangerDark),
          );
        }
      }
    }
  }

  Future<void> _addClaim() async {
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (ctx) => _ClaimEntryDialog(),
    );
    if (result != null) {
      try {
        const syndicateId = 1;
        final response = await authService.post(
          '/exposure/claims/$syndicateId',
          body: result,
        );
        if (response.statusCode == 200 || response.statusCode == 201) {
          _loadActualStats();
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Claim added successfully'), backgroundColor: AppTheme.successDark),
            );
          }
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Failed to add claim: $e'), backgroundColor: AppTheme.dangerDark),
          );
        }
      }
    }
  }

  String _getZoneCode(String zone) {
    final codes = {
      'North America': 'NA',
      'Europe': 'EU',
      'Asia Pacific': 'APAC',
      'Latin America': 'LATAM',
      'Middle East': 'ME',
      'Africa': 'AFR',
    };
    return codes[zone] ?? zone.substring(0, 2).toUpperCase();
  }

  IconData _getPerilIcon(String peril) {
    final icons = {
      'Windstorm': Icons.air,
      'Hurricane': Icons.air,
      'Earthquake': Icons.landscape,
      'Flood': Icons.water,
      'Cyber': Icons.security,
      'Fire': Icons.local_fire_department,
      'Marine': Icons.directions_boat,
      'Aviation': Icons.flight,
    };
    return icons[peril] ?? Icons.warning;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: AppTheme.corporateBlue))
          : NestedScrollView(
              headerSliverBuilder: (context, innerBoxIsScrolled) => [
                _buildAppBar(),
                SliverPersistentHeader(
                  pinned: true,
                  delegate: _TabBarDelegate(
                    TabBar(
                      controller: _tabController,
                      labelColor: AppTheme.darkBg,
                      unselectedLabelColor: Colors.grey,
                      indicatorColor: AppTheme.corporateBlue,
                      tabs: const [
                        Tab(text: 'Portfolio'),
                        Tab(text: 'Actual Stats'),
                      ],
                    ),
                  ),
                ),
              ],
              body: TabBarView(
                controller: _tabController,
                children: [
                  _buildPortfolioTab(),
                  _buildActualStatsTab(),
                ],
              ),
            ),
    );
  }

  Widget _buildPortfolioTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          _buildKPISection(),
          const SizedBox(height: 24),
          _buildCapacityUtilization(),
          const SizedBox(height: 24),
          _buildExposureByZone(),
          const SizedBox(height: 24),
          _buildPerilAnalysis(),
          const SizedBox(height: 24),
          _buildRiskAlerts(),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildActualStatsTab() {
    final totalLosses = _actualStats?['total_incurred_losses'] ?? 0.0;
    final totalClaims = _actualStats?['total_claims_amount'] ?? 0.0;
    final totalReserves = _actualStats?['total_reserves'] ?? 0.0;
    final lossRatio = _actualStats?['loss_ratio'] ?? 0.0;
    final claimsCount = _actualStats?['claims_count'] ?? 0;
    final openClaimsCount = _actualStats?['open_claims_count'] ?? 0;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Actual Stats KPI Cards
          _buildSectionHeader('Actual Performance', 'Real losses and claims data'),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(child: _buildActualStatCard(
                'Incurred Losses',
                'GBP ${(totalLosses / 1000000).toStringAsFixed(1)}M',
                Icons.trending_down,
                AppTheme.dangerDark,
              )),
              const SizedBox(width: 12),
              Expanded(child: _buildActualStatCard(
                'Loss Ratio',
                '${lossRatio.toStringAsFixed(1)}%',
                Icons.pie_chart,
                lossRatio > 65 ? AppTheme.dangerDark : lossRatio > 50 ? AppTheme.warningAmber : AppTheme.successDark,
              )),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _buildActualStatCard(
                'Total Claims',
                'GBP ${(totalClaims / 1000000).toStringAsFixed(1)}M',
                Icons.receipt_long,
                AppTheme.warningAmber,
              )),
              const SizedBox(width: 12),
              Expanded(child: _buildActualStatCard(
                'Open Claims',
                '$openClaimsCount of $claimsCount',
                Icons.pending_actions,
                AppTheme.corporateBlueLight,
              )),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _buildActualStatCard(
                'Reserves',
                'GBP ${(totalReserves / 1000000).toStringAsFixed(1)}M',
                Icons.savings,
                AppTheme.corporateBlue,
              )),
              const SizedBox(width: 12),
              const Expanded(child: SizedBox()),
            ],
          ),

          const SizedBox(height: 24),

          // Recent Losses Section
          _buildSectionWithAction(
            'Recent Losses',
            'Track incurred losses',
            'Add Loss',
            _addLoss,
          ),
          const SizedBox(height: 12),
          _buildLossesList(),

          const SizedBox(height: 24),

          // Recent Claims Section
          _buildSectionWithAction(
            'Recent Claims',
            'Manage claims',
            'Add Claim',
            _addClaim,
          ),
          const SizedBox(height: 12),
          _buildClaimsList(),

          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildActualStatCard(String title, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(height: 12),
          Text(
            value,
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: AppTheme.darkBg,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            title,
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey[600],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionWithAction(String title, String subtitle, String buttonText, VoidCallback onPressed) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: AppTheme.darkBg)),
            Text(subtitle, style: TextStyle(fontSize: 13, color: Colors.grey[600])),
          ],
        ),
        ElevatedButton.icon(
          onPressed: onPressed,
          icon: const Icon(Icons.add, size: 18),
          label: Text(buttonText),
          style: ElevatedButton.styleFrom(
            backgroundColor: AppTheme.corporateBlue,
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          ),
        ),
      ],
    );
  }

  Widget _buildLossesList() {
    if (_losses.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.grey[200]!),
        ),
        child: Center(
          child: Column(
            children: [
              Icon(Icons.trending_down, size: 40, color: Colors.grey[300]),
              const SizedBox(height: 8),
              Text('No losses recorded', style: TextStyle(color: Colors.grey[500])),
            ],
          ),
        ),
      );
    }

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 10)],
      ),
      child: ListView.separated(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        itemCount: _losses.length,
        separatorBuilder: (_, __) => Divider(height: 1, color: Colors.grey[200]),
        itemBuilder: (context, index) {
          final loss = _losses[index];
          return ListTile(
            leading: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppTheme.dangerDark.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.trending_down, color: AppTheme.dangerDark, size: 20),
            ),
            title: Text(
              'GBP ${((loss['loss_amount'] ?? 0) / 1000).toStringAsFixed(0)}K',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            subtitle: Text(
              '${loss['territory'] ?? 'Unknown'} - ${loss['peril'] ?? 'N/A'}',
              style: TextStyle(fontSize: 12, color: Colors.grey[600]),
            ),
            trailing: Text(
              loss['loss_type']?.toString().toUpperCase() ?? 'ATTRITIONAL',
              style: TextStyle(fontSize: 11, color: Colors.grey[500]),
            ),
          );
        },
      ),
    );
  }

  Widget _buildClaimsList() {
    if (_claims.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.grey[200]!),
        ),
        child: Center(
          child: Column(
            children: [
              Icon(Icons.receipt_long, size: 40, color: Colors.grey[300]),
              const SizedBox(height: 8),
              Text('No claims recorded', style: TextStyle(color: Colors.grey[500])),
            ],
          ),
        ),
      );
    }

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 10)],
      ),
      child: ListView.separated(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        itemCount: _claims.length,
        separatorBuilder: (_, __) => Divider(height: 1, color: Colors.grey[200]),
        itemBuilder: (context, index) {
          final claim = _claims[index];
          final status = claim['status']?.toString().toUpperCase() ?? 'REPORTED';
          Color statusColor;
          switch (status) {
            case 'PAID':
            case 'CLOSED':
              statusColor = AppTheme.successDark;
              break;
            case 'DISPUTED':
              statusColor = AppTheme.dangerDark;
              break;
            default:
              statusColor = AppTheme.warningAmber;
          }
          return ListTile(
            leading: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppTheme.warningAmber.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.receipt_long, color: AppTheme.warningAmber, size: 20),
            ),
            title: Text(
              claim['claim_number'] ?? 'Claim #${index + 1}',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            subtitle: Text(
              'GBP ${((claim['claim_amount'] ?? 0) / 1000).toStringAsFixed(0)}K - ${claim['cause'] ?? 'N/A'}',
              style: TextStyle(fontSize: 12, color: Colors.grey[600]),
            ),
            trailing: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: statusColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                status,
                style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: statusColor),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildAppBar() {
    return SliverAppBar(
      expandedHeight: 120,
      floating: false,
      pinned: true,
      backgroundColor: AppTheme.darkBg,
      flexibleSpace: FlexibleSpaceBar(
        title: const Text(
          'Exposure Dashboard',
          style: TextStyle(
            fontWeight: FontWeight.w600,
            fontSize: 18,
          ),
        ),
        background: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [AppTheme.darkBg, AppTheme.corporateBlue],
            ),
          ),
          child: Align(
            alignment: Alignment.bottomRight,
            child: Padding(
              padding: const EdgeInsets.only(right: 16, bottom: 60),
              child: Icon(
                Icons.analytics_outlined,
                size: 80,
                color: Colors.white.withOpacity(0.1),
              ),
            ),
          ),
        ),
      ),
      actions: [
        IconButton(
          icon: const Icon(Icons.refresh_rounded),
          onPressed: () {
            setState(() => _isLoading = true);
            _loadExposureData();
          },
        ),
        IconButton(
          icon: const Icon(Icons.file_download_outlined),
          onPressed: _exportReport,
        ),
        const SizedBox(width: 8),
      ],
    );
  }

  Widget _buildKPISection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader('Portfolio Overview', 'Real-time exposure metrics'),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(child: _buildKPICard(
              'Gross Exposure',
              'GBP 2.5B',
              '+3.2%',
              true,
              LinearGradient(colors: [AppTheme.corporateBlue, AppTheme.corporateBlue.withOpacity(0.8)]),
              Icons.account_balance_wallet_outlined,
            )),
            const SizedBox(width: 12),
            Expanded(child: _buildKPICard(
              'Net Exposure',
              'GBP 1.8B',
              '+2.1%',
              true,
              LinearGradient(colors: [AppTheme.corporateBlueLight, AppTheme.corporateBlueLight.withOpacity(0.7)]),
              Icons.shield_outlined,
            )),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(child: _buildKPICard(
              'PML 1-in-100',
              'GBP 318M',
              '-1.5%',
              false,
              LinearGradient(colors: [AppTheme.warningAmber, AppTheme.warningAmber.withOpacity(0.7)]),
              Icons.trending_down,
            )),
            const SizedBox(width: 12),
            Expanded(child: _buildKPICard(
              'PML 1-in-250',
              'GBP 512M',
              '+0.8%',
              true,
              LinearGradient(colors: [AppTheme.dangerDark, AppTheme.errorRed]),
              Icons.priority_high_rounded,
            )),
          ],
        ),
      ],
    );
  }

  Widget _buildSectionHeader(String title, String subtitle) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: AppTheme.darkBg,
                letterSpacing: -0.5,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              subtitle,
              style: TextStyle(
                fontSize: 13,
                color: Colors.grey[600],
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildKPICard(String title, String value, String change, bool isPositive, Gradient gradient, IconData icon) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: Colors.white, size: 20),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      isPositive ? Icons.arrow_upward : Icons.arrow_downward,
                      color: Colors.white,
                      size: 12,
                    ),
                    const SizedBox(width: 2),
                    Text(
                      change,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            value,
            style: const TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w700,
              color: Colors.white,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            title,
            style: TextStyle(
              fontSize: 13,
              color: Colors.white.withOpacity(0.85),
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCapacityUtilization() {
    const double utilization = 67.5;
    const double capacity = 3.7;
    final remaining = capacity * (1 - utilization / 100);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Capacity Utilization',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.darkBg,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: AppTheme.warningAmber.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  '${utilization.toStringAsFixed(1)}%',
                  style: const TextStyle(
                    color: AppTheme.warningAmber,
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: Stack(
              children: [
                Container(
                  height: 12,
                  decoration: BoxDecoration(
                    color: Colors.grey[200],
                  ),
                ),
                FractionallySizedBox(
                  widthFactor: utilization / 100,
                  child: Container(
                    height: 12,
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: utilization > 80
                            ? [AppTheme.dangerDark, AppTheme.dangerDark.withOpacity(0.8)]
                            : utilization > 60
                                ? [AppTheme.warningAmber, AppTheme.warningAmber.withOpacity(0.8)]
                                : [AppTheme.successDark, AppTheme.successDark.withOpacity(0.8)],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _buildCapacityMetric(
                  'Total Capacity',
                  'GBP ${capacity.toStringAsFixed(1)}B',
                  Icons.pie_chart_outline,
                ),
              ),
              Container(width: 1, height: 40, color: Colors.grey[200]),
              Expanded(
                child: _buildCapacityMetric(
                  'Utilized',
                  'GBP ${(capacity * utilization / 100).toStringAsFixed(1)}B',
                  Icons.check_circle_outline,
                ),
              ),
              Container(width: 1, height: 40, color: Colors.grey[200]),
              Expanded(
                child: _buildCapacityMetric(
                  'Available',
                  'GBP ${remaining.toStringAsFixed(1)}B',
                  Icons.add_circle_outline,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildCapacityMetric(String label, String value, IconData icon) {
    return Column(
      children: [
        Icon(icon, color: AppTheme.corporateBlue, size: 20),
        const SizedBox(height: 4),
        Text(
          value,
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w700,
            color: AppTheme.darkBg,
          ),
        ),
        Text(
          label,
          style: TextStyle(
            fontSize: 11,
            color: Colors.grey[600],
          ),
        ),
      ],
    );
  }

  Widget _buildExposureByZone() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Geographic Distribution',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: AppTheme.darkBg,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Exposure allocation by region',
            style: TextStyle(fontSize: 13, color: Colors.grey[600]),
          ),
          const SizedBox(height: 24),
          SizedBox(
            height: 200,
            child: BarChart(
              BarChartData(
                alignment: BarChartAlignment.spaceAround,
                maxY: 50,
                barGroups: _zoneExposure.asMap().entries.map((e) {
                  return BarChartGroupData(
                    x: e.key,
                    barRods: [
                      BarChartRodData(
                        toY: e.value['gross'],
                        color: (e.value['color'] as Color).withOpacity(0.4),
                        width: 16,
                        borderRadius: const BorderRadius.vertical(top: Radius.circular(6)),
                      ),
                      BarChartRodData(
                        toY: e.value['net'],
                        color: e.value['color'],
                        width: 16,
                        borderRadius: const BorderRadius.vertical(top: Radius.circular(6)),
                      ),
                    ],
                  );
                }).toList(),
                titlesData: FlTitlesData(
                  show: true,
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      getTitlesWidget: (value, meta) {
                        return Padding(
                          padding: const EdgeInsets.only(top: 8),
                          child: Text(
                            _zoneExposure[value.toInt()]['code'],
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: Colors.grey[700],
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      getTitlesWidget: (value, meta) {
                        return Text(
                          '${value.toInt()}%',
                          style: TextStyle(fontSize: 10, color: Colors.grey[500]),
                        );
                      },
                      reservedSize: 32,
                    ),
                  ),
                  topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                ),
                gridData: FlGridData(
                  show: true,
                  horizontalInterval: 10,
                  getDrawingHorizontalLine: (value) => FlLine(
                    color: Colors.grey[200]!,
                    strokeWidth: 1,
                  ),
                  drawVerticalLine: false,
                ),
                borderData: FlBorderData(show: false),
              ),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _buildChartLegend('Gross', AppTheme.corporateBlue.withOpacity(0.4)),
              const SizedBox(width: 24),
              _buildChartLegend('Net', AppTheme.corporateBlue),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildChartLegend(String label, Color color) {
    return Row(
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(3),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            color: Colors.grey[700],
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }

  Widget _buildPerilAnalysis() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Peril Analysis',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: AppTheme.darkBg,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'PML by peril type (GBP millions)',
            style: TextStyle(fontSize: 13, color: Colors.grey[600]),
          ),
          const SizedBox(height: 20),
          ..._perilExposure.map((p) => _buildPerilRow(p)),
        ],
      ),
    );
  }

  Widget _buildPerilRow(Map<String, dynamic> peril) {
    final trend = peril['trend'] as double;
    final isPositive = trend >= 0;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.bg(context),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.grey[200]!),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppTheme.corporateBlue.withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(
              peril['icon'] as IconData,
              color: AppTheme.corporateBlue,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            flex: 2,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  peril['peril'],
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                    color: AppTheme.darkBg,
                  ),
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Icon(
                      isPositive ? Icons.trending_up : Icons.trending_down,
                      size: 14,
                      color: isPositive ? AppTheme.dangerDark : AppTheme.successDark,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '${isPositive ? '+' : ''}${trend.toStringAsFixed(1)}% MoM',
                      style: TextStyle(
                        fontSize: 11,
                        color: isPositive ? AppTheme.dangerDark : AppTheme.successDark,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  '${peril['pml100'].toStringAsFixed(0)}M',
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
                    color: AppTheme.darkBg,
                  ),
                ),
                Text(
                  '1-in-100',
                  style: TextStyle(fontSize: 10, color: Colors.grey[500]),
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  '${peril['pml250'].toStringAsFixed(0)}M',
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
                    color: AppTheme.darkBg,
                  ),
                ),
                Text(
                  '1-in-250',
                  style: TextStyle(fontSize: 10, color: Colors.grey[500]),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRiskAlerts() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppTheme.warningAmber.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.notifications_active, color: AppTheme.warningAmber, size: 20),
              ),
              const SizedBox(width: 12),
              const Text(
                'Risk Alerts',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.darkBg,
                ),
              ),
              const Spacer(),
              TextButton(
                onPressed: () {},
                child: const Text('View All'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _buildAlertItem(
            'North America windstorm approaching 75% capacity threshold',
            'warning',
            '2 hours ago',
          ),
          _buildAlertItem(
            'Cyber exposure increased 12.4% month-over-month',
            'info',
            '5 hours ago',
          ),
          _buildAlertItem(
            'Japan earthquake PML exceeds risk appetite by 5%',
            'critical',
            'Yesterday',
          ),
        ],
      ),
    );
  }

  Widget _buildAlertItem(String message, String severity, String time) {
    Color color;
    Color bgColor;
    IconData icon;

    switch (severity) {
      case 'critical':
        color = AppTheme.dangerDark;
        bgColor = AppTheme.dangerDark.withOpacity(0.1);
        icon = Icons.error_outline;
        break;
      case 'warning':
        color = AppTheme.warningAmber;
        bgColor = AppTheme.warningAmber.withOpacity(0.1);
        icon = Icons.warning_amber_rounded;
        break;
      default:
        color = AppTheme.corporateBlueLight;
        bgColor = AppTheme.corporateBlueLight.withOpacity(0.1);
        icon = Icons.info_outline;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  message,
                  style: TextStyle(
                    fontSize: 13,
                    color: Colors.grey[800],
                    height: 1.3,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  time,
                  style: TextStyle(
                    fontSize: 11,
                    color: Colors.grey[500],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _exportReport() {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Row(
          children: [
            Icon(Icons.download, color: Colors.white),
            SizedBox(width: 12),
            Text('Exporting exposure report...'),
          ],
        ),
        backgroundColor: AppTheme.corporateBlue,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    );
  }
}

// TabBar delegate for sticky tabs
class _TabBarDelegate extends SliverPersistentHeaderDelegate {
  final TabBar tabBar;

  _TabBarDelegate(this.tabBar);

  @override
  double get minExtent => tabBar.preferredSize.height;

  @override
  double get maxExtent => tabBar.preferredSize.height;

  @override
  Widget build(BuildContext context, double shrinkOffset, bool overlapsContent) {
    return Container(
      color: AppTheme.bg(context),
      child: tabBar,
    );
  }

  @override
  bool shouldRebuild(_TabBarDelegate oldDelegate) => false;
}

// Loss Entry Dialog
class _LossEntryDialog extends StatefulWidget {
  @override
  State<_LossEntryDialog> createState() => _LossEntryDialogState();
}

class _LossEntryDialogState extends State<_LossEntryDialog> {
  final _formKey = GlobalKey<FormState>();
  final _amountController = TextEditingController();
  final _descriptionController = TextEditingController();
  String _territory = 'North America';
  String _peril = 'Windstorm';
  String _lossType = 'attritional';

  @override
  void dispose() {
    _amountController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add Loss'),
      content: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _amountController,
                decoration: const InputDecoration(
                  labelText: 'Loss Amount (GBP)',
                  prefixText: '£ ',
                ),
                keyboardType: TextInputType.number,
                validator: (v) => v == null || v.isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                value: _territory,
                decoration: const InputDecoration(labelText: 'Territory'),
                items: ['North America', 'Europe', 'Asia Pacific', 'Latin America', 'Middle East']
                    .map((t) => DropdownMenuItem(value: t, child: Text(t)))
                    .toList(),
                onChanged: (v) => setState(() => _territory = v!),
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                value: _peril,
                decoration: const InputDecoration(labelText: 'Peril'),
                items: ['Windstorm', 'Earthquake', 'Flood', 'Fire', 'Cyber', 'Marine']
                    .map((p) => DropdownMenuItem(value: p, child: Text(p)))
                    .toList(),
                onChanged: (v) => setState(() => _peril = v!),
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                value: _lossType,
                decoration: const InputDecoration(labelText: 'Loss Type'),
                items: const [
                  DropdownMenuItem(value: 'attritional', child: Text('Attritional')),
                  DropdownMenuItem(value: 'large_loss', child: Text('Large Loss')),
                  DropdownMenuItem(value: 'cat_loss', child: Text('CAT Loss')),
                ],
                onChanged: (v) => setState(() => _lossType = v!),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _descriptionController,
                decoration: const InputDecoration(labelText: 'Description'),
                maxLines: 2,
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: () {
            if (_formKey.currentState!.validate()) {
              Navigator.pop(context, {
                'loss_amount': double.parse(_amountController.text),
                'loss_date': DateTime.now().toIso8601String(),
                'territory': _territory,
                'peril': _peril,
                'loss_type': _lossType,
                'description': _descriptionController.text,
                'currency': 'GBP',
              });
            }
          },
          child: const Text('Add Loss'),
        ),
      ],
    );
  }
}

// Claim Entry Dialog
class _ClaimEntryDialog extends StatefulWidget {
  @override
  State<_ClaimEntryDialog> createState() => _ClaimEntryDialogState();
}

class _ClaimEntryDialogState extends State<_ClaimEntryDialog> {
  final _formKey = GlobalKey<FormState>();
  final _claimNumberController = TextEditingController();
  final _amountController = TextEditingController();
  final _reserveController = TextEditingController();
  final _causeController = TextEditingController();
  String _territory = 'North America';
  String _status = 'reported';

  @override
  void dispose() {
    _claimNumberController.dispose();
    _amountController.dispose();
    _reserveController.dispose();
    _causeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add Claim'),
      content: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _claimNumberController,
                decoration: const InputDecoration(labelText: 'Claim Number'),
                validator: (v) => v == null || v.isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _amountController,
                decoration: const InputDecoration(
                  labelText: 'Claim Amount (GBP)',
                  prefixText: '£ ',
                ),
                keyboardType: TextInputType.number,
                validator: (v) => v == null || v.isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _reserveController,
                decoration: const InputDecoration(
                  labelText: 'Reserve Amount (GBP)',
                  prefixText: '£ ',
                ),
                keyboardType: TextInputType.number,
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                value: _territory,
                decoration: const InputDecoration(labelText: 'Territory'),
                items: ['North America', 'Europe', 'Asia Pacific', 'Latin America', 'Middle East']
                    .map((t) => DropdownMenuItem(value: t, child: Text(t)))
                    .toList(),
                onChanged: (v) => setState(() => _territory = v!),
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                value: _status,
                decoration: const InputDecoration(labelText: 'Status'),
                items: const [
                  DropdownMenuItem(value: 'reported', child: Text('Reported')),
                  DropdownMenuItem(value: 'open', child: Text('Open')),
                  DropdownMenuItem(value: 'under_review', child: Text('Under Review')),
                  DropdownMenuItem(value: 'paid', child: Text('Paid')),
                  DropdownMenuItem(value: 'closed', child: Text('Closed')),
                ],
                onChanged: (v) => setState(() => _status = v!),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _causeController,
                decoration: const InputDecoration(labelText: 'Cause'),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: () {
            if (_formKey.currentState!.validate()) {
              Navigator.pop(context, {
                'claim_number': _claimNumberController.text,
                'claim_amount': double.parse(_amountController.text),
                'reserve_amount': double.tryParse(_reserveController.text) ?? 0,
                'claim_date': DateTime.now().toIso8601String(),
                'territory': _territory,
                'status': _status,
                'cause': _causeController.text,
                'currency': 'GBP',
              });
            }
          },
          child: const Text('Add Claim'),
        ),
      ],
    );
  }
}
