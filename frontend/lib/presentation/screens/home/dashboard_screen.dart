import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/subscription_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Dashboard Screen - Main home screen with overview and quick actions
class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool _isCreatingSession = false;
  String? _qrToken;
  String? _qrUrl;
  bool _isPolling = false;
  List<Map<String, dynamic>> _uploadedDocs = [];

  // Real stats from API
  int _totalAssessments = 0;
  int _approvedCount = 0;
  int _pendingCount = 0;
  List<Map<String, dynamic>> _recentAssessments = [];
  bool _isLoadingStats = true;

  // Subscription service for tier-based UI
  final SubscriptionService _subscriptionService = SubscriptionService();

  // Tier helpers
  bool get _isPremium => _subscriptionService.isPremium;
  bool get _isBasicOrHigher => _subscriptionService.isBasic || _subscriptionService.isPremium;
  bool get _isTrial => _subscriptionService.isTrial;

  @override
  void initState() {
    super.initState();
    _checkAuthAndLoad();
  }

  Future<void> _checkAuthAndLoad() async {
    if (!authService.isLoggedIn) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          context.go('/login');
        }
      });
      return;
    }
    _fetchStats();
  }

  Future<void> _fetchStats() async {
    try {
      final response = await authService.get('/assessments/?page=1&page_size=50');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final items = data['items'] as List? ?? [];

        int approved = 0;
        int pending = 0;

        for (final item in items) {
          final decision = item['decision']?.toString().toLowerCase() ?? '';
          if (decision == 'go') {
            approved++;
          } else if (decision == 'refer' || decision == 'pending') {
            pending++;
          }
        }

        if (mounted) {
          setState(() {
            _totalAssessments = items.length;
            _approvedCount = approved;
            _pendingCount = pending;
            _recentAssessments = items.take(5).map((e) => Map<String, dynamic>.from(e)).toList();
            _isLoadingStats = false;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoadingStats = false);
      }
    }
  }

  String get _userName {
    final user = authService.user;
    if (user != null && user['full_name'] != null) {
      return user['full_name'];
    }
    return 'User';
  }

  String get _userInitials {
    final name = _userName;
    final parts = name.split(' ');
    if (parts.length >= 2) {
      return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
    }
    return name.isNotEmpty ? name[0].toUpperCase() : 'U';
  }

  String _monthName(int month) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return months[month - 1];
  }

  Future<void> _showQRCodeModal() async {
    setState(() => _isCreatingSession = true);

    try {
      // Create upload session (using demo endpoint for testing)
      final response = await authService.post('/upload-sessions/demo');

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = jsonDecode(response.body);
        setState(() {
          _qrToken = data['token'];
          _qrUrl = data['qr_url'] ?? '/upload/${data['token']}';
        });

        if (mounted) {
          _showQRDialog();
        }
      } else if (response.statusCode == 401) {
        if (mounted) {
          context.go('/login');
        }
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Failed to create upload session')),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    }

    setState(() => _isCreatingSession = false);
  }

  Future<void> _startPolling() async {
    if (_qrToken == null || _isPolling) return;
    _isPolling = true;

    while (_isPolling && mounted) {
      try {
        final response = await authService.get('/upload-sessions/$_qrToken/status');

        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);
          final status = data['status'] as String;
          final documents = data['documents'] as List? ?? [];

          if (status == 'complete' || documents.isNotEmpty) {
            _isPolling = false;
            if (mounted) {
              setState(() {
                _uploadedDocs = List<Map<String, dynamic>>.from(documents);
              });

              // Close QR dialog and show documents
              Navigator.of(context).pop();
              _showUploadedDocsDialog(status == 'complete');
            }
            return;
          }
        } else if (response.statusCode == 401) {
          _isPolling = false;
          return;
        }
      } catch (e) {
        // Continue polling on error
      }

      await Future.delayed(const Duration(seconds: 2));
    }
  }

  void _stopPolling() {
    _isPolling = false;
  }

  void _showUploadedDocsDialog(bool isComplete) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Builder(
          builder: (context) {
            final l10n = AppLocalizations.of(context);
            return Row(
              children: [
                Icon(
                  isComplete ? Icons.check_circle : Icons.cloud_upload,
                  color: AppTheme.success,
                ),
                const SizedBox(width: 12),
                Text(isComplete ? l10n.completed : l10n.processing),
              ],
            );
          },
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${_uploadedDocs.length} document(s) uploaded from mobile:',
              style: TextStyle(color: AppTheme.textSecondary, fontSize: 14),
            ),
            const SizedBox(height: 16),
            Container(
              constraints: const BoxConstraints(maxHeight: 200),
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: _uploadedDocs.length,
                itemBuilder: (context, index) {
                  final doc = _uploadedDocs[index];
                  return Container(
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.success.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppTheme.success.withValues(alpha: 0.3)),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.insert_drive_file, color: AppTheme.success, size: 20),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            doc['filename'] ?? 'Document ${index + 1}',
                            style: const TextStyle(fontSize: 13),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        Icon(Icons.check, color: AppTheme.success, size: 18),
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(AppLocalizations.of(ctx).close),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              // Navigate to processing with the token
              context.go('/home/processing/$_qrToken');
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryDark,
              foregroundColor: Colors.white,
            ),
            child: Text(AppLocalizations.of(ctx).startAnalysis),
          ),
        ],
      ),
    );
  }

  void _showQRDialog() {
    // Start polling when dialog opens
    _startPolling();

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          title: Row(
            children: [
              Icon(Icons.qr_code_scanner, color: AppTheme.primaryDark),
              const SizedBox(width: 12),
              Expanded(child: Text(AppLocalizations.of(context).uploadDocument)),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 220,
                height: 220,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.border, width: 2),
                ),
                child: _qrUrl != null
                    ? QrImageView(
                        data: _qrUrl!,
                        version: QrVersions.auto,
                        size: 200,
                        backgroundColor: Colors.white,
                        errorCorrectionLevel: QrErrorCorrectLevel.M,
                      )
                    : const Center(child: CircularProgressIndicator()),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.info.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: AppTheme.info,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        '${AppLocalizations.of(context).loading}\n${AppLocalizations.of(context).uploadDocument}',
                        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              if (_qrUrl != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryDark.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: SelectableText(
                    _qrUrl!,
                    style: TextStyle(fontSize: 10, color: AppTheme.primaryDark),
                    textAlign: TextAlign.center,
                  ),
                ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () {
                _stopPolling();
                Navigator.pop(ctx);
              },
              child: Text(AppLocalizations.of(context).cancel),
            ),
            ElevatedButton(
              onPressed: () {
                _stopPolling();
                Navigator.pop(ctx);
                context.go('/home/intake');
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryDark,
                foregroundColor: Colors.white,
              ),
              child: Text(AppLocalizations.of(context).uploadDocument),
            ),
          ],
        ),
      ),
    ).then((_) {
      // Stop polling when dialog is closed
      _stopPolling();
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: AppTheme.background,
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            // App Bar
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.all(20.0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          l10n.welcomeBack,
                          style: const TextStyle(
                            fontSize: 14,
                            color: AppTheme.textSecondary,
                            fontFamily: 'Inter',
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _userName,
                          style: const TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.textPrimary,
                            fontFamily: 'Inter',
                          ),
                        ),
                      ],
                    ),
                    Row(
                      children: [
                        IconButton(
                          onPressed: () {
                            // TODO: Implement notifications
                          },
                          icon: Stack(
                            children: [
                              const Icon(
                                Icons.notifications_outlined,
                                color: AppTheme.textPrimary,
                                size: 28,
                              ),
                              Positioned(
                                right: 0,
                                top: 0,
                                child: Container(
                                  width: 10,
                                  height: 10,
                                  decoration: const BoxDecoration(
                                    color: AppTheme.danger,
                                    shape: BoxShape.circle,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 8),
                        CircleAvatar(
                          radius: 22,
                          backgroundColor: AppTheme.primaryDark,
                          child: Text(
                            _userInitials,
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),

            // Quick Stats Cards - 3 cards for better overview (Basic+ only)
            if (_isBasicOrHigher)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20.0),
                  child: Row(
                    children: [
                      Expanded(
                        child: _buildStatCard(
                          title: l10n.reports,
                          value: _isLoadingStats ? '-' : '$_totalAssessments',
                          subtitle: l10n.reports,
                          icon: Icons.assessment_outlined,
                          color: AppTheme.primaryDark,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildStatCard(
                          title: l10n.goDecision,
                          value: _isLoadingStats ? '-' : '$_approvedCount',
                          subtitle: _totalAssessments > 0
                              ? '${((_approvedCount / _totalAssessments) * 100).toInt()}%'
                              : '0%',
                          icon: Icons.check_circle_outline,
                          color: AppTheme.success,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildStatCard(
                          title: l10n.referDecision,
                          value: _isLoadingStats ? '-' : '$_pendingCount',
                          subtitle: l10n.processing,
                          icon: Icons.pending_outlined,
                          color: AppTheme.warning,
                        ),
                      ),
                    ],
                  ),
                ),
              ),

            if (_isBasicOrHigher) const SliverToBoxAdapter(child: SizedBox(height: 24)),

            // New Assessment Button - Upload Documents
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [AppTheme.primaryDark, AppTheme.primaryLight],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Material(
                    color: Colors.transparent,
                    child: InkWell(
                      key: const Key('startAnalysisButton'),
                      onTap: () => context.go('/home/intake'),
                      borderRadius: BorderRadius.circular(16),
                      child: Padding(
                        padding: const EdgeInsets.all(20.0),
                        child: Row(
                          children: [
                            Container(
                              width: 56,
                              height: 56,
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.2),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: const Icon(
                                Icons.add_circle_outline,
                                color: Colors.white,
                                size: 32,
                              ),
                            ),
                            const SizedBox(width: 16),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    l10n.startAnalysis,
                                    style: const TextStyle(
                                      fontSize: 18,
                                      fontWeight: FontWeight.w600,
                                      color: Colors.white,
                                      fontFamily: 'Inter',
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    l10n.uploadDocument,
                                    style: TextStyle(
                                      fontSize: 14,
                                      color: Colors.white.withValues(alpha: 0.8),
                                      fontFamily: 'Inter',
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const Icon(
                              Icons.arrow_forward_ios,
                              color: Colors.white,
                              size: 20,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),

            // QR Code option for web - mobile upload (Premium only)
            if (kIsWeb && _isPremium) ...[
              const SliverToBoxAdapter(child: SizedBox(height: 12)),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20.0),
                  child: Container(
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppTheme.border),
                    ),
                    child: Material(
                      color: Colors.transparent,
                      child: InkWell(
                        onTap: _isCreatingSession ? null : _showQRCodeModal,
                        borderRadius: BorderRadius.circular(16),
                        child: Padding(
                          padding: const EdgeInsets.all(16.0),
                          child: Row(
                            children: [
                              Container(
                                width: 48,
                                height: 48,
                                decoration: BoxDecoration(
                                  color: AppTheme.accent.withValues(alpha: 0.1),
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: _isCreatingSession
                                    ? const Padding(
                                        padding: EdgeInsets.all(12.0),
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                        ),
                                      )
                                    : Icon(
                                        Icons.qr_code_scanner,
                                        color: AppTheme.accent,
                                        size: 24,
                                      ),
                              ),
                              const SizedBox(width: 14),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      l10n.uploadDocument,
                                      style: const TextStyle(
                                        fontSize: 16,
                                        fontWeight: FontWeight.w600,
                                        color: AppTheme.textPrimary,
                                        fontFamily: 'Inter',
                                      ),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      l10n.uploadDocument,
                                      style: const TextStyle(
                                        fontSize: 13,
                                        color: AppTheme.textSecondary,
                                        fontFamily: 'Inter',
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              Icon(
                                Icons.arrow_forward_ios,
                                color: AppTheme.textHint,
                                size: 16,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],

            const SliverToBoxAdapter(child: SizedBox(height: 24)),

            // Recent Assessments Section
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      l10n.recentAssessments,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textPrimary,
                        fontFamily: 'Inter',
                      ),
                    ),
                    TextButton(
                      onPressed: () => context.go('/reports'),
                      child: Text(
                        l10n.viewAll,
                        style: const TextStyle(
                          color: AppTheme.primaryDark,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Recent Assessment List
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 20.0),
              sliver: _recentAssessments.isEmpty && !_isLoadingStats
                  ? SliverToBoxAdapter(
                      child: Container(
                        padding: const EdgeInsets.all(24),
                        decoration: BoxDecoration(
                          color: AppTheme.surface,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppTheme.border),
                        ),
                        child: Column(
                          children: [
                            Icon(Icons.folder_open_outlined, size: 48, color: AppTheme.textHint),
                            const SizedBox(height: 12),
                            Text(l10n.noData, style: const TextStyle(color: AppTheme.textSecondary)),
                            const SizedBox(height: 4),
                            Text(l10n.uploadDocument, style: const TextStyle(color: AppTheme.textHint, fontSize: 12)),
                          ],
                        ),
                      ),
                    )
                  : SliverList(
                      delegate: SliverChildBuilderDelegate(
                        (context, index) {
                          if (_isLoadingStats) {
                            return const Center(child: Padding(
                              padding: EdgeInsets.all(20),
                              child: CircularProgressIndicator(),
                            ));
                          }
                          final item = _recentAssessments[index];
                          final decision = (item['decision'] ?? 'pending').toString().toUpperCase();
                          final createdAt = DateTime.tryParse(item['created_at'] ?? '') ?? DateTime.now();
                          return _buildAssessmentItem(
                            context,
                            title: item['reference_number'] ?? 'Assessment #${item['id']}',
                            company: item['insured_name'] ?? item['title'] ?? 'Unknown',
                            status: decision == 'GO' ? 'GO' : (decision == 'NO_GO' ? 'NO-GO' : 'REFER'),
                            date: '${createdAt.day} ${_monthName(createdAt.month)} ${createdAt.year}',
                            assessmentId: '${item['id']}',
                          );
                        },
                        childCount: _isLoadingStats ? 1 : _recentAssessments.length,
                      ),
                    ),
            ),

            const SliverToBoxAdapter(child: SizedBox(height: 100)),
          ],
        ),
      ),
    );
  }

  Widget _buildStatCard({
    required String title,
    required String value,
    required String subtitle,
    required IconData icon,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: color, size: 20),
              ),
              Text(
                subtitle,
                style: const TextStyle(
                  fontSize: 12,
                  color: AppTheme.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            value,
            style: const TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
              fontFamily: 'Inter',
            ),
          ),
          const SizedBox(height: 4),
          Text(
            title,
            style: const TextStyle(
              fontSize: 14,
              color: AppTheme.textSecondary,
              fontFamily: 'Inter',
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAssessmentItem(
    BuildContext context, {
    required String title,
    required String company,
    required String status,
    required String date,
    required String assessmentId,
  }) {
    Color statusColor;
    switch (status) {
      case 'GO':
        statusColor = AppTheme.success;
        break;
      case 'NO-GO':
        statusColor = AppTheme.danger;
        break;
      default:
        statusColor = AppTheme.warning;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => context.go('/reports/results/$assessmentId'),
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(
                    status == 'GO' ? Icons.check_circle : (status == 'NO-GO' ? Icons.cancel : Icons.help),
                    color: statusColor,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                          fontFamily: 'Inter',
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        company,
                        style: const TextStyle(
                          fontSize: 14,
                          color: AppTheme.textSecondary,
                          fontFamily: 'Inter',
                        ),
                      ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: statusColor.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        status,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: statusColor,
                        ),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      date,
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppTheme.textHint,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
