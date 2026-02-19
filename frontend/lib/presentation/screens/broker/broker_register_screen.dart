import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../../../core/services/auth_service.dart';

class BrokerRegisterScreen extends StatefulWidget {
  const BrokerRegisterScreen({super.key});

  @override
  State<BrokerRegisterScreen> createState() => _BrokerRegisterScreenState();
}

class _BrokerRegisterScreenState extends State<BrokerRegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  final _fullNameController = TextEditingController();
  final _companyController = TextEditingController();
  final _phoneController = TextEditingController();
  final _licenseController = TextEditingController();

  String _territory = 'UK';
  bool _isLoading = false;
  String? _errorMessage;

  final List<String> _territories = ['UK', 'Europe', 'Worldwide', 'North America', 'Asia Pacific'];

  Future<void> _register() async {
    if (!_formKey.currentState!.validate()) return;
    if (_passwordController.text != _confirmPasswordController.text) {
      setState(() => _errorMessage = 'Passwords do not match');
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final response = await http.post(
        Uri.parse('${AuthService().baseUrl}/broker-portal/register'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': _emailController.text,
          'password': _passwordController.text,
          'full_name': _fullNameController.text,
          'company_name': _companyController.text,
          'phone': _phoneController.text,
          'license_number': _licenseController.text,
          'territory': _territory,
        }),
      );

      if (response.statusCode == 201) {
        _showSuccessDialog();
      } else {
        setState(() => _errorMessage = jsonDecode(response.body)['detail'] ?? 'Registration failed');
      }
    } catch (e) {
      setState(() => _errorMessage = 'Connection error: ${e.toString()}');
    } finally {
      setState(() => _isLoading = false);
    }
  }

  void _showSuccessDialog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Registration Submitted'),
        content: const Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.check_circle, color: Colors.green, size: 60),
            SizedBox(height: 16),
            Text('Your application is under review.'),
            SizedBox(height: 8),
            Text('You will receive an email once approved.', style: TextStyle(color: Colors.grey)),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              ctx.pop();
              context.go('/broker/login');
            },
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Register as Broker')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Account Details', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              _buildTextField('Email', _emailController, Icons.email),
              const SizedBox(height: 16),
              _buildTextField('Password', _passwordController, Icons.lock, obscure: true),
              const SizedBox(height: 16),
              _buildTextField('Confirm Password', _confirmPasswordController, Icons.lock, obscure: true),
              const SizedBox(height: 24),
              const Text('Company Information', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              _buildTextField('Full Name', _fullNameController, Icons.person),
              const SizedBox(height: 16),
              _buildTextField('Company Name', _companyController, Icons.business),
              const SizedBox(height: 16),
              _buildTextField('Phone', _phoneController, Icons.phone),
              const SizedBox(height: 16),
              _buildTextField('License Number', _licenseController, Icons.badge),
              const SizedBox(height: 16),
              DropdownButtonFormField(
                value: _territory,
                decoration: _buildInputDecoration('Primary Territory', Icons.public),
                items: _territories.map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
                onChanged: (v) => setState(() => _territory = v!),
              ),
              const SizedBox(height: 24),
              if (_errorMessage != null)
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(color: Colors.red.withOpacity(0.1), border: Border.all(color: Colors.red), borderRadius: BorderRadius.circular(8)),
                  child: Text(_errorMessage!, style: const TextStyle(color: Colors.red)),
                ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                height: 50,
                child: ElevatedButton(
                  onPressed: _isLoading ? null : _register,
                  style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF1E3A5F), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8))),
                  child: _isLoading ? const CircularProgressIndicator(color: Colors.white) : const Text('Submit Application', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                ),
              ),
              const SizedBox(height: 16),
              Center(
                child: TextButton(
                  onPressed: () => context.go('/broker/login'),
                  child: const Text('Already registered? Login here'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTextField(String label, TextEditingController controller, IconData icon, {bool obscure = false}) {
    return TextFormField(
      controller: controller,
      obscureText: obscure,
      decoration: _buildInputDecoration(label, icon),
      validator: (v) => v == null || v.isEmpty ? '$label required' : null,
    );
  }

  InputDecoration _buildInputDecoration(String label, IconData icon) {
    return InputDecoration(labelText: label, prefixIcon: Icon(icon), border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)));
  }
}