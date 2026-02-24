import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

class SharedWithMeScreen extends StatefulWidget {
  const SharedWithMeScreen({super.key});

  @override
  State<SharedWithMeScreen> createState() => _SharedWithMeScreenState();
}

class _SharedWithMeScreenState extends State<SharedWithMeScreen> {
  List<Map<String, dynamic>> _shares = [];
  bool _isLoading = true;
  String? _errorMessage;

  Future<void> _fetchShares() async {
    try {
      final response = await authService.get('/api/v1/shares/received');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as List? ?? [];
        if (mounted) {
          setState(() {
            _shares = data.map((e) => Map<String, dynamic>.from(e as Map)).toList();
            _isLoading = false;
          });
        }
      } else {
        setState(() {
          _errorMessage = 'Failed to load shared submissions';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Error loading shared submissions: $e';
        _isLoading = false;
      });
    }
  }

  @override
  void initState() {
    super.initState();
    _fetchShares();
  }

  String _monthName(int month) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return months[month - 1];
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceOf(context),
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_rounded, color: AppTheme.text1(context)),
          onPressed: () => context.pop(),
        ),
        title: Text(
          'Shared With Me',
          style: TextStyle(
            color: AppTheme.text1(context),
            fontSize: 18,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      body: _isLoading
          ? Center(
              child: CircularProgressIndicator(
                color: AppTheme.primaryDark,
              ),
            )
          : _errorMessage != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.error_outline_rounded, size: 48, color: AppTheme.danger),
                        const SizedBox(height: 16),
                        Text(
                          _errorMessage!,
                          style: TextStyle(color: AppTheme.text1(context), textAlign: TextAlign.center),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _fetchShares,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppTheme.primaryDark,
                            foregroundColor: Colors.white,
                          ),
                          child: Text(l10n?.retry ?? 'Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : _shares.isEmpty
                  ? Center(
                      child: Padding(
                        padding: const EdgeInsets.all(40),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.share_outlined, size: 64, color: AppTheme.textH(context)),
                            const SizedBox(height: 16),
                            Text(
                              'No shared submissions',
                              style: TextStyle(
                                color: AppTheme.text1(context),
                                fontSize: 18,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Submissions shared with you will appear here.\nAsk a colleague to share a submission with you.',
                              style: TextStyle(
                                color: AppTheme.text2(context),
                                fontSize: 14,
                                textAlign: TextAlign.center,
                              ),
                            ),
                          ],
                        ),
                      ),
                    )
                  : ListView(
                      padding: const EdgeInsets.all(16),
                      children: _shares.map((item) => _buildShareCard(item)).toList(),
                    ),
    );
  }

  Widget _buildShareCard(Map<String, dynamic> item) {
    final share = item['share'] as Map<String, dynamic>;
    final assessment = item['assessment'] as Map<String, dynamic>;
    final createdAt = DateTime.tryParse(share['created_at'] ?? '') ?? DateTime.now();
    final shareType = share['share_type'] ?? 'analysis';
    final shareIcon = shareType == 'analysis' ? Icons.analytics_outlined : Icons.description_outlined;
    final shareColor = shareType == 'analysis' ? AppTheme.primaryDark : AppTheme.success;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => context.go('/reports/results/${assessment['id']}'),
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: shareColor.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(shareIcon, color: shareColor, size: 22),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            assessment['insured_name'] ?? 'Unknown',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.text1(context),
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          Text(
                            assessment['reference_number'] ?? 'Assessment #${assessment['id']}',
                            style: TextStyle(
                              fontSize: 12,
                              color: AppTheme.text2(context),
                            ),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: shareColor.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        shareType.toUpperCase(),
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: shareColor,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Divider(color: AppTheme.borderOf(context).withOpacity(0.5)),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Icon(Icons.person_outline_rounded, size: 14, color: AppTheme.textH(context)),
                    const SizedBox(width: 4),
                    Text(
                      'Shared by ${share['shared_by_name'] ?? 'Unknown'}',
                      style: TextStyle(
                        fontSize: 13,
                        color: AppTheme.text2(context),
                      ),
                    ),
                    const Spacer(),
                    Icon(Icons.calendar_today_rounded, size: 12, color: AppTheme.textH(context)),
                    const SizedBox(width: 4),
                    Text(
                      '${createdAt.day} ${_monthName(createdAt.month)} ${createdAt.year}',
                      style: TextStyle(
                        fontSize: 12,
                        color: AppTheme.textH(context),
                      ),
                    ),
                  ],
                ),
                if (share['message'] != null && (share['message'] as String).isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.surfaceVariantOf(context),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(Icons.message_outlined, size: 16, color: AppTheme.textH(context)),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            share['message'] as String,
                            style: TextStyle(
                              fontSize: 13,
                              color: AppTheme.text1(context),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}