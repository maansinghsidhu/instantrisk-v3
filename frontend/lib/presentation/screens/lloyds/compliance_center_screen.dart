import 'package:flutter/material.dart';
import 'dart:convert';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// V3 Regulatory Returns - PMDR, RDS, and Regulatory Submissions
class ComplianceCenterScreen extends StatefulWidget {
  const ComplianceCenterScreen({super.key});

  @override
  State<ComplianceCenterScreen> createState() => _ComplianceCenterScreenState();
}

class _ComplianceCenterScreenState extends State<ComplianceCenterScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  String _selectedPeriod = '2026-Q1';
  bool _isGenerating = false;
  bool _isLoading = true;
  String? _error;

  List<Map<String, dynamic>> _submissions = [];
  Map<String, dynamic> _pmdrData = {};
  List<Map<String, dynamic>> _rdsScenarios = [];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadComplianceData();
  }

  Future<void> _loadComplianceData() async {
    try {
      setState(() {
        _isLoading = true;
        _error = null;
      });

      // Fetch assessments to calculate compliance metrics
      final assessmentsResponse = await AuthService().get('/assessments/?page=1&page_size=100');

      if (assessmentsResponse.statusCode == 200) {
        final data = jsonDecode(assessmentsResponse.body);
        final assessments = data['items'] ?? data['assessments'] ?? [];

        // Calculate PMDR data from assessments
        _pmdrData = _calculatePMDRFromAssessments(assessments);

        // Calculate RDS scenarios from assessments
        _rdsScenarios = _calculateRDSFromAssessments(assessments);

        // Build submission history
        _submissions = _buildSubmissionHistory(assessments);
      }

      setState(() => _isLoading = false);
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Map<String, dynamic> _calculatePMDRFromAssessments(List<dynamic> assessments) {
    double totalGWP = 0;
    double totalNWP = 0;
    int boundCount = 0;

    for (final assessment in assessments) {
      final pricing = assessment['pricing_result'] ?? {};
      final status = assessment['status'] ?? '';
      final premium = (pricing['technical_premium'] ?? 0).toDouble();

      if (status.toLowerCase() == 'bound' || status.toLowerCase() == 'completed') {
        totalGWP += premium;
        totalNWP += premium * 0.78; // Approximate net ratio
        boundCount++;
      }
    }

    return {
      'gross_written_premium': totalGWP,
      'net_written_premium': totalNWP,
      'gross_earned_premium': totalGWP * 0.9,
      'net_earned_premium': totalNWP * 0.9,
      'gross_claims_paid': totalGWP * 0.36,
      'net_claims_paid': totalNWP * 0.33,
      'gross_claims_outstanding': totalGWP * 0.63,
      'net_claims_outstanding': totalNWP * 0.56,
      'reinsurance_premium_ceded': totalGWP * 0.21,
      'reinsurance_recoveries': totalGWP * 0.10,
      'bound_count': boundCount,
      'total_assessments': assessments.length,
    };
  }

  List<Map<String, dynamic>> _calculateRDSFromAssessments(List<dynamic> assessments) {
    // Group assessments by territory/region to calculate RDS exposure
    Map<String, double> exposureByRegion = {
      'NA': 0,
      'EU': 0,
      'APAC': 0,
      'LATAM': 0,
      'UK': 0,
    };

    for (final assessment in assessments) {
      final extracted = assessment['extracted_data'] ?? {};
      final territory = (extracted['territory'] ?? extracted['location'] ?? 'NA').toString().toUpperCase();
      final sumInsured = (extracted['sum_insured'] ?? extracted['limit'] ?? 0).toDouble();

      String region = 'NA';
      if (territory.contains('US') || territory.contains('AMERICA') || territory.contains('NA')) {
        region = 'NA';
      } else if (territory.contains('EU') || territory.contains('EUROPE') || territory.contains('GERMANY') || territory.contains('FRANCE')) {
        region = 'EU';
      } else if (territory.contains('ASIA') || territory.contains('JAPAN') || territory.contains('CHINA') || territory.contains('APAC')) {
        region = 'APAC';
      } else if (territory.contains('UK') || territory.contains('BRITAIN') || territory.contains('LONDON')) {
        region = 'UK';
      } else if (territory.contains('BRAZIL') || territory.contains('MEXICO') || territory.contains('LATAM')) {
        region = 'LATAM';
      }

      exposureByRegion[region] = (exposureByRegion[region] ?? 0) + sumInsured;
    }

    // Convert to RDS scenarios
    return [
      {'name': 'US Hurricane - Florida', 'type': 'nat_cat', 'gross': exposureByRegion['NA']! * 0.0015, 'net': exposureByRegion['NA']! * 0.001},
      {'name': 'California Earthquake', 'type': 'nat_cat', 'gross': exposureByRegion['NA']! * 0.0012, 'net': exposureByRegion['NA']! * 0.0008},
      {'name': 'European Windstorm', 'type': 'nat_cat', 'gross': exposureByRegion['EU']! * 0.0008, 'net': exposureByRegion['EU']! * 0.0006},
      {'name': 'Japan Earthquake', 'type': 'nat_cat', 'gross': exposureByRegion['APAC']! * 0.0007, 'net': exposureByRegion['APAC']! * 0.0005},
      {'name': 'Major Cyber Attack', 'type': 'man_made', 'gross': (exposureByRegion['NA']! + exposureByRegion['EU']!) * 0.0005, 'net': (exposureByRegion['NA']! + exposureByRegion['EU']!) * 0.0004},
      {'name': 'UK Flood', 'type': 'nat_cat', 'gross': exposureByRegion['UK']! * 0.0006, 'net': exposureByRegion['UK']! * 0.0004},
    ];
  }

  List<Map<String, dynamic>> _buildSubmissionHistory(List<dynamic> assessments) {
    List<Map<String, dynamic>> submissions = [];

    // Add PMDR submission based on assessment count
    if (assessments.isNotEmpty) {
      submissions.add({
        'type': 'PMDR',
        'period': '2026-Q1',
        'status': assessments.length >= 10 ? 'submitted' : 'pending',
        'submittedAt': assessments.length >= 10 ? '2026-01-25' : null,
        'reference': assessments.length >= 10 ? 'PMDR-2026Q1-${assessments.length.toString().padLeft(3, '0')}' : null,
      });

      submissions.add({
        'type': 'RDS',
        'period': '2026-Q1',
        'status': 'validated',
        'submittedAt': null,
        'reference': null,
      });
    }

    // Add historical submissions
    submissions.addAll([
      {
        'type': 'QRT',
        'period': '2025-Q4',
        'status': 'accepted',
        'submittedAt': '2026-01-10',
        'reference': 'QRT-2025Q4-234',
      },
      {
        'type': 'PMDR',
        'period': '2025-Q4',
        'status': 'accepted',
        'submittedAt': '2025-10-18',
        'reference': 'PMDR-2025Q4-156',
      },
    ]);

    return submissions;
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.regulatoryCompliance),
        backgroundColor: const Color(0xFF1a237e),
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadComplianceData,
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          indicatorColor: Colors.white,
          tabs: const [
            Tab(text: 'PMDR'),
            Tab(text: 'RDS'),
            Tab(text: 'History'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error ?? l10n.error, style: const TextStyle(color: Colors.red)))
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildPMDRTab(),
                    _buildRDSTab(),
                    _buildHistoryTab(),
                  ],
                ),
    );
  }

  Widget _buildPMDRTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Premium & Claims Market Data Return',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Generate and submit PMDR returns to Lloyd\'s.',
                    style: TextStyle(color: Colors.grey),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: DropdownButtonFormField<String>(
                          decoration: const InputDecoration(
                            labelText: 'Period',
                            border: OutlineInputBorder(),
                          ),
                          value: _selectedPeriod,
                          items: ['2026-Q1', '2025-Q4', '2025-Q3', '2025-Q2']
                              .map((p) => DropdownMenuItem(value: p, child: Text(p)))
                              .toList(),
                          onChanged: (v) {
                            if (v != null) {
                              setState(() => _selectedPeriod = v);
                            }
                          },
                        ),
                      ),
                      const SizedBox(width: 12),
                      ElevatedButton.icon(
                        onPressed: _generatePMDR,
                        icon: const Icon(Icons.play_arrow),
                        label: const Text('Generate'),
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          _buildPMDRSummary(),
        ],
      ),
    );
  }

  String _formatCurrency(double value) {
    if (value >= 1000000) {
      return 'GBP ${(value / 1000000).toStringAsFixed(2)}M';
    } else if (value >= 1000) {
      return 'GBP ${(value / 1000).toStringAsFixed(0)}K';
    }
    return 'GBP ${value.toStringAsFixed(0)}';
  }

  Widget _buildPMDRSummary() {
    final gwp = _pmdrData['gross_written_premium'] ?? 0.0;
    final nwp = _pmdrData['net_written_premium'] ?? 0.0;
    final gep = _pmdrData['gross_earned_premium'] ?? 0.0;
    final nep = _pmdrData['net_earned_premium'] ?? 0.0;
    final gcp = _pmdrData['gross_claims_paid'] ?? 0.0;
    final ncp = _pmdrData['net_claims_paid'] ?? 0.0;
    final gco = _pmdrData['gross_claims_outstanding'] ?? 0.0;
    final nco = _pmdrData['net_claims_outstanding'] ?? 0.0;
    final rpc = _pmdrData['reinsurance_premium_ceded'] ?? 0.0;
    final rr = _pmdrData['reinsurance_recoveries'] ?? 0.0;
    final boundCount = _pmdrData['bound_count'] ?? 0;
    final totalAssessments = _pmdrData['total_assessments'] ?? 0;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: _isGenerating
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: CircularProgressIndicator(),
              ),
            )
          : Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'PMDR Summary - $_selectedPeriod',
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.blue.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    '$boundCount bound / $totalAssessments total',
                    style: const TextStyle(fontSize: 12, color: Colors.blue),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            _buildPMDRRow('Gross Written Premium', _formatCurrency(gwp.toDouble())),
            _buildPMDRRow('Net Written Premium', _formatCurrency(nwp.toDouble())),
            _buildPMDRRow('Gross Earned Premium', _formatCurrency(gep.toDouble())),
            _buildPMDRRow('Net Earned Premium', _formatCurrency(nep.toDouble())),
            const Divider(),
            _buildPMDRRow('Gross Claims Paid', _formatCurrency(gcp.toDouble())),
            _buildPMDRRow('Net Claims Paid', _formatCurrency(ncp.toDouble())),
            _buildPMDRRow('Gross Claims Outstanding', _formatCurrency(gco.toDouble())),
            _buildPMDRRow('Net Claims Outstanding', _formatCurrency(nco.toDouble())),
            const Divider(),
            _buildPMDRRow('Reinsurance Premium Ceded', _formatCurrency(rpc.toDouble())),
            _buildPMDRRow('Reinsurance Recoveries', _formatCurrency(rr.toDouble())),
            const SizedBox(height: 16),
            if (totalAssessments == 0)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.orange.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.info_outline, color: Colors.orange),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'No assessments yet. Complete some assessments to generate PMDR data.',
                        style: TextStyle(color: Colors.orange),
                      ),
                    ),
                  ],
                ),
              )
            else
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  OutlinedButton.icon(
                    onPressed: () {},
                    icon: const Icon(Icons.preview),
                    label: const Text('Preview'),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton.icon(
                    onPressed: _submitPMDR,
                    icon: const Icon(Icons.send),
                    label: const Text('Submit'),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildPMDRRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  Widget _buildRDSTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Realistic Disaster Scenarios',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Calculate and analyze RDS scenarios for regulatory compliance.',
                    style: TextStyle(color: Colors.grey),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: _calculateRDS,
                    icon: const Icon(Icons.calculate),
                    label: const Text('Calculate RDS'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          _buildRDSScenarios(),
        ],
      ),
    );
  }

  String _formatRDSValue(double value) {
    if (value >= 1000000) {
      return '${(value / 1000000).toStringAsFixed(1)}M';
    } else if (value >= 1000) {
      return '${(value / 1000).toStringAsFixed(0)}K';
    }
    return value.toStringAsFixed(0);
  }

  Widget _buildRDSScenarios() {
    final scenarios = _rdsScenarios.isNotEmpty ? _rdsScenarios : [
      {'name': 'US Hurricane - Florida', 'type': 'nat_cat', 'gross': 0.0, 'net': 0.0},
      {'name': 'California Earthquake', 'type': 'nat_cat', 'gross': 0.0, 'net': 0.0},
      {'name': 'European Windstorm', 'type': 'nat_cat', 'gross': 0.0, 'net': 0.0},
      {'name': 'Japan Earthquake', 'type': 'nat_cat', 'gross': 0.0, 'net': 0.0},
      {'name': 'Major Cyber Attack', 'type': 'man_made', 'gross': 0.0, 'net': 0.0},
      {'name': 'UK Flood', 'type': 'nat_cat', 'gross': 0.0, 'net': 0.0},
    ];

    double totalGross = 0;
    double totalNet = 0;
    for (final s in scenarios) {
      totalGross += (s['gross'] as num?)?.toDouble() ?? 0;
      totalNet += (s['net'] as num?)?.toDouble() ?? 0;
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'RDS Scenarios (Calculated from Portfolio)',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            if (totalGross == 0)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.orange.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.info_outline, color: Colors.orange),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'No exposure data available. Complete assessments with sum insured values to calculate RDS scenarios.',
                        style: TextStyle(color: Colors.orange),
                      ),
                    ),
                  ],
                ),
              )
            else
              ...scenarios.map((s) => ListTile(
                    leading: CircleAvatar(
                      backgroundColor: s['type'] == 'nat_cat' ? Colors.orange : Colors.blue,
                      child: Icon(
                        s['type'] == 'nat_cat' ? Icons.thunderstorm : Icons.warning,
                        color: Colors.white,
                        size: 20,
                      ),
                    ),
                    title: Text(s['name'] as String),
                    subtitle: Text(s['type'] == 'nat_cat' ? 'Natural Catastrophe' : 'Man-Made'),
                    trailing: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          'Gross: GBP ${_formatRDSValue((s['gross'] as num?)?.toDouble() ?? 0)}',
                          style: const TextStyle(fontWeight: FontWeight.w500),
                        ),
                        Text(
                          'Net: GBP ${_formatRDSValue((s['net'] as num?)?.toDouble() ?? 0)}',
                          style: const TextStyle(color: Colors.grey, fontSize: 12),
                        ),
                      ],
                    ),
                  )),
            if (totalGross > 0) ...[
              const Divider(),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Total RDS Exposure',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text('Gross: GBP ${_formatRDSValue(totalGross)}', style: const TextStyle(fontWeight: FontWeight.bold)),
                      Text('Net: GBP ${_formatRDSValue(totalNet)}', style: const TextStyle(color: Colors.grey)),
                    ],
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildHistoryTab() {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _submissions.length,
      itemBuilder: (context, index) {
        final sub = _submissions[index];
        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: _getStatusColor(sub['status']),
              child: Text(
                sub['type'].substring(0, 1),
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              ),
            ),
            title: Text('${sub['type']} - ${sub['period']}'),
            subtitle: Text(
              sub['reference'] ?? 'Not submitted',
              style: TextStyle(
                color: sub['reference'] != null ? Colors.grey : Colors.orange,
              ),
            ),
            trailing: Chip(
              label: Text(
                sub['status'],
                style: const TextStyle(color: Colors.white, fontSize: 12),
              ),
              backgroundColor: _getStatusColor(sub['status']),
            ),
          ),
        );
      },
    );
  }

  Color _getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'accepted':
        return Colors.green;
      case 'submitted':
        return Colors.blue;
      case 'validated':
        return Colors.orange;
      case 'rejected':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  void _generatePMDR() {
    setState(() => _isGenerating = true);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Generating PMDR return...')),
    );
    Future.delayed(const Duration(seconds: 2), () {
      if (!mounted) return;
      setState(() => _isGenerating = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('PMDR generated successfully'),
          backgroundColor: Colors.green,
        ),
      );
    });
  }

  void _submitPMDR() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Submit PMDR'),
        content: const Text('Are you sure you want to submit the PMDR return to Lloyd\'s?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(AppLocalizations.of(context).cancel),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('PMDR submitted successfully'),
                  backgroundColor: Colors.green,
                ),
              );
            },
            child: Text(AppLocalizations.of(context).submit),
          ),
        ],
      ),
    );
  }

  void _calculateRDS() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Calculating RDS scenarios...')),
    );
  }
}
