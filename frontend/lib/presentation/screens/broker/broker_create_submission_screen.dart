import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../../../core/services/auth_service.dart';

class BrokerCreateSubmissionScreen extends StatefulWidget {
  const BrokerCreateSubmissionScreen({super.key});

  @override
  State<BrokerCreateSubmissionScreen> createState() =>
      _BrokerCreateSubmissionScreenState();
}

class _BrokerCreateSubmissionScreenState
    extends State<BrokerCreateSubmissionScreen> {
  final _formKey = GlobalKey<FormState>();
  final _insuredNameController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _sumInsuredController = TextEditingController();
  final _notesController = TextEditingController();

  String _riskCategory = 'cyber';
  String _territory = 'UK';
  String _priority = 'normal';
  String _inceptionDate = '';
  String _expiryDate = '';

  bool _isLoading = false;

  final List<String> _riskCategories = [
    'cyber',
    'property',
    'marine',
    'liability',
    'financial_lines',
    'specialty'
  ];

  final List<String> _territories = [
    'UK',
    'Europe',
    'Worldwide',
    'North America',
    'Asia Pacific',
    'ROW'
  ];

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    try {
      final response = await http.post(
        Uri.parse('${AuthService().baseUrl}/broker-portal/submissions'),
        headers: {
          'Authorization': 'Bearer ${AuthService().token}',
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'insured_name': _insuredNameController.text,
          'risk_category': _riskCategory,
          'description': _descriptionController.text,
          'sum_insured': double.parse(_sumInsuredController.text),
          'territory': _territory,
          'inception_date': _inceptionDate,
          'expiry_date': _expiryDate,
          'priority': _priority,
          'notes': _notesController.text,
        }),
      );

      if (response.statusCode == 201) {
        _showSuccessDialog();
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${jsonDecode(response.body)['detail']}')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: ${e.toString()}')),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }

  void _showSuccessDialog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Submission Created'),
        content: const Text(
            'Your submission has been received. An underwriter will review it shortly.'),
        actions: [
          TextButton(
            onPressed: () {
              ctx.pop();
              ctx.pop();
              context.go('/broker/dashboard');
            },
            child: const Text('Go to Dashboard'),
          ),
          TextButton(
            onPressed: () => ctx.pop(),
            child: const Text('Create Another'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('New Submission'),
        backgroundColor: const Color(0xFF1E3A5F),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Insured Details',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _insuredNameController,
                decoration: _buildInputDecoration('Insured Name *', Icons.business),
                validator: (v) => v == null || v.isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField(
                value: _riskCategory,
                decoration: _buildInputDecoration('Risk Category *', Icons.category),
                items: _riskCategories
                    .map((e) => DropdownMenuItem(value: e, child: Text(e.toUpperCase())))
                    .toList(),
                onChanged: (v) => setState(() => _riskCategory = v!),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _descriptionController,
                maxLines: 3,
                decoration: _buildInputDecoration('Business Description *', Icons.description),
                validator: (v) => v == null || v.isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: 24),
              const Text(
                'Coverage Details',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _sumInsuredController,
                keyboardType: TextInputType.number,
                decoration: _buildInputDecoration('Sum Insured (GBP) *', Icons.attach_money),
                validator: (v) =>
                    v == null || v.isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField(
                value: _territory,
                decoration: _buildInputDecoration('Territory *', Icons.public),
                items: _territories
                    .map((e) => DropdownMenuItem(value: e, child: Text(e)))
                    .toList(),
                onChanged: (v) => setState(() => _territory = v!),
              ),
              const SizedBox(height: 24),
              const Text(
                'Policy Period',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      decoration: _buildInputDecoration('Inception (YYYY-MM-DD) *', Icons.calendar_today),
                      onChanged: (v) => _inceptionDate = v,
                      validator: (v) => v == null || v.isEmpty ? 'Required' : null,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: TextFormField(
                      decoration: _buildInputDecoration('Expiry (YYYY-MM-DD) *', Icons.calendar_today),
                      onChanged: (v) => _expiryDate = v,
                      validator: (v) => v == null || v.isEmpty ? 'Required' : null,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              DropdownButtonFormField(
                value: _priority,
                decoration: _buildInputDecoration('Priority', Icons.priority_high),
                items: ['urgent', 'normal', 'low']
                    .map((e) => DropdownMenuItem(value: e, child: Text(e.toUpperCase())))
                    .toList(),
                onChanged: (v) => setState(() => _priority = v!),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _notesController,
                maxLines: 2,
                decoration: _buildInputDecoration('Additional Notes', Icons.notes),
              ),
              const SizedBox(height: 32),
              SizedBox(
                width: double.infinity,
                height: 50,
                child: ElevatedButton(
                  onPressed: _isLoading ? null : _submit,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF4CAF50),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                  child: _isLoading
                      ? const CircularProgressIndicator(color: Colors.white)
                      : const Text(
                          'Submit for Underwriting',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  InputDecoration _buildInputDecoration(String label, IconData icon) {
    return InputDecoration(
      labelText: label,
      prefixIcon: Icon(icon, color: const Color(0xFF1E3A5F)),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
    );
  }
}