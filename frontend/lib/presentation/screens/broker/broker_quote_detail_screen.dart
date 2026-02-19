import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../../../core/services/auth_service.dart';

class BrokerQuoteDetailScreen extends StatelessWidget {
  final String quoteId;
  const BrokerQuoteDetailScreen({super.key, required this.quoteId});

  Future<dynamic> _fetchQuote() async {
    final response = await http.get(
      Uri.parse('${AuthService().baseUrl}/broker-portal/quotes/$quoteId'),
      headers: {'Authorization': 'Bearer ${AuthService().token}', 'Content-Type': 'application/json'},
    );
    return response.statusCode == 200 ? jsonDecode(response.body) : null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Quote Details')),
      body: FutureBuilder(future: _fetchQuote(), builder: (ctx, snapshot) {
        if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
        final quote = snapshot.data!;
        return ListView(padding: const EdgeInsets.all(16), children: [
          _buildQuoteCard(quote),
          const SizedBox(height: 20),
          if (quote['status'] == 'quoted') ...[
            ElevatedButton(
              onPressed: () => _acceptQuote(context),
              style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
              child: const Text('Accept Quote'),
            ),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: () => _declineQuote(context),
              style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
              child: const Text('Decline'),
            ),
          ],
        ]);
      }),
    );
  }

  Widget _buildQuoteCard(dynamic quote) {
    return Card(
      child: Padding(padding: const EdgeInsets.all(16), child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Quote Summary', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const Divider(),
          _buildRow('Premium', '£${quote['premium']}'),
          _buildRow('Deductible', '£${quote['deductible']}'),
          _buildRow('Coverage', quote['coverage']),
          _buildRow('Expires', quote['expires_at']),
          _buildRow('Status', quote['status'].toUpperCase()),
        ],
      )),
    );
  }

  Widget _buildRow(String label, String value) {
    return Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [Text(label, style: const TextStyle(color: Colors.grey)), Text(value, style: const TextStyle(fontWeight: FontWeight.bold))],
    ));
  }

  void _acceptQuote(BuildContext context) async {
    await http.post(Uri.parse('${AuthService().baseUrl}/broker-portal/quotes/$quoteId/accept'), headers: {'Authorization': 'Bearer ${AuthService().token}', 'Content-Type': 'application/json'});
    if (mounted) context.pop(true);
  }

  void _declineQuote(BuildContext context) async {
    await http.post(Uri.parse('${AuthService().baseUrl}/broker-portal/quotes/$quoteId/decline'), headers: {'Authorization': 'Bearer ${AuthService().token}', 'Content-Type': 'application/json'}, body: jsonEncode({'reason': 'Too expensive'}));
    if (mounted) context.pop(true);
  }
}