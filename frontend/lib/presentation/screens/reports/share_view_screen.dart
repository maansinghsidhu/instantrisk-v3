import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';

/// Public screen for viewing shared assessments (no auth required)
class ShareViewScreen extends StatefulWidget {
  final String token;
  const ShareViewScreen({super.key, required this.token});

  @override
  State<ShareViewScreen> createState() => _ShareViewScreenState();
}

class _ShareViewScreenState extends State<ShareViewScreen> {
  Map<String, dynamic>? _data;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadSharedAssessment();
  }

  Future<void> _loadSharedAssessment() async {
    try {
      final baseUrl = authService.baseUrl;
      final response = await http.get(Uri.parse('$baseUrl/share/${widget.token}'));
      if (response.statusCode == 200) {
        setState(() {
          _data = jsonDecode(response.body);
          _isLoading = false;
        });
      } else if (response.statusCode == 410) {
        setState(() {
          _error = 'This share link has expired';
          _isLoading = false;
        });
      } else {
        setState(() {
          _error = 'Share link not found';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to load shared assessment';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: AppTheme.darkBg,
        elevation: 0,
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Image.asset('assets/images/logo-icon.png', height: 28),
            const SizedBox(width: 10),
            const Text('Shared Assessment',
                style: TextStyle(color: Colors.white, fontSize: 16, fontFamily: 'Inter')),
          ],
        ),
        centerTitle: true,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError()
              : _buildContent(),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.link_off, size: 64, color: Colors.grey[600]),
            const SizedBox(height: 16),
            Text(_error!, style: const TextStyle(color: Colors.white, fontSize: 18)),
            const SizedBox(height: 8),
            Text('The link may have expired or been revoked.',
                style: TextStyle(color: Colors.grey[500], fontSize: 14)),
          ],
        ),
      ),
    );
  }

  Widget _buildContent() {
    final d = _data!;
    final decision = d['decision']?.toString().toUpperCase() ?? 'PENDING';
    final isGo = decision == 'GO';
    final isNoGo = decision == 'NO_GO' || decision == 'NO-GO';
    final decisionColor = isGo ? AppTheme.success : isNoGo ? AppTheme.danger : AppTheme.warning;
    final decisionLabel = isGo ? 'GO' : isNoGo ? 'NO-GO' : decision;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Shared by badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.white10,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text('Shared by ${d['shared_by'] ?? 'Unknown'} · Expires ${_formatExpiry(d['expires_at'])}',
                style: const TextStyle(color: Colors.white60, fontSize: 12)),
          ),
          const SizedBox(height: 20),

          // Decision banner
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [decisionColor.withValues(alpha: 0.2), decisionColor.withValues(alpha: 0.05)],
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: decisionColor.withValues(alpha: 0.3)),
            ),
            child: Column(
              children: [
                Text(decisionLabel,
                    style: TextStyle(fontSize: 32, fontWeight: FontWeight.w800, color: decisionColor, fontFamily: 'Inter')),
                if (d['risk_score'] != null)
                  Text('Risk Score: ${d['risk_score']}',
                      style: const TextStyle(color: Colors.white70, fontSize: 14)),
                if (d['confidence_score'] != null)
                  Text('Confidence: ${d['confidence_score']}%',
                      style: const TextStyle(color: Colors.white54, fontSize: 13)),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // Details
          _buildField('Insured', d['insured_name']),
          _buildField('Risk Category', d['risk_category']),
          _buildField('Assessment Date', _formatDate(d['created_at'])),
          if (d['premium_price'] != null) _buildField('Premium', '\$${d['premium_price']}'),
          if (d['underwriting_percentage'] != null) _buildField('Underwriting %', '${d['underwriting_percentage']}%'),
          const SizedBox(height: 20),

          // Rationale
          if (d['decision_rationale'] != null) ...[
            const Text('Decision Rationale',
                style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.surfaceOf(context),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.borderOf(context)),
              ),
              child: Text(d['decision_rationale'], style: const TextStyle(color: Colors.white70, fontSize: 14, height: 1.5)),
            ),
          ],
          const SizedBox(height: 40),

          // Branding footer
          Center(
            child: Column(
              children: [
                Image.asset('assets/images/logo-icon.png', height: 32),
                const SizedBox(height: 8),
                Text('InstantRisk Engine · Underwriting Platform',
                    style: TextStyle(color: Colors.grey[600], fontSize: 12)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildField(String label, dynamic value) {
    if (value == null || value.toString().isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 140,
            child: Text(label, style: const TextStyle(color: Colors.white54, fontSize: 13)),
          ),
          Expanded(
            child: Text(value.toString(), style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w500)),
          ),
        ],
      ),
    );
  }

  String _formatExpiry(String? dateStr) {
    if (dateStr == null) return '';
    try {
      final dt = DateTime.parse(dateStr);
      final diff = dt.difference(DateTime.now());
      if (diff.inHours > 0) return 'in ${diff.inHours}h';
      if (diff.inMinutes > 0) return 'in ${diff.inMinutes}m';
      return 'expired';
    } catch (_) {
      return '';
    }
  }

  String _formatDate(String? dateStr) {
    if (dateStr == null) return '';
    try {
      final dt = DateTime.parse(dateStr);
      return '${dt.day}/${dt.month}/${dt.year}';
    } catch (_) {
      return dateStr;
    }
  }
}
