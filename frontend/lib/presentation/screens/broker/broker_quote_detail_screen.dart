import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../../../core/services/auth_service.dart';

class BrokerQuoteDetailScreen extends StatefulWidget {
  final String quoteId;
  const BrokerQuoteDetailScreen({super.key, required this.quoteId});

  @override
  State<BrokerQuoteDetailScreen> createState() => _BrokerQuoteDetailScreenState();
}

class _BrokerQuoteDetailScreenState extends State<BrokerQuoteDetailScreen> {
  Map<String, dynamic>? _quote;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _fetchQuote();
  }

  Future<void> _fetchQuote() async {
    try {
      final response = await http.get(
        Uri.parse('${AuthService().baseUrl}/broker-portal/quotes/${widget.quoteId}'),
        headers: {
          'Authorization': 'Bearer ${AuthService().token}',
          'Content-Type': 'application/json',
        },
      );
      if (response.statusCode == 200) {
        setState(() {
          _quote = jsonDecode(response.body) as Map<String, dynamic>;
          _isLoading = false;
        });
      } else {
        setState(() => _isLoading = false);
      }
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Quote Details')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _quote == null
              ? const Center(child: Text('Quote not found'))
              : ListView(padding: const EdgeInsets.all(16), children: [
                  _buildQuoteCard(_quote!),
                  const SizedBox(height: 20),
                  if (_quote!['status'] == 'quoted') ...[
                    ElevatedButton(
                      onPressed: () => _acceptQuote(),
                      style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
                      child: const Text('Accept Quote', style: TextStyle(color: Colors.white)),
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton(
                      onPressed: () => _declineQuote(),
                      style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
                      child: const Text('Decline'),
                    ),
                  ],
                ]),
    );
  }

  Widget _buildQuoteCard(Map<String, dynamic> quote) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Quote Summary', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const Divider(),
            _buildRow('Premium', '\u00A3${quote['premium'] ?? 'N/A'}'),
            _buildRow('Deductible', '\u00A3${quote['deductible'] ?? 'N/A'}'),
            _buildRow('Coverage', '${quote['coverage'] ?? 'N/A'}'),
            _buildRow('Expires', '${quote['expires_at'] ?? 'N/A'}'),
            _buildRow('Status', '${quote['status'] ?? 'unknown'}'.toUpperCase()),
          ],
        ),
      ),
    );
  }

  Widget _buildRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  Future<void> _acceptQuote() async {
    await http.post(
      Uri.parse('${AuthService().baseUrl}/broker-portal/quotes/${widget.quoteId}/accept'),
      headers: {
        'Authorization': 'Bearer ${AuthService().token}',
        'Content-Type': 'application/json',
      },
    );
    if (mounted) context.pop(true);
  }

  Future<void> _declineQuote() async {
    await http.post(
      Uri.parse('${AuthService().baseUrl}/broker-portal/quotes/${widget.quoteId}/decline'),
      headers: {
        'Authorization': 'Bearer ${AuthService().token}',
        'Content-Type': 'application/json',
      },
      body: jsonEncode({'reason': 'Too expensive'}),
    );
    if (mounted) context.pop(true);
  }
}
