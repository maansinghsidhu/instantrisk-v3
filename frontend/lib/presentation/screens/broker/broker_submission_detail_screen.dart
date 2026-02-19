import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class BrokerSubmissionDetailScreen extends StatelessWidget {
  final String submissionId;
  const BrokerSubmissionDetailScreen({super.key, required this.submissionId});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Submission Details')),
      body: ListView(padding: const EdgeInsets.all(16), children: const [
        ListTile(title: Text('Status'), subtitle: Text('Submitted')),
        ListTile(title: Text('Risk Category'), subtitle: Text('Cyber')),
        ListTile(title: Text('Sum Insured'), subtitle: Text('£5,000,000')),
        Divider(),
        ListTile(title: Text('Underwriter'), subtitle: Text('Pending Assignment')),
        SizedBox(height: 20),
        ElevatedButton.icon(
          onPressed: null,
          icon: Icon(Icons.message),
          label: Text('Message Underwriter'),
        ),
      ]),
    );
  }
}