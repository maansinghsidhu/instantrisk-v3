import 'package:flutter/material.dart';
import 'dart:convert';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// V3 Placement Board - Subscription Market Workflow
class PlacementBoardScreen extends StatefulWidget {
  const PlacementBoardScreen({super.key});

  @override
  State<PlacementBoardScreen> createState() => _PlacementBoardScreenState();
}

class _PlacementBoardScreenState extends State<PlacementBoardScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool _isLoading = true;
  List<dynamic> _placements = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _loadPlacements();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadPlacements() async {
    try {
      final response = await AuthService().get('/placements/');

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() {
          _placements = data['placements'] ?? data ?? [];
          _isLoading = false;
        });
      } else {
        setState(() {
          _error = 'Failed to load placements (${response.statusCode})';
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

  List<dynamic> _filterByStatus(String status) {
    if (status == 'all') return _placements;
    return _placements.where((p) => p['status'] == status).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Placement Board'),
        backgroundColor: const Color(0xFF1a237e),
        foregroundColor: Colors.white,
        bottom: TabBar(
          controller: _tabController,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          indicatorColor: Colors.white,
          tabs: const [
            Tab(text: 'All'),
            Tab(text: 'Marketing'),
            Tab(text: 'Placing'),
            Tab(text: 'Bound'),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () => _showCreatePlacementDialog(),
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!, style: const TextStyle(color: Colors.red)))
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildPlacementList(_filterByStatus('all')),
                    _buildPlacementList(_filterByStatus('marketing')),
                    _buildPlacementList(_filterByStatus('placing')),
                    _buildPlacementList(_filterByStatus('bound')),
                  ],
                ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showCreatePlacementDialog(),
        backgroundColor: const Color(0xFF1a237e),
        child: const Icon(Icons.add, color: Colors.white),
      ),
    );
  }

  Widget _buildPlacementList(List<dynamic> placements) {
    if (placements.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.inbox, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text('No placements found', style: TextStyle(color: Colors.grey)),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadPlacements,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: placements.length,
        itemBuilder: (context, index) {
          final placement = placements[index] as Map<String, dynamic>;
          return _buildPlacementCard(placement);
        },
      ),
    );
  }

  Widget _buildPlacementCard(Map<String, dynamic> placement) {
    final totalLine = double.tryParse(placement['total_line']?.toString() ?? '0') ?? 0.0;
    final targetLine = double.tryParse(placement['target_line']?.toString() ?? '100') ?? 100.0;
    final progress = targetLine > 0 ? (totalLine / targetLine).clamp(0.0, 1.0) : 0.0;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: () => _showPlacementDetails(placement),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    placement['umr'] ?? 'Unknown UMR',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  ),
                  Chip(
                    label: Text(
                      placement['status'] ?? 'pending',
                      style: const TextStyle(color: Colors.white, fontSize: 12),
                    ),
                    backgroundColor: _getStatusColor(placement['status']),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  const Icon(Icons.business, size: 16, color: Colors.grey),
                  const SizedBox(width: 4),
                  Text(
                    'Lead: Syndicate ${placement['lead_syndicate_id'] ?? 'TBD'}',
                    style: const TextStyle(color: Colors.grey),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Row(
                children: [
                  const Icon(Icons.attach_money, size: 16, color: Colors.grey),
                  const SizedBox(width: 4),
                  Text(
                    '${placement['currency'] ?? 'GBP'} ${placement['gross_premium'] ?? 0}',
                    style: const TextStyle(color: Colors.grey),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text('Placement Progress'),
                      Text('${totalLine.toStringAsFixed(0)}% / ${targetLine.toStringAsFixed(0)}%'),
                    ],
                  ),
                  const SizedBox(height: 4),
                  LinearProgressIndicator(
                    value: progress,
                    backgroundColor: Colors.grey[200],
                    valueColor: AlwaysStoppedAnimation<Color>(
                      progress >= 1.0 ? Colors.green : Colors.blue,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton.icon(
                    onPressed: () => _showAddLineDialog(placement),
                    icon: const Icon(Icons.add, size: 18),
                    label: const Text('Add Line'),
                  ),
                  TextButton.icon(
                    onPressed: () => _showPlacementDetails(placement),
                    icon: const Icon(Icons.visibility, size: 18),
                    label: const Text('View'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Color _getStatusColor(String? status) {
    switch (status?.toLowerCase()) {
      case 'bound':
        return Colors.green;
      case 'placing':
        return Colors.blue;
      case 'quoting':
        return Colors.orange;
      case 'declined':
        return Colors.red;
      case 'marketing':
        return Colors.purple;
      default:
        return Colors.grey;
    }
  }

  void _showCreatePlacementDialog() {
    final umrController = TextEditingController();
    final premiumController = TextEditingController();
    final syndicateController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Create New Placement'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: umrController,
                decoration: const InputDecoration(
                  labelText: 'UMR',
                  hintText: 'e.g., B099926ABC001',
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: syndicateController,
                decoration: const InputDecoration(
                  labelText: 'Lead Syndicate Number',
                  hintText: 'e.g., 1234',
                ),
                keyboardType: TextInputType.number,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: premiumController,
                decoration: const InputDecoration(
                  labelText: 'Gross Premium (GBP)',
                  hintText: 'e.g., 125000',
                ),
                keyboardType: TextInputType.number,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(context);
              await _createPlacement(
                umrController.text,
                syndicateController.text,
                premiumController.text,
              );
            },
            child: const Text('Create'),
          ),
        ],
      ),
    );
  }

  Future<void> _createPlacement(String umr, String syndicate, String premium) async {
    try {
      final response = await AuthService().post('/placements/', body: {
        'umr': umr,
        'lead_syndicate': int.tryParse(syndicate) ?? 1234,
        'gross_premium': premium,
        'currency': 'GBP',
        'inception_date': DateTime.now().toIso8601String(),
        'expiry_date': DateTime.now().add(const Duration(days: 365)).toIso8601String(),
      });

      if (!mounted) return;

      if (response.statusCode == 200 || response.statusCode == 201) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Placement created successfully')),
        );
        _loadPlacements();
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${response.body}')),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }

  void _showAddLineDialog(Map<String, dynamic> placement) {
    final syndicateController = TextEditingController();
    final lineController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Add Line to ${placement['umr']}'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: syndicateController,
              decoration: const InputDecoration(
                labelText: 'Syndicate Number',
                hintText: 'e.g., 5678',
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: lineController,
              decoration: const InputDecoration(
                labelText: 'Line Percentage',
                hintText: 'e.g., 15.0',
              ),
              keyboardType: TextInputType.number,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(context);
              await _addLine(
                placement['umr'],
                syndicateController.text,
                lineController.text,
              );
            },
            child: const Text('Add Line'),
          ),
        ],
      ),
    );
  }

  Future<void> _addLine(String umr, String syndicate, String line) async {
    try {
      final response = await AuthService().post('/placements/$umr/lines', body: {
        'syndicate_number': syndicate,
        'written_line': double.tryParse(line) ?? 10.0,
      });

      if (!mounted) return;

      if (response.statusCode == 200 || response.statusCode == 201) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Line added successfully')),
        );
        _loadPlacements();
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${response.body}')),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }

  void _showPlacementDetails(Map<String, dynamic> placement) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        maxChildSize: 0.9,
        minChildSize: 0.5,
        expand: false,
        builder: (context, scrollController) => Container(
          padding: const EdgeInsets.all(16),
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
              Text(
                placement['umr'] ?? 'Unknown UMR',
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              _buildDetailRow('Status', placement['status'] ?? 'N/A'),
              _buildDetailRow('Lead Syndicate', '${placement['lead_syndicate_id']}'),
              _buildDetailRow('Gross Premium', '${placement['currency']} ${placement['gross_premium']}'),
              _buildDetailRow('Total Line', '${placement['total_line']}%'),
              _buildDetailRow('Target Line', '${placement['target_line']}%'),
              const SizedBox(height: 16),
              const Text(
                'Syndicate Lines',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              if (placement['lines'] != null && (placement['lines'] as List).isNotEmpty)
                ...(placement['lines'] as List).map((line) => ListTile(
                      leading: const CircleAvatar(child: Icon(Icons.business)),
                      title: Text('Syndicate ${line['syndicate_number']}'),
                      subtitle: Text('Status: ${line['status']}'),
                      trailing: Text('${line['written_line']}%'),
                    ))
              else
                const Text('No lines added yet'),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
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
}
