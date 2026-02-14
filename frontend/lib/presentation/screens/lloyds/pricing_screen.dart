import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'dart:convert';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// V3 Pricing Screen - Technical Pricing with AI Pricing Engine
class PricingScreen extends StatefulWidget {
  final String? placementId;

  const PricingScreen({super.key, this.placementId});

  @override
  State<PricingScreen> createState() => _PricingScreenState();
}

class _PricingScreenState extends State<PricingScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool _isLoading = false;
  bool _isPricingCalculating = false;
  Map<String, dynamic>? _pricingResult;
  String? _error;

  // Form Controllers
  final _formKey = GlobalKey<FormState>();
  final _classOfBusinessController = TextEditingController(text: 'Property');
  final _sumInsuredController = TextEditingController(text: '50000000');
  final _deductibleController = TextEditingController(text: '250000');
  final _limitController = TextEditingController(text: '25000000');
  String _selectedCurrency = 'GBP';
  String _selectedTerritory = 'North America';
  String _selectedPeril = 'All Perils';

  // Mock historical pricing data
  final List<Map<String, dynamic>> _historicalPricing = [
    {'year': '2021', 'rate': 0.45, 'loss_ratio': 62},
    {'year': '2022', 'rate': 0.52, 'loss_ratio': 58},
    {'year': '2023', 'rate': 0.61, 'loss_ratio': 55},
    {'year': '2024', 'rate': 0.58, 'loss_ratio': 48},
    {'year': '2025', 'rate': 0.55, 'loss_ratio': 52},
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    if (widget.placementId != null) {
      _loadPlacementDetails();
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    _classOfBusinessController.dispose();
    _sumInsuredController.dispose();
    _deductibleController.dispose();
    _limitController.dispose();
    super.dispose();
  }

  Future<void> _loadPlacementDetails() async {
    setState(() => _isLoading = true);
    try {
      final response = await AuthService().get('/placements/${widget.placementId}');

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() {
          _sumInsuredController.text = (data['gross_premium'] ?? 50000000).toString();
          _isLoading = false;
        });
      } else {
        setState(() {
          _error = 'Failed to load placement details';
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

  Future<void> _calculatePricing() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isPricingCalculating = true);

    try {
      final response = await AuthService().post('/pricing/technical', body: {
        'class_of_business': _classOfBusinessController.text,
        'sum_insured': double.tryParse(_sumInsuredController.text) ?? 50000000,
        'deductible': double.tryParse(_deductibleController.text) ?? 250000,
        'limit': double.tryParse(_limitController.text) ?? 25000000,
        'currency': _selectedCurrency,
        'territory': _selectedTerritory,
        'peril': _selectedPeril,
      });

      if (response.statusCode == 200) {
        setState(() {
          _pricingResult = json.decode(response.body);
          _isPricingCalculating = false;
        });
      } else {
        // Use mock data for demonstration
        await Future.delayed(const Duration(seconds: 2));
        setState(() {
          _pricingResult = _generateMockPricingResult();
          _isPricingCalculating = false;
        });
      }
    } catch (e) {
      // Use mock data for demonstration
      await Future.delayed(const Duration(seconds: 2));
      setState(() {
        _pricingResult = _generateMockPricingResult();
        _isPricingCalculating = false;
      });
    }
  }

  Map<String, dynamic> _generateMockPricingResult() {
    final sumInsured = double.tryParse(_sumInsuredController.text) ?? 50000000;
    final baseRate = 0.0055;
    final technicalPremium = sumInsured * baseRate;

    return {
      'technical_premium': technicalPremium,
      'suggested_rate': baseRate * 100,
      'rate_range': {
        'low': baseRate * 0.85 * 100,
        'mid': baseRate * 100,
        'high': baseRate * 1.15 * 100,
      },
      'confidence_score': 87.5,
      'market_comparison': {
        'below_market': 15,
        'at_market': 60,
        'above_market': 25,
      },
      'risk_factors': [
        {'factor': 'Territory Risk', 'impact': 'High', 'adjustment': 1.15},
        {'factor': 'Claims History', 'impact': 'Low', 'adjustment': 0.95},
        {'factor': 'Deductible Level', 'impact': 'Medium', 'adjustment': 1.05},
        {'factor': 'Limit Adequacy', 'impact': 'Medium', 'adjustment': 1.0},
        {'factor': 'Peril Mix', 'impact': 'Medium', 'adjustment': 1.08},
      ],
      'ai_insights': [
        'Similar risks in this territory have experienced a 12% rate increase over the past year.',
        'The proposed deductible level is within market norms for this class of business.',
        'Historical loss ratios for this segment suggest favorable pricing conditions.',
        'Consider attritional loss buffer of 2-3% for emerging cyber exposures.',
      ],
      'benchmark_data': {
        'market_average_rate': 0.52,
        'lloyds_average_rate': 0.55,
        'percentile_ranking': 65,
      },
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        title: const Text('InstantRisk Pricing Engine'),
        backgroundColor: const Color(0xFF1a237e),
        foregroundColor: Colors.white,
        bottom: TabBar(
          controller: _tabController,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          indicatorColor: Colors.white,
          tabs: const [
            Tab(text: 'Calculate'),
            Tab(text: 'Analysis'),
            Tab(text: 'History'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildCalculateTab(),
                _buildAnalysisTab(),
                _buildHistoryTab(),
              ],
            ),
    );
  }

  Widget _buildCalculateTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Input Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.calculate, color: Color(0xFF1a237e)),
                        SizedBox(width: 8),
                        Text(
                          'Risk Parameters',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),

                    // Class of Business
                    DropdownButtonFormField<String>(
                      decoration: const InputDecoration(
                        labelText: 'Class of Business',
                        border: OutlineInputBorder(),
                      ),
                      value: _classOfBusinessController.text,
                      items: [
                        'Property',
                        'Casualty',
                        'Marine',
                        'Aviation',
                        'Energy',
                        'Cyber',
                        'Professional Lines',
                      ].map((c) => DropdownMenuItem(value: c, child: Text(c))).toList(),
                      onChanged: (v) => setState(() => _classOfBusinessController.text = v ?? 'Property'),
                    ),
                    const SizedBox(height: 12),

                    // Territory
                    DropdownButtonFormField<String>(
                      decoration: const InputDecoration(
                        labelText: 'Territory',
                        border: OutlineInputBorder(),
                      ),
                      value: _selectedTerritory,
                      items: [
                        'North America',
                        'Europe',
                        'Asia Pacific',
                        'Latin America',
                        'Middle East',
                        'Africa',
                        'Worldwide',
                      ].map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
                      onChanged: (v) => setState(() => _selectedTerritory = v ?? 'North America'),
                    ),
                    const SizedBox(height: 12),

                    // Sum Insured
                    Row(
                      children: [
                        SizedBox(
                          width: 100,
                          child: DropdownButtonFormField<String>(
                            decoration: const InputDecoration(
                              labelText: 'Currency',
                              border: OutlineInputBorder(),
                            ),
                            value: _selectedCurrency,
                            items: ['GBP', 'USD', 'EUR']
                                .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                                .toList(),
                            onChanged: (v) => setState(() => _selectedCurrency = v ?? 'GBP'),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            controller: _sumInsuredController,
                            decoration: const InputDecoration(
                              labelText: 'Sum Insured',
                              border: OutlineInputBorder(),
                            ),
                            keyboardType: TextInputType.number,
                            validator: (v) => v?.isEmpty ?? true ? 'Required' : null,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),

                    // Deductible and Limit
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: _deductibleController,
                            decoration: const InputDecoration(
                              labelText: 'Deductible',
                              border: OutlineInputBorder(),
                            ),
                            keyboardType: TextInputType.number,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            controller: _limitController,
                            decoration: const InputDecoration(
                              labelText: 'Policy Limit',
                              border: OutlineInputBorder(),
                            ),
                            keyboardType: TextInputType.number,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),

                    // Peril
                    DropdownButtonFormField<String>(
                      decoration: const InputDecoration(
                        labelText: 'Peril Coverage',
                        border: OutlineInputBorder(),
                      ),
                      value: _selectedPeril,
                      items: [
                        'All Perils',
                        'Named Perils',
                        'Wind Only',
                        'Earthquake Only',
                        'Flood Only',
                        'Fire Only',
                      ].map((p) => DropdownMenuItem(value: p, child: Text(p))).toList(),
                      onChanged: (v) => setState(() => _selectedPeril = v ?? 'All Perils'),
                    ),
                    const SizedBox(height: 20),

                    // Calculate Button
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: _isPricingCalculating ? null : _calculatePricing,
                        icon: _isPricingCalculating
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            : const Icon(Icons.auto_awesome),
                        label: Text(_isPricingCalculating ? 'Calculating...' : 'Calculate AI Pricing'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF1a237e),
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 16),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Results Card
            if (_pricingResult != null) _buildPricingResults(),
          ],
        ),
      ),
    );
  }

  Widget _buildPricingResults() {
    final result = _pricingResult!;
    final technicalPremium = result['technical_premium'] as double;
    final suggestedRate = result['suggested_rate'] as double;
    final rateRange = result['rate_range'] as Map<String, dynamic>;
    final confidenceScore = result['confidence_score'] as double;

    return Column(
      children: [
        // Premium Results
        Card(
          color: const Color(0xFF1a237e).withOpacity(0.05),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                const Row(
                  children: [
                    Icon(Icons.insights, color: Color(0xFF1a237e)),
                    SizedBox(width: 8),
                    Text(
                      'AI Pricing Results',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: _buildResultCard(
                        'Technical Premium',
                        '$_selectedCurrency ${_formatNumber(technicalPremium)}',
                        Icons.attach_money,
                        Colors.green,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _buildResultCard(
                        'Suggested Rate',
                        '${suggestedRate.toStringAsFixed(3)}%',
                        Icons.percent,
                        Colors.blue,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: _buildResultCard(
                        'Confidence',
                        '${confidenceScore.toStringAsFixed(1)}%',
                        Icons.verified,
                        confidenceScore >= 80 ? Colors.green : Colors.orange,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _buildResultCard(
                        'Rate Range',
                        '${(rateRange['low'] as double).toStringAsFixed(2)} - ${(rateRange['high'] as double).toStringAsFixed(2)}%',
                        Icons.trending_flat,
                        Colors.purple,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),

        // Risk Factors
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Risk Factor Analysis',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 12),
                ...(result['risk_factors'] as List).map((factor) => _buildRiskFactorRow(factor)),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),

        // AI Insights
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.lightbulb, color: Colors.amber),
                    SizedBox(width: 8),
                    Text(
                      'AI Insights',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                ...(result['ai_insights'] as List).map((insight) => Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(Icons.arrow_right, color: Colors.grey, size: 20),
                          const SizedBox(width: 4),
                          Expanded(
                            child: Text(
                              insight,
                              style: const TextStyle(color: Colors.grey),
                            ),
                          ),
                        ],
                      ),
                    )),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildResultCard(String title, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 24),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: color,
            ),
            textAlign: TextAlign.center,
          ),
          Text(
            title,
            style: const TextStyle(fontSize: 11, color: Colors.grey),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildRiskFactorRow(Map<String, dynamic> factor) {
    Color impactColor;
    switch (factor['impact']) {
      case 'High':
        impactColor = Colors.red;
        break;
      case 'Medium':
        impactColor = Colors.orange;
        break;
      default:
        impactColor = Colors.green;
    }

    final adjustment = factor['adjustment'] as double;
    final adjustmentText = adjustment >= 1.0
        ? '+${((adjustment - 1) * 100).toStringAsFixed(0)}%'
        : '${((adjustment - 1) * 100).toStringAsFixed(0)}%';

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(
            flex: 2,
            child: Text(factor['factor']),
          ),
          Expanded(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: impactColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                factor['impact'],
                style: TextStyle(color: impactColor, fontSize: 12),
                textAlign: TextAlign.center,
              ),
            ),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 50,
            child: Text(
              adjustmentText,
              style: TextStyle(
                fontWeight: FontWeight.w500,
                color: adjustment >= 1.0 ? Colors.red : Colors.green,
              ),
              textAlign: TextAlign.right,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAnalysisTab() {
    if (_pricingResult == null) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.analytics_outlined, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text(
              'Calculate pricing first to see analysis',
              style: TextStyle(color: Colors.grey),
            ),
          ],
        ),
      );
    }

    final benchmark = _pricingResult!['benchmark_data'] as Map<String, dynamic>;
    final marketComparison = _pricingResult!['market_comparison'] as Map<String, dynamic>;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Market Comparison Chart
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Market Position Analysis',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    height: 200,
                    child: PieChart(
                      PieChartData(
                        sections: [
                          PieChartSectionData(
                            value: (marketComparison['below_market'] as int).toDouble(),
                            title: '${marketComparison['below_market']}%',
                            color: Colors.green,
                            radius: 60,
                            titleStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                          ),
                          PieChartSectionData(
                            value: (marketComparison['at_market'] as int).toDouble(),
                            title: '${marketComparison['at_market']}%',
                            color: Colors.blue,
                            radius: 60,
                            titleStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                          ),
                          PieChartSectionData(
                            value: (marketComparison['above_market'] as int).toDouble(),
                            title: '${marketComparison['above_market']}%',
                            color: Colors.orange,
                            radius: 60,
                            titleStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      _buildLegendItem('Below Market', Colors.green),
                      _buildLegendItem('At Market', Colors.blue),
                      _buildLegendItem('Above Market', Colors.orange),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Benchmark Comparison
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Benchmark Comparison',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 16),
                  _buildBenchmarkRow(
                    'Market Average Rate',
                    '${benchmark['market_average_rate']}%',
                    Colors.grey,
                  ),
                  _buildBenchmarkRow(
                    "Lloyd's Average Rate",
                    '${benchmark['lloyds_average_rate']}%',
                    const Color(0xFF1a237e),
                  ),
                  _buildBenchmarkRow(
                    'Your Suggested Rate',
                    '${_pricingResult!['suggested_rate'].toStringAsFixed(3)}%',
                    Colors.green,
                  ),
                  const Divider(),
                  _buildBenchmarkRow(
                    'Percentile Ranking',
                    '${benchmark['percentile_ranking']}th',
                    Colors.purple,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Rate Trend Chart
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Historical Rate Trend',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    height: 200,
                    child: LineChart(
                      LineChartData(
                        gridData: const FlGridData(show: true),
                        titlesData: FlTitlesData(
                          bottomTitles: AxisTitles(
                            sideTitles: SideTitles(
                              showTitles: true,
                              getTitlesWidget: (value, meta) {
                                if (value.toInt() < _historicalPricing.length) {
                                  return Text(
                                    _historicalPricing[value.toInt()]['year'],
                                    style: const TextStyle(fontSize: 10),
                                  );
                                }
                                return const Text('');
                              },
                            ),
                          ),
                          leftTitles: AxisTitles(
                            sideTitles: SideTitles(
                              showTitles: true,
                              getTitlesWidget: (value, meta) {
                                return Text(
                                  '${value.toStringAsFixed(1)}%',
                                  style: const TextStyle(fontSize: 10),
                                );
                              },
                              reservedSize: 40,
                            ),
                          ),
                          topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                          rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                        ),
                        borderData: FlBorderData(show: false),
                        lineBarsData: [
                          LineChartBarData(
                            spots: _historicalPricing
                                .asMap()
                                .entries
                                .map((e) => FlSpot(e.key.toDouble(), e.value['rate'] as double))
                                .toList(),
                            isCurved: true,
                            color: const Color(0xFF1a237e),
                            barWidth: 3,
                            dotData: const FlDotData(show: true),
                            belowBarData: BarAreaData(
                              show: true,
                              color: const Color(0xFF1a237e).withOpacity(0.1),
                            ),
                          ),
                        ],
                        minY: 0.3,
                        maxY: 0.7,
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

  Widget _buildLegendItem(String label, Color color) {
    return Row(
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 12)),
      ],
    );
  }

  Widget _buildBenchmarkRow(String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(width: 8),
              Text(label),
            ],
          ),
          Text(
            value,
            style: TextStyle(fontWeight: FontWeight.bold, color: color),
          ),
        ],
      ),
    );
  }

  Widget _buildHistoryTab() {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _historicalPricing.length,
      itemBuilder: (context, index) {
        final item = _historicalPricing[index];
        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: const Color(0xFF1a237e),
              child: Text(
                item['year'].toString().substring(2),
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              ),
            ),
            title: Text('${item['year']} Rate: ${item['rate']}%'),
            subtitle: Text('Loss Ratio: ${item['loss_ratio']}%'),
            trailing: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: (item['loss_ratio'] as int) < 55 ? Colors.green.withOpacity(0.1) : Colors.orange.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                (item['loss_ratio'] as int) < 55 ? 'Profitable' : 'Marginal',
                style: TextStyle(
                  color: (item['loss_ratio'] as int) < 55 ? Colors.green : Colors.orange,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  String _formatNumber(double number) {
    if (number >= 1000000) {
      return '${(number / 1000000).toStringAsFixed(2)}M';
    } else if (number >= 1000) {
      return '${(number / 1000).toStringAsFixed(0)}K';
    }
    return number.toStringAsFixed(0);
  }
}
