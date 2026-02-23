import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../../../core/services/auth_service.dart';

class BrokerSubmissionsListScreen extends StatefulWidget {
  const BrokerSubmissionsListScreen({super.key});

  @override
  State<BrokerSubmissionsListScreen> createState() => _BrokerSubmissionsListScreenState();
}

class _BrokerSubmissionsListScreenState extends State<BrokerSubmissionsListScreen> {
  List<dynamic> _submissions = [];
  bool _isLoading = true;
  String _statusFilter = 'all';

  @override
  void initState() {
    super.initState();
    _loadSubmissions();
  }

  Future<void> _loadSubmissions() async {
    setState(() => _isLoading = true);
    try {
      final url = _statusFilter == 'all' 
          ? '${AuthService().baseUrl}/broker-portal/submissions'
          : '${AuthService().baseUrl}/broker-portal/submissions?status_filter=$_statusFilter';
      
      final response = await http.get(
        Uri.parse(url),
        headers: {'Authorization': 'Bearer ${AuthService().token}', 'Content-Type': 'application/json'},
      );
      
      if (response.statusCode == 200) {
        setState(() {
          _submissions = jsonDecode(response.body);
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  Color _getStatusColor(String status) {
    switch (status) {
      case 'bound': return Colors.green;
      case 'quoted': return Colors.blue;
      case 'submitted': return Colors.orange;
      case 'declined': return Colors.red;
      default: return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Submissions'),
        backgroundColor: const Color(0xFF1E3A5F),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () => context.go('/broker/submissions/create'),
            tooltip: 'New Submission',
          ),
        ],
      ),
      body: Column(
        children: [
          _buildFilterChips(),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _submissions.isEmpty
                    ? _buildEmptyState()
                    : ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _submissions.length,
                        itemBuilder: (ctx, index) => _buildSubmissionCard(_submissions[index]),
                      ),
          ),
        ],
      ),
      bottomNavigationBar: _buildBottomNav(context),
    );
  }

  Widget _buildFilterChips() {
    final filters = ['all', 'submitted', 'under_review', 'quoted', 'bound', 'declined'];
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: filters.map((f) {
            final isSelected = _statusFilter == f;
            return Padding(
              padding: const EdgeInsets.only(right: 8),
              child: FilterChip(
                label: Text(f.replaceAll('_', ' ').toUpperCase()),
                selected: isSelected,
                onSelected: (selected) {
                  setState(() => _statusFilter = f);
                  _loadSubmissions();
                },
                selectedColor: const Color(0xFF1E3A5F),
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  Widget _buildSubmissionCard(dynamic submission) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        contentPadding: const EdgeInsets.all(16),
        leading: CircleAvatar(
          backgroundColor: _getStatusColor(submission['status']).withOpacity(0.2),
          child: Icon(Icons.folder, color: _getStatusColor(submission['status'])),
        ),
        title: Text(
          submission['insured_name'],
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Text('${submission['risk_category'].toUpperCase()} | £${(submission['sum_insured']/1000000).toStringAsFixed(1)}M'),
            const SizedBox(height: 4),
            Text('Ref: ${submission['reference']}', style: TextStyle(color: Colors.grey[600], fontSize: 12)),
          ],
        ),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: _getStatusColor(submission['status']).withOpacity(0.2),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Text(
            submission['status'].toUpperCase(),
            style: TextStyle(color: _getStatusColor(submission['status']), fontWeight: FontWeight.bold, fontSize: 12),
          ),
        ),
        onTap: () => context.go('/broker/submissions/${submission['submission_id']}'),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: const [
          Icon(Icons.folder_off, size: 64, color: Colors.grey),
          SizedBox(height: 16),
          Text('No submissions found', style: TextStyle(fontSize: 18, color: Colors.grey)),
          SizedBox(height: 8),
          Text('Create your first submission to get started'),
        ],
      ),
    );
  }

  Widget _buildBottomNav(BuildContext context) {
    return NavigationBar(
      selectedIndex: 1,
      onDestinationSelected: (index) {
        if (index == 0) context.go('/broker/dashboard');
      },
      destinations: const [
        NavigationDestination(icon: Icon(Icons.dashboard), label: 'Dashboard'),
        NavigationDestination(icon: Icon(Icons.folder), label: 'Submissions'),
      ],
    );
  }
}