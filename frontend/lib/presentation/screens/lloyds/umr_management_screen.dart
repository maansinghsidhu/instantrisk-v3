import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'dart:convert';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// V3 UMR Management Screen - UMR Generation and Management
class UMRManagementScreen extends StatefulWidget {
  const UMRManagementScreen({super.key});

  @override
  State<UMRManagementScreen> createState() => _UMRManagementScreenState();
}

class _UMRManagementScreenState extends State<UMRManagementScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool _isLoading = true;
  bool _isGenerating = false;
  List<Map<String, dynamic>> _umrList = [];
  String? _error;
  String? _generatedUMR;

  // Generation form controllers
  final _syndicateController = TextEditingController(text: '1234');
  final _brokerCodeController = TextEditingController(text: 'ABC');
  final _sequenceController = TextEditingController();
  String _selectedYear = '2026';

  // Search controller
  final _searchController = TextEditingController();
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadUMRList();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _syndicateController.dispose();
    _brokerCodeController.dispose();
    _sequenceController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadUMRList() async {
    try {
      final response = await AuthService().get('/placements/');

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final list = data['placements'] ?? data ?? [];
        setState(() {
          _umrList = (list as List).map((e) => e as Map<String, dynamic>).toList();
          _isLoading = false;
        });
      } else {
        // Use mock data
        await Future.delayed(const Duration(milliseconds: 500));
        setState(() {
          _umrList = _generateMockUMRList();
          _isLoading = false;
        });
      }
    } catch (e) {
      await Future.delayed(const Duration(milliseconds: 500));
      setState(() {
        _umrList = _generateMockUMRList();
        _isLoading = false;
      });
    }
  }

  List<Map<String, dynamic>> _generateMockUMRList() {
    return [
      {
        'umr': 'B0999261234ABC001',
        'status': 'bound',
        'created_at': '2026-01-15',
        'syndicate': '1234',
        'broker': 'ABC',
        'insured': 'Global Corp Ltd',
        'class': 'Property',
        'premium': 250000,
        'currency': 'GBP',
      },
      {
        'umr': 'B0999261234ABC002',
        'status': 'placing',
        'created_at': '2026-01-18',
        'syndicate': '1234',
        'broker': 'ABC',
        'insured': 'Tech Industries Inc',
        'class': 'Cyber',
        'premium': 175000,
        'currency': 'USD',
      },
      {
        'umr': 'B0999261234DEF001',
        'status': 'quoting',
        'created_at': '2026-01-20',
        'syndicate': '1234',
        'broker': 'DEF',
        'insured': 'Maritime Holdings',
        'class': 'Marine',
        'premium': 500000,
        'currency': 'GBP',
      },
      {
        'umr': 'B0999265678XYZ001',
        'status': 'bound',
        'created_at': '2026-01-10',
        'syndicate': '5678',
        'broker': 'XYZ',
        'insured': 'Aviation Partners',
        'class': 'Aviation',
        'premium': 1250000,
        'currency': 'USD',
      },
      {
        'umr': 'B0999261234ABC003',
        'status': 'marketing',
        'created_at': '2026-01-22',
        'syndicate': '1234',
        'broker': 'ABC',
        'insured': 'Energy Solutions',
        'class': 'Energy',
        'premium': 850000,
        'currency': 'GBP',
      },
      {
        'umr': 'B0999269012GHI001',
        'status': 'declined',
        'created_at': '2026-01-05',
        'syndicate': '9012',
        'broker': 'GHI',
        'insured': 'Risk Ventures',
        'class': 'Casualty',
        'premium': 320000,
        'currency': 'EUR',
      },
    ];
  }

  Future<void> _generateUMR() async {
    if (_syndicateController.text.length != 4) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Syndicate number must be 4 digits'),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

    if (_brokerCodeController.text.length != 3) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Broker code must be 3 characters'),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

    setState(() => _isGenerating = true);

    try {
      final response = await AuthService().post('/umr/generate', body: {
        'syndicate': _syndicateController.text,
        'broker_code': _brokerCodeController.text,
        'year': _selectedYear,
      });

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() {
          _generatedUMR = data['umr'];
          _isGenerating = false;
        });
      } else {
        // Generate mock UMR
        await Future.delayed(const Duration(seconds: 1));
        _generateMockUMR();
      }
    } catch (e) {
      await Future.delayed(const Duration(seconds: 1));
      _generateMockUMR();
    }
  }

  void _generateMockUMR() {
    final year = _selectedYear.substring(2);
    final syndicate = _syndicateController.text;
    final broker = _brokerCodeController.text.toUpperCase();

    // Get next sequence number
    final existingUMRs = _umrList.where((u) {
      final umr = u['umr'] as String;
      return umr.contains(syndicate) && umr.contains(broker);
    }).toList();

    final sequence = (existingUMRs.length + 1).toString().padLeft(3, '0');

    setState(() {
      _generatedUMR = 'B099$year$syndicate$broker$sequence';
      _isGenerating = false;
    });
  }

  List<Map<String, dynamic>> get _filteredUMRList {
    if (_searchQuery.isEmpty) return _umrList;
    return _umrList.where((umr) {
      final searchLower = _searchQuery.toLowerCase();
      return (umr['umr'] as String).toLowerCase().contains(searchLower) ||
          (umr['insured'] as String).toLowerCase().contains(searchLower) ||
          (umr['class'] as String).toLowerCase().contains(searchLower);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.umrManagement),
        backgroundColor: const Color(0xFF1a237e),
        foregroundColor: Colors.white,
        bottom: TabBar(
          controller: _tabController,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          indicatorColor: Colors.white,
          tabs: [
            Tab(text: l10n.umrGenerate),
            Tab(text: l10n.umrRegistry),
            Tab(text: l10n.umrValidation),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildGenerateTab(),
                _buildRegistryTab(),
                _buildValidationTab(),
              ],
            ),
    );
  }

  Widget _buildGenerateTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // UMR Format Info Card
          Card(
            color: const Color(0xFF1a237e).withOpacity(0.05),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.info_outline, color: Color(0xFF1a237e)),
                      SizedBox(width: 8),
                      Text(
                        'UMR Format Standard',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFF1a237e),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.grey[300]!),
                    ),
                    child: const Column(
                      children: [
                        Text(
                          'B099 26 1234 ABC 001',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                            fontFamily: 'monospace',
                            letterSpacing: 2,
                          ),
                        ),
                        SizedBox(height: 8),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                          children: [
                            _FormatPart(label: 'Prefix', value: 'B099'),
                            _FormatPart(label: 'Year', value: '26'),
                            _FormatPart(label: 'Syndicate', value: '1234'),
                            _FormatPart(label: 'Broker', value: 'ABC'),
                            _FormatPart(label: 'Seq', value: '001'),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Generation Form Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Generate New UMR',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 16),

                  // Year Selection
                  DropdownButtonFormField<String>(
                    decoration: const InputDecoration(
                      labelText: 'Year',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.calendar_today),
                    ),
                    value: _selectedYear,
                    items: ['2024', '2025', '2026', '2027']
                        .map((y) => DropdownMenuItem(value: y, child: Text(y)))
                        .toList(),
                    onChanged: (v) => setState(() => _selectedYear = v ?? '2026'),
                  ),
                  const SizedBox(height: 12),

                  // Syndicate Number
                  TextFormField(
                    controller: _syndicateController,
                    decoration: const InputDecoration(
                      labelText: 'Syndicate Number',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.business),
                      hintText: '4 digits (e.g., 1234)',
                    ),
                    keyboardType: TextInputType.number,
                    maxLength: 4,
                    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  ),
                  const SizedBox(height: 12),

                  // Broker Code
                  TextFormField(
                    controller: _brokerCodeController,
                    decoration: const InputDecoration(
                      labelText: 'Broker Code',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.badge),
                      hintText: '3 characters (e.g., ABC)',
                    ),
                    maxLength: 3,
                    textCapitalization: TextCapitalization.characters,
                    inputFormatters: [
                      FilteringTextInputFormatter.allow(RegExp(r'[A-Za-z]')),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Generate Button
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: _isGenerating ? null : _generateUMR,
                      icon: _isGenerating
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Icon(Icons.add_circle),
                      label: Text(_isGenerating ? 'Generating...' : 'Generate UMR'),
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

          // Generated UMR Result
          if (_generatedUMR != null)
            Card(
              color: Colors.green.withOpacity(0.1),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.check_circle, color: Colors.green),
                        SizedBox(width: 8),
                        Text(
                          'UMR Generated Successfully',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: Colors.green,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.green),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            _generatedUMR!,
                            style: const TextStyle(
                              fontSize: 24,
                              fontWeight: FontWeight.bold,
                              fontFamily: 'monospace',
                              letterSpacing: 2,
                            ),
                          ),
                          const SizedBox(width: 12),
                          IconButton(
                            icon: const Icon(Icons.copy),
                            onPressed: () {
                              Clipboard.setData(ClipboardData(text: _generatedUMR!));
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('UMR copied to clipboard')),
                              );
                            },
                            tooltip: 'Copy UMR',
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: [
                        ElevatedButton.icon(
                          onPressed: () {
                            _tabController.animateTo(1);
                          },
                          icon: const Icon(Icons.visibility),
                          label: const Text('View in Registry'),
                        ),
                        OutlinedButton.icon(
                          onPressed: () {
                            setState(() => _generatedUMR = null);
                          },
                          icon: const Icon(Icons.add),
                          label: const Text('Generate Another'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildRegistryTab() {
    return Column(
      children: [
        // Search Bar
        Padding(
          padding: const EdgeInsets.all(16),
          child: TextField(
            controller: _searchController,
            decoration: InputDecoration(
              hintText: 'Search by UMR, insured, or class...',
              prefixIcon: const Icon(Icons.search),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              suffixIcon: _searchQuery.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear),
                      onPressed: () {
                        _searchController.clear();
                        setState(() => _searchQuery = '');
                      },
                    )
                  : null,
            ),
            onChanged: (value) => setState(() => _searchQuery = value),
          ),
        ),

        // Stats Row
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            children: [
              _buildStatChip('Total', _umrList.length, Colors.blue),
              const SizedBox(width: 8),
              _buildStatChip(
                'Bound',
                _umrList.where((u) => u['status'] == 'bound').length,
                Colors.green,
              ),
              const SizedBox(width: 8),
              _buildStatChip(
                'Active',
                _umrList.where((u) => u['status'] == 'placing' || u['status'] == 'quoting').length,
                Colors.orange,
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),

        // UMR List
        Expanded(
          child: RefreshIndicator(
            onRefresh: _loadUMRList,
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _filteredUMRList.length,
              itemBuilder: (context, index) {
                final umr = _filteredUMRList[index];
                return _buildUMRCard(umr);
              },
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildStatChip(String label, int count, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          children: [
            Text(
              count.toString(),
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildUMRCard(Map<String, dynamic> umr) {
    final status = umr['status'] as String;
    final statusColor = _getStatusColor(status);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: () => _showUMRDetails(umr),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Text(
                        umr['umr'],
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                          fontFamily: 'monospace',
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton(
                        icon: const Icon(Icons.copy, size: 18),
                        onPressed: () {
                          Clipboard.setData(ClipboardData(text: umr['umr']));
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('UMR copied')),
                          );
                        },
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(),
                      ),
                    ],
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: statusColor.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      status.toUpperCase(),
                      style: TextStyle(
                        color: statusColor,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  const Icon(Icons.business, size: 16, color: Colors.grey),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      umr['insured'],
                      style: const TextStyle(color: Colors.grey),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Row(
                children: [
                  _buildInfoChip(Icons.category, umr['class']),
                  const SizedBox(width: 8),
                  _buildInfoChip(
                    Icons.attach_money,
                    '${umr['currency']} ${_formatNumber(umr['premium'])}',
                  ),
                  const SizedBox(width: 8),
                  _buildInfoChip(Icons.calendar_today, umr['created_at']),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildInfoChip(IconData icon, String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: Colors.grey[100],
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: Colors.grey),
          const SizedBox(width: 4),
          Text(
            text,
            style: const TextStyle(fontSize: 11, color: Colors.grey),
          ),
        ],
      ),
    );
  }

  Widget _buildValidationTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Validation Input Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Validate UMR',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    decoration: const InputDecoration(
                      labelText: 'Enter UMR to Validate',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.qr_code),
                      hintText: 'e.g., B099261234ABC001',
                    ),
                    textCapitalization: TextCapitalization.characters,
                    onSubmitted: (value) => _validateUMR(value),
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: () {},
                      icon: const Icon(Icons.verified),
                      label: const Text('Validate'),
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

          // Validation Rules Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'UMR Validation Rules',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 16),
                  _buildValidationRule(
                    'Format Check',
                    'UMR must follow B099YYNNNNAAASSS format',
                    Icons.text_format,
                  ),
                  _buildValidationRule(
                    'Prefix Validation',
                    'Must start with B099 (Lloyd\'s market prefix)',
                    Icons.label,
                  ),
                  _buildValidationRule(
                    'Year Code',
                    '2-digit year (24-27 currently valid)',
                    Icons.calendar_today,
                  ),
                  _buildValidationRule(
                    'Syndicate Number',
                    '4-digit valid Lloyd\'s syndicate number',
                    Icons.business,
                  ),
                  _buildValidationRule(
                    'Broker Code',
                    '3-character registered broker code',
                    Icons.badge,
                  ),
                  _buildValidationRule(
                    'Sequence Number',
                    '3-digit unique sequence for syndicate/broker',
                    Icons.numbers,
                  ),
                  _buildValidationRule(
                    'Uniqueness Check',
                    'UMR must be unique in Lloyd\'s database',
                    Icons.fingerprint,
                  ),
                  _buildValidationRule(
                    'Checksum Validation',
                    'Internal checksum verification',
                    Icons.verified_user,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Bulk Validation Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Bulk Validation',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Upload a CSV file with multiple UMRs to validate',
                    style: TextStyle(color: Colors.grey),
                  ),
                  const SizedBox(height: 16),
                  OutlinedButton.icon(
                    onPressed: _uploadBulkFile,
                    icon: const Icon(Icons.upload_file),
                    label: const Text('Upload CSV File'),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 24),
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

  Widget _buildValidationRule(String title, String description, IconData icon) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: const Color(0xFF1a237e).withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: const Color(0xFF1a237e), size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                Text(
                  description,
                  style: const TextStyle(color: Colors.grey, fontSize: 13),
                ),
              ],
            ),
          ),
        ],
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
      case 'marketing':
        return Colors.purple;
      case 'declined':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  String _formatNumber(dynamic number) {
    if (number == null) return '0';
    final n = number is int ? number.toDouble() : number as double;
    if (n >= 1000000) {
      return '${(n / 1000000).toStringAsFixed(2)}M';
    } else if (n >= 1000) {
      return '${(n / 1000).toStringAsFixed(0)}K';
    }
    return n.toStringAsFixed(0);
  }

  void _showUMRDetails(Map<String, dynamic> umr) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        maxChildSize: 0.9,
        minChildSize: 0.4,
        expand: false,
        builder: (context, scrollController) => Container(
          padding: const EdgeInsets.all(20),
          child: ListView(
            controller: scrollController,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: Colors.grey[300],
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    umr['umr'],
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      fontFamily: 'monospace',
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.copy),
                    onPressed: () {
                      Clipboard.setData(ClipboardData(text: umr['umr']));
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('UMR copied to clipboard')),
                      );
                    },
                  ),
                ],
              ),
              const Divider(),
              _buildDetailRow('Status', umr['status'].toUpperCase()),
              _buildDetailRow('Insured', umr['insured']),
              _buildDetailRow('Class of Business', umr['class']),
              _buildDetailRow('Syndicate', umr['syndicate']),
              _buildDetailRow('Broker Code', umr['broker']),
              _buildDetailRow('Premium', '${umr['currency']} ${umr['premium']}'),
              _buildDetailRow('Created', umr['created_at']),
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: () {
                        Navigator.pop(context);
                        // Navigate to placement details
                      },
                      icon: const Icon(Icons.visibility),
                      label: const Text('View Placement'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () {
                        Navigator.pop(context);
                        // Navigate to edit
                      },
                      icon: const Icon(Icons.edit),
                      label: const Text('Edit'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  void _validateUMR(String umr) {
    // Implement UMR validation logic
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Validating UMR: $umr')),
    );
  }

  void _uploadBulkFile() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Bulk upload feature coming soon')),
    );
  }
}

// Helper widget for UMR format display
class _FormatPart extends StatelessWidget {
  final String label;
  final String value;

  const _FormatPart({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            fontFamily: 'monospace',
          ),
        ),
        Text(
          label,
          style: const TextStyle(fontSize: 10, color: Colors.grey),
        ),
      ],
    );
  }
}
