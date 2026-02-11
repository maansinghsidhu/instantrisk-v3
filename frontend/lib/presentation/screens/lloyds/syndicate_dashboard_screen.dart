import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// V3 Syndicate Dashboard - Lloyd's Market Overview
class SyndicateDashboardScreen extends StatefulWidget {
  const SyndicateDashboardScreen({super.key});

  @override
  State<SyndicateDashboardScreen> createState() => _SyndicateDashboardScreenState();
}

class _SyndicateDashboardScreenState extends State<SyndicateDashboardScreen> {
  bool _isLoading = true;
  List<dynamic> _recentPlacements = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadDashboardData();
  }

  Future<void> _loadDashboardData() async {
    try {
      final placementsResponse = await AuthService().get('/placements/');

      if (placementsResponse.statusCode == 200) {
        final data = json.decode(placementsResponse.body);
        final placements = data['placements'] ?? data ?? [];
        setState(() {
          _recentPlacements = placements is List ? placements : [];
          _isLoading = false;
        });
      } else {
        setState(() {
          _error = 'Failed to load dashboard data';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Syndicate Dashboard'),
        backgroundColor: const Color(0xFF1a237e),
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              setState(() => _isLoading = true);
              _loadDashboardData();
            },
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!, style: const TextStyle(color: Colors.red)))
              : RefreshIndicator(
                  onRefresh: _loadDashboardData,
                  child: SingleChildScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // KPI Cards Row
                        _buildKPICards(),
                        const SizedBox(height: 24),

                        // Exposure Chart
                        _buildExposureChart(),
                        const SizedBox(height: 24),

                        // Recent Placements
                        _buildRecentPlacements(),
                        const SizedBox(height: 24),

                        // Quick Actions
                        _buildQuickActions(),
                      ],
                    ),
                  ),
                ),
    );
  }

  Widget _buildKPICards() {
    final screenWidth = MediaQuery.of(context).size.width;
    final isWideScreen = screenWidth > 800;

    final cards = [
      _buildKPICard('Active Placements', '${_recentPlacements.length}', Icons.assignment, Colors.blue),
      _buildKPICard('Total GWP', 'GBP 2.5M', Icons.attach_money, Colors.green),
      _buildKPICard('Avg Line Size', '15.2%', Icons.pie_chart, Colors.orange),
      _buildKPICard('Capacity Used', '67%', Icons.speed, Colors.purple),
    ];

    if (isWideScreen) {
      // Web view: single row with 4 compact cards
      return Row(
        children: cards.map((card) => Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 6),
            child: card,
          ),
        )).toList(),
      );
    } else {
      // Mobile view: 2x2 grid
      return GridView.count(
        crossAxisCount: 2,
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        childAspectRatio: 1.5,
        children: cards,
      );
    }
  }

  Widget _buildKPICard(String title, String value, IconData icon, Color color) {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: color, size: 28),
            const SizedBox(height: 8),
            Text(
              value,
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
            Text(
              title,
              style: const TextStyle(fontSize: 12, color: Colors.grey),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildExposureChart() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Exposure by Zone',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            SizedBox(
              height: 200,
              child: PieChart(
                PieChartData(
                  sections: [
                    PieChartSectionData(
                      value: 35,
                      title: 'NA',
                      color: Colors.blue,
                      radius: 60,
                    ),
                    PieChartSectionData(
                      value: 30,
                      title: 'EU',
                      color: Colors.green,
                      radius: 60,
                    ),
                    PieChartSectionData(
                      value: 20,
                      title: 'APAC',
                      color: Colors.orange,
                      radius: 60,
                    ),
                    PieChartSectionData(
                      value: 15,
                      title: 'Other',
                      color: Colors.grey,
                      radius: 60,
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRecentPlacements() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Recent Placements',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                TextButton(
                  onPressed: () => context.go('/lloyds/placements'),
                  child: const Text('View All'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            if (_recentPlacements.isEmpty)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text('No placements yet'),
              )
            else
              ...(_recentPlacements.take(5).map((p) => ListTile(
                    leading: CircleAvatar(
                      backgroundColor: _getStatusColor(p['status'] ?? 'pending'),
                      child: const Icon(Icons.description, color: Colors.white, size: 20),
                    ),
                    title: Text(p['umr'] ?? 'Unknown UMR'),
                    subtitle: Text('Line: ${p['total_line'] ?? 0}%'),
                    trailing: Chip(
                      label: Text(
                        p['status'] ?? 'pending',
                        style: const TextStyle(fontSize: 10, color: Colors.white),
                      ),
                      backgroundColor: _getStatusColor(p['status'] ?? 'pending'),
                    ),
                  ))),
          ],
        ),
      ),
    );
  }

  Color _getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'bound':
        return Colors.green;
      case 'placing':
        return Colors.blue;
      case 'quoting':
        return Colors.orange;
      case 'declined':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  Widget _buildQuickActions() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Quick Actions',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ElevatedButton.icon(
                  onPressed: () => context.go('/lloyds/placements'),
                  icon: const Icon(Icons.add),
                  label: const Text('New Placement'),
                ),
                ElevatedButton.icon(
                  onPressed: () => context.go('/lloyds/exposure'),
                  icon: const Icon(Icons.analytics),
                  label: const Text('View Exposure'),
                ),
                ElevatedButton.icon(
                  onPressed: () => context.go('/lloyds/compliance'),
                  icon: const Icon(Icons.verified_user),
                  label: const Text('Compliance'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
