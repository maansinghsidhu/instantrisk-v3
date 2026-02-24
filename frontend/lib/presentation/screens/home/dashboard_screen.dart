import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/subscription_service.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../widgets/common/screen_header.dart';

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

  // Shared With Me
  List<Map<String, dynamic>> _sharedWithMe = [];
  bool _isLoadingShared = true;

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
    _fetchSharedWithMe();
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
          } else if (decision == 'pending') {
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

  Future<void> _fetchSharedWithMe() async {
    try {
      final response = await authService.get('/api/v1/shares/received');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as List? ?? [];
        if (mounted) {
          setState(() {
            _sharedWithMe = data.take(5).map((e) => Map<String, dynamic>.from(e as Map)).toList();
            _isLoadingShared = false;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoadingShared = false);
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
              style: TextStyle(color: AppTheme.text2(context), fontSize: 14),
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
                  border: Border.all(color: AppTheme.borderOf(context), width: 2),
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
                        style: TextStyle(fontSize: 12, color: AppTheme.text2(context)),
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
      backgroundColor: AppTheme.bg(context),
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            // App Bar with unified header
            SliverToBoxAdapter(
              child: ScreenHeader(
                title: _userName,
                subtitle: l10n.welcomeBack,
                badge: 'Powered by InstantRisk Engine',
                actions: [
                  Container(
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: IconButton(
                      onPressed: () {},
                      icon: Stack(
                        children: [
                          const Icon(Icons.notifications_outlined, color: Colors.white, size: 24),
                          Positioned(
                            right: 0, top: 0,
                            child: Container(
                              width: 9, height: 9,
                              decoration: BoxDecoration(
                                color: AppTheme.danger,
                                shape: BoxShape.circle,
                                border: Border.all(color: AppTheme.darkBg, width: 1.5),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Container(
                    padding: const EdgeInsets.all(3),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white.withValues(alpha: 0.3), width: 2),
                    ),
                    child: CircleAvatar(
                      radius: 20,
                      backgroundColor: AppTheme.primaryDark,
                      child: Text(
                        _userInitials,
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 15),
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SliverToBoxAdapter(child: SizedBox(height: 20)),

            // Quick Stats Cards - 3 cards for better overview (Basic+ only)
            if (_isBasicOrHigher)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16.0),
                  child: LayoutBuilder(
                    builder: (context, constraints) {
                      final narrow = constraints.maxWidth < 380;
                      final gap = narrow ? 6.0 : 10.0;
                      return Row(
                        children: [
                          Expanded(
                            child: _buildStatCard(
                              title: l10n.reports,
                              value: _isLoadingStats ? '-' : '$_totalAssessments',
                              subtitle: l10n.reports,
                              icon: Icons.assessment_outlined,
                              color: AppTheme.primaryDark,
                              compact: narrow,
                            ),
                          ),
                          SizedBox(width: gap),
                          Expanded(
                            child: _buildStatCard(
                              title: l10n.goDecision,
                              value: _isLoadingStats ? '-' : '$_approvedCount',
                              subtitle: _totalAssessments > 0
                                  ? '${((_approvedCount / _totalAssessments) * 100).toInt()}%'
                                  : '0%',
                              icon: Icons.check_circle_outline,
                              color: AppTheme.success,
                              compact: narrow,
                            ),
                          ),
                          SizedBox(width: gap),
                          Expanded(
                            child: _buildStatCard(
                              title: l10n.pending,
                              value: _isLoadingStats ? '-' : '$_pendingCount',
                              subtitle: l10n.processing,
                              icon: Icons.pending_outlined,
                              color: AppTheme.warning,
                              compact: narrow,
                            ),
                          ),
                        ],
                      );
                    },
                  ),
                ),
              ),

            if (_isBasicOrHigher) const SliverToBoxAdapter(child: SizedBox(height: 24)),

            // New Assessment Button - Upload Documents
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: Container(
                  decoration: BoxDecoration(
                    color: AppTheme.primaryDark,
                    borderRadius: BorderRadius.circular(20),
                    boxShadow: [
                      BoxShadow(
                        color: AppTheme.primaryDark.withValues(alpha: 0.25),
                        blurRadius: 16,
                        offset: const Offset(0, 6),
                      ),
                    ],
                  ),
                  child: Material(
                    color: Colors.transparent,
                    child: InkWell(
                      key: const Key('startAnalysisButton'),
                      onTap: () => context.go('/home/intake'),
                      borderRadius: BorderRadius.circular(20),
                      child: Padding(
                        padding: const EdgeInsets.all(16.0),
                        child: Row(
                          children: [
                            Container(
                              width: 44,
                              height: 44,
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.2),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: const Icon(
                                Icons.bolt_rounded,
                                color: Colors.white,
                                size: 24,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    l10n.startAnalysis,
                                    style: const TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.w700,
                                      color: Colors.white,
                                      fontFamily: 'Inter',
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    'Upload documents for analysis',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.white.withValues(alpha: 0.85),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const Icon(
                              Icons.arrow_forward_rounded,
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
                  padding: const EdgeInsets.symmetric(horizontal: 16.0),
                  child: Container(
                    decoration: BoxDecoration(
                      color: AppTheme.surfaceOf(context),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppTheme.borderOf(context)),
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
                                  color: AppTheme.primaryDark.withValues(alpha: 0.1),
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
                                        color: AppTheme.primaryDark,
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
                                      style: TextStyle(
                                        fontSize: 16,
                                        fontWeight: FontWeight.w600,
                                        color: AppTheme.text1(context),
                                        fontFamily: 'Inter',
                                      ),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      l10n.uploadDocument,
                                      style: TextStyle(
                                        fontSize: 13,
                                        color: AppTheme.text2(context),
                                        fontFamily: 'Inter',
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              Icon(
                                Icons.arrow_forward_ios,
                                color: AppTheme.textH(context),
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
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      l10n.recentAssessments,
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.text1(context),
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
              padding: const EdgeInsets.symmetric(horizontal: 16.0),
              sliver: _recentAssessments.isEmpty && !_isLoadingStats
                  ? SliverToBoxAdapter(
                      child: Container(
                        padding: const EdgeInsets.all(24),
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceOf(context),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppTheme.borderOf(context)),
                        ),
                        child: Column(
                          children: [
                            Icon(Icons.folder_open_outlined, size: 48, color: AppTheme.textH(context)),
                            SizedBox(height: 12),
                            Text(l10n.noData, style: TextStyle(color: AppTheme.text2(context))),
                            SizedBox(height: 4),
                            Text(l10n.uploadDocument, style: TextStyle(color: AppTheme.textH(context), fontSize: 12)),
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
                            status: decision == 'GO' ? 'GO' : 'NO-GO',
                            date: '${createdAt.day} ${_monthName(createdAt.month)} ${createdAt.year}',
                            assessmentId: '${item['id']}',
                          );
                        },
                        childCount: _isLoadingStats ? 1 : _recentAssessments.length,
                      ),
                    ),
            ),

            const SliverToBoxAdapter(child: SizedBox(height: 24)),

            // Shared With Me Section
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.share_outlined, color: AppTheme.primaryDark, size: 22),
                        const SizedBox(width: 8),
                        Text(
                          'Shared With Me',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.text1(context),
                            fontFamily: 'Inter',
                          ),
                        ),
                      ],
                    ),
                    TextButton(
                      onPressed: () => context.go('/shared'),
                      child: const Text(
                        'View All',
                        style: TextStyle(
                          color: AppTheme.primaryDark,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Shared With Me List
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0),
              sliver: _sharedWithMe.isEmpty && !_isLoadingShared
                  ? SliverToBoxAdapter(
                      child: Container(
                        padding: const EdgeInsets.all(24),
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceOf(context),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppTheme.borderOf(context)),
                        ),
                        child: Column(
                          children: [
                            Icon(Icons.share_outlined, size: 48, color: AppTheme.textH(context)),
                            const SizedBox(height: 12),
                            Text('No shared submissions', style: TextStyle(color: AppTheme.text2(context))),
                            const SizedBox(height: 4),
                            Text('Submissions shared with you will appear here', 
                                style: TextStyle(color: AppTheme.textH(context), fontSize: 12)),
                          ],
                        ),
                      ),
                    )
                  : SliverList(
                      delegate: SliverChildBuilderDelegate(
                        (context, index) {
                          if (_isLoadingShared) {
                            return const Center(
                                child: Padding(
                              padding: EdgeInsets.all(20),
                              child: CircularProgressIndicator(),
                            ));
                          }
                          final item = _sharedWithMe[index];
                          final share = item['share'] as Map<String, dynamic>;
                          final assessment = item['assessment'] as Map<String, dynamic>;
                          final createdAt = DateTime.tryParse(share['created_at'] ?? '') ?? DateTime.now();
                          return _buildSharedItem(
                            context,
                            title: assessment['reference_number'] ?? 'Assessment #${assessment['id']}',
                            company: assessment['insured_name'] ?? 'Unknown',
                            sharedBy: share['shared_by_name'] ?? 'Unknown',
                            shareType: share['share_type'] ?? 'analysis',
                            date: '${createdAt.day} ${_monthName(createdAt.month)} ${createdAt.year}',
                            assessmentId: '${assessment['id']}',
                          );
                        },
                        childCount: _isLoadingShared ? 1 : _sharedWithMe.length,
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
    bool compact = false,
  }) {
    return Container(
      padding: EdgeInsets.all(compact ? 12 : 18),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.borderOf(context)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 10,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: EdgeInsets.all(compact ? 6 : 10),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: color, size: compact ? 16 : 20),
          ),
          SizedBox(height: compact ? 8 : 14),
          Text(
            value,
            style: TextStyle(
              fontSize: compact ? 22 : 32,
              fontWeight: FontWeight.w800,
              color: AppTheme.text1(context),
              fontFamily: 'Inter',
              letterSpacing: -1,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            title,
            style: TextStyle(
              fontSize: compact ? 11 : 13,
              fontWeight: FontWeight.w500,
              color: AppTheme.text2(context),
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
    IconData statusIcon;
    switch (status) {
      case 'GO':
        statusColor = AppTheme.success;
        statusIcon = Icons.check_circle_rounded;
        break;
      case 'NO-GO':
        statusColor = AppTheme.danger;
        statusIcon = Icons.cancel_rounded;
        break;
      default:
        statusColor = AppTheme.warning;
        statusIcon = Icons.schedule_rounded;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.borderOf(context)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => context.go('/reports/results/$assessmentId'),
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  width: 50,
                  height: 50,
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Icon(statusIcon, color: statusColor, size: 24),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        company,
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text1(context),
                          fontFamily: 'Inter',
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 3),
                      Row(
                        children: [
                          Icon(Icons.tag_rounded, size: 13, color: AppTheme.textH(context)),
                          const SizedBox(width: 4),
                          Flexible(
                            child: Text(
                              title,
                              style: TextStyle(
                                fontSize: 12,
                                color: AppTheme.text2(context),
                                fontFamily: 'Inter',
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          SizedBox(width: 8),
                          Icon(Icons.calendar_today_rounded, size: 11, color: AppTheme.textH(context)),
                          const SizedBox(width: 3),
                          Text(
                            date,
                            style: TextStyle(
                              fontSize: 11,
                              color: AppTheme.textH(context),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    status,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      color: statusColor,
                      letterSpacing: 0.5,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSharedItem(
    BuildContext context, {
    required String title,
    required String company,
    required String sharedBy,
    required String shareType,
    required String date,
    required String assessmentId,
  }) {
    final shareIcon = shareType == 'analysis' 
        ? Icons.analytics_outlined 
        : Icons.description_outlined;
    final shareColor = shareType == 'analysis' 
        ? AppTheme.primaryDark 
        : AppTheme.success;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.borderOf(context)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => context.go('/reports/results/$assessmentId'),
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  width: 50,
                  height: 50,
                  decoration: BoxDecoration(
                    color: shareColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Icon(shareIcon, color: shareColor, size: 24),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        company,
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text1(context),
                          fontFamily: 'Inter',
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 3),
                      Row(
                        children: [
                          Icon(Icons.tag_rounded, size: 13, color: AppTheme.textH(context)),
                          const SizedBox(width: 4),
                          Flexible(
                            child: Text(
                              title,
                              style: TextStyle(
                                fontSize: 12,
                                color: AppTheme.text2(context),
                                fontFamily: 'Inter',
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 3),
                      Row(
                        children: [
                          Icon(Icons.person_outline_rounded, size: 11, color: AppTheme.textH(context)),
                          const SizedBox(width: 3),
                          Text(
                            'Shared by $sharedBy',
                            style: TextStyle(
                              fontSize: 11,
                              color: AppTheme.textH(context),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Icon(Icons.calendar_today_rounded, size: 11, color: AppTheme.textH(context)),
                          const SizedBox(width: 3),
                          Text(
                            date,
                            style: TextStyle(
                              fontSize: 11,
                              color: AppTheme.textH(context),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
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
          ),
        ),
      ),
    );
  }
}
