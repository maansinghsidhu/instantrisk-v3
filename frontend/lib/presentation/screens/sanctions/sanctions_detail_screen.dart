import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/subscription_service.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../widgets/sanctions_network_map_widget.dart';

/// Sanctions Detail Screen
/// Shows detailed sanctions screening results for an assessment
class SanctionsDetailScreen extends StatefulWidget {
  final String assessmentId;

  const SanctionsDetailScreen({
    super.key,
    required this.assessmentId,
  });

  @override
  State<SanctionsDetailScreen> createState() => _SanctionsDetailScreenState();
}

class _SanctionsDetailScreenState extends State<SanctionsDetailScreen> {
  bool _isLoading = true;
  bool _isRunningDeep = false;
  String? _error;
  Map<String, dynamic> _summary = {};
  List<Map<String, dynamic>> _screenings = [];
  Map<String, dynamic>? _networkData;
  bool _isLoadingNetwork = false;

  @override
  void initState() {
    super.initState();
    _loadSanctionsSummary();
  }

  Future<void> _loadSanctionsSummary() async {
    try {
      setState(() {
        _isLoading = true;
        _error = null;
      });

      final response = await authService.get(
        '/sanctions/assessments/${widget.assessmentId}/summary'
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _summary = data;
          _screenings = List<Map<String, dynamic>>.from(data['screenings'] ?? []);
        });

        // Check if there's a full investigation and load network data
        final hasFullInvestigation = _screenings.any(
          (s) => s['level'] == 'full' || s['level'] == 'extensive' || s['level'] == 'deep'
        );
        if (hasFullInvestigation) {
          _loadNetworkData();
        }
      }

      setState(() => _isLoading = false);
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _runScreening(String level) async {
    // Use the level directly - backend expects: quick, enhanced, deep, full
    String screeningLevel = level;

    // Navigate to progress screen with level, reload data when returning
    await context.push(
      '/assessments/${widget.assessmentId}/sanctions/screening',
      extra: {'level': screeningLevel},
    );

    // Reload data when returning from progress screen
    _loadSanctionsSummary();

    // If it was a full investigation, also load network data
    if (level == 'full') {
      _loadNetworkData();
    }
  }

  Future<void> _loadNetworkData() async {
    setState(() => _isLoadingNetwork = true);

    try {
      // Try to get network data from the latest full investigation
      final response = await authService.get(
        '/sanctions/assessments/${widget.assessmentId}/network'
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _networkData = data['network_map'];
        });
      }
    } catch (e) {
      debugPrint('Failed to load network data: $e');
      // Check if any screening has network data
      for (final screening in _screenings) {
        if (screening['network_map'] != null) {
          setState(() {
            _networkData = Map<String, dynamic>.from(screening['network_map']);
          });
          break;
        }
      }
    } finally {
      setState(() => _isLoadingNetwork = false);
    }
  }

  Color _getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'clear':
        return const Color(0xFF059669);
      case 'review':
        return const Color(0xFFF59E0B);
      case 'match':
        return const Color(0xFFDC2626);
      case 'no_entities':
        return Color(0xFF6B7280);
      default:
        return AppTheme.text2(context);
    }
  }

  IconData _getStatusIcon(String status) {
    switch (status.toLowerCase()) {
      case 'clear':
        return Icons.check_circle;
      case 'review':
        return Icons.warning;
      case 'match':
        return Icons.dangerous;
      case 'no_entities':
        return Icons.info_outline;
      default:
        return Icons.help_outline;
    }
  }

  String _getStatusText(String status, AppLocalizations l10n) {
    switch (status.toLowerCase()) {
      case 'clear':
        return l10n.clear;
      case 'review':
        return l10n.reviewRequired;
      case 'match':
        return l10n.matchFound;
      case 'not_screened':
        return 'NOT SCREENED';
      case 'no_entities':
        return l10n.noEntitiesFound;
      default:
        return status.toUpperCase();
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    // Check if user has access to sanctions screening (Premium only)
    if (!subscriptionService.hasFeature('sanctions_screening')) {
      return Scaffold(
        backgroundColor: AppTheme.bg(context),
        appBar: AppBar(
          backgroundColor: AppTheme.surfaceOf(context),
          elevation: 0,
          leading: IconButton(
            icon: Icon(Icons.arrow_back, color: AppTheme.text1(context)),
            onPressed: () => context.canPop() ? context.pop() : context.go('/reports'),
          ),
          title: Text(
            l10n.sanctionsScreening,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: AppTheme.text1(context),
            ),
          ),
          centerTitle: true,
        ),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(32.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: Colors.orange.shade50,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Icon(
                    Icons.shield_outlined,
                    size: 64,
                    color: Colors.orange.shade700,
                  ),
                ),
                const SizedBox(height: 24),
                Text(
                  'Sanctions Screening',
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.text1(context),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  'Screen entities against global sanctions lists including OFAC, UN, EU, and UK sanctions.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 15,
                    color: AppTheme.text2(context),
                    height: 1.5,
                  ),
                ),
                const SizedBox(height: 32),
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryDark.withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.primaryDark.withValues(alpha: 0.2)),
                  ),
                  child: Column(
                    children: [
                      const Icon(Icons.workspace_premium, color: AppTheme.primaryDark, size: 32),
                      const SizedBox(height: 8),
                      const Text(
                        'Premium Feature',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.primaryDark,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Upgrade to Premium to access sanctions screening',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 13, color: AppTheme.text2(context)),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: () => context.go('/subscription'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primaryDark,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: const Text('Upgrade to Premium', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceOf(context),
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: AppTheme.text1(context)),
          onPressed: () {
            if (context.canPop()) {
              context.pop();
            } else {
              context.go('/reports');
            }
          },
        ),
        title: Text(
          l10n.sanctionsScreening,
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.text1(context),
          ),
        ),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => _loadSanctionsSummary(),
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildErrorState(l10n)
              : _buildContent(l10n),
    );
  }

  Widget _buildContent(AppLocalizations l10n) {
    final status = _summary['overall_status'] ?? 'not_screened';
    final statusColor = _getStatusColor(status);

    return Column(
      children: [
        // Status header
        Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: statusColor.withOpacity(0.1),
            border: Border(bottom: BorderSide(color: statusColor.withOpacity(0.3))),
          ),
          child: Column(
            children: [
              // Status icon
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: statusColor.withOpacity(0.2),
                ),
                child: Icon(
                  _getStatusIcon(status),
                  size: 40,
                  color: statusColor,
                ),
              ),
              const SizedBox(height: 16),
              // Status text
              Text(
                _getStatusText(status, l10n),
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: statusColor,
                  letterSpacing: 1,
                ),
              ),
              const SizedBox(height: 8),
              if (_summary['total_screenings'] != null && _summary['total_screenings'] > 0)
                Text(
                  'Last screened: ${_summary['last_screened']?.toString().split('T')[0] ?? 'Unknown'}',
                  style: TextStyle(
                    fontSize: 13,
                    color: AppTheme.text2(context),
                  ),
                ),
            ],
          ),
        ),

        // Stats row
        if (_summary['total_screenings'] != null && _summary['total_screenings'] > 0)
          Container(
            padding: EdgeInsets.all(16),
            color: AppTheme.surfaceOf(context),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildStat('Screenings', '${_summary['total_screenings'] ?? 0}'),
                _buildStat('Entities', '${_summary['entities_screened'] ?? 0}'),
                _buildStat('Matches', '${_summary['matches_found'] ?? 0}'),
                _buildStat('Score', '${(_summary['highest_score'] ?? 0).toStringAsFixed(0)}%'),
              ],
            ),
          ),

        // Content
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Screening levels section
              _buildLevelsSection(l10n),

              const SizedBox(height: 24),

              // Screening history
              if (_screenings.isNotEmpty) ...[
                Text(
                  l10n.screeningHistory,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textH(context),
                    letterSpacing: 1,
                  ),
                ),
                const SizedBox(height: 12),
                ..._screenings.map((s) => _buildScreeningCard(s)),
              ],

              // Network Map Visualization (shown after full investigation)
              const SizedBox(height: 24),
              _buildNetworkMapSection(l10n),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildNetworkMapSection(AppLocalizations l10n) {
    // Check if any screening has network data
    final hasFullInvestigation = _screenings.any(
      (s) => s['level'] == 'full' || s['level'] == 'extensive' || s['level'] == 'deep'
    );

    if (!hasFullInvestigation && _networkData == null) {
      return Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppTheme.surfaceOf(context),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppTheme.borderOf(context)),
        ),
        child: Column(
          children: [
            Icon(
              Icons.hub_outlined,
              size: 48,
              color: AppTheme.textH(context),
            ),
            const SizedBox(height: 12),
            Text(
              'Network Map',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppTheme.text1(context),
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'Run "Extensive" screening to visualize\nentity relationships and connections',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13,
                color: AppTheme.text2(context),
              ),
            ),
          ],
        ),
      );
    }

    if (_isLoadingNetwork) {
      return Container(
        padding: const EdgeInsets.all(40),
        decoration: BoxDecoration(
          color: AppTheme.surfaceOf(context),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppTheme.borderOf(context)),
        ),
        child: Center(
          child: Column(
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 12),
              Text(
                'Loading network data...',
                style: TextStyle(color: AppTheme.text2(context)),
              ),
            ],
          ),
        ),
      );
    }

    // Use network data from state or extract from screenings
    Map<String, dynamic> networkMap = _networkData ?? {};
    if (networkMap.isEmpty) {
      for (final screening in _screenings) {
        if (screening['network_map'] != null) {
          networkMap = Map<String, dynamic>.from(screening['network_map']);
          break;
        }
        // Also check in result field
        final result = screening['result'];
        if (result != null && result['network_map'] != null) {
          networkMap = Map<String, dynamic>.from(result['network_map']);
          break;
        }
      }
    }

    return SanctionsNetworkMapWidget(
      networkData: networkMap,
      onNodeTap: (entityId) {
        // Show entity details in a bottom sheet
        _showEntityDetails(entityId, networkMap);
      },
    );
  }

  void _showEntityDetails(String entityId, Map<String, dynamic> networkMap) {
    final nodes = networkMap['nodes'] as List<dynamic>? ?? [];
    Map<String, dynamic>? foundEntity;
    for (final node in nodes) {
      if (node['id']?.toString() == entityId) {
        foundEntity = Map<String, dynamic>.from(node);
        break;
      }
    }

    if (foundEntity == null) return;

    // Create non-null reference for use in builder
    final entity = foundEntity;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => Container(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.orange.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.person,
                    color: Colors.orange,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        entity['name']?.toString() ?? 'Unknown Entity',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text1(context),
                        ),
                      ),
                      Text(
                        entity['type']?.toString().toUpperCase() ?? 'ENTITY',
                        style: TextStyle(
                          fontSize: 12,
                          color: AppTheme.text2(context),
                        ),
                      ),
                    ],
                  ),
                ),
                if (entity['score'] != null)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: _getScoreColor((entity['score'] as num).toDouble()).withOpacity(0.1),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      '${(entity['score'] as num).toStringAsFixed(0)}%',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: _getScoreColor((entity['score'] as num).toDouble()),
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 20),
            const Divider(),
            const SizedBox(height: 16),

            if (entity['datasets'] != null && (entity['datasets'] as List).isNotEmpty) ...[
              Text(
                'Data Sources',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.text1(context),
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: (entity['datasets'] as List).map((ds) => Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryDark.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    ds.toString().toUpperCase(),
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.primaryDark,
                    ),
                  ),
                )).toList(),
              ),
            ],

            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pop(context),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryDark,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  'Close',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Color _getScoreColor(double score) {
    if (score >= 80) return Colors.red.shade700;
    if (score >= 60) return Colors.orange.shade700;
    if (score >= 40) return Colors.amber.shade600;
    return AppTheme.success;
  }

  Widget _buildStat(String label, String value) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.w700,
            color: AppTheme.text1(context),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            color: AppTheme.text2(context),
          ),
        ),
      ],
    );
  }

  Widget _buildLevelsSection(AppLocalizations l10n) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          l10n.screeningLevels,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: AppTheme.textH(context),
            letterSpacing: 1,
          ),
        ),
        const SizedBox(height: 12),

        // Quick (~5s)
        _buildLevelCard(
          l10n: l10n,
          level: 1,
          name: 'Quick',
          description: 'Fast check against OFAC, EU, UN sanctions lists (~5s)',
          isAuto: true,
          isComplete: _screenings.any((s) => s['level'] == 'quick' || s['level'] == 'enhanced'),
          onRun: () => _runScreening('quick'),
          color: const Color(0xFF2563EB),
        ),

        const SizedBox(height: 12),

        // Standard (~20s)
        _buildLevelCard(
          l10n: l10n,
          level: 2,
          name: 'Standard',
          description: 'Fuzzy matching, PEPs, adverse media, aliases (~20s)',
          isAuto: false,
          isComplete: _screenings.any((s) => s['level'] == 'enhanced' || s['level'] == 'standard' || s['level'] == 'deep'),
          onRun: () => _runScreening('standard'),
          color: const Color(0xFF7C3AED),
        ),

        const SizedBox(height: 12),

        // Extensive (~60s)
        _buildLevelCard(
          l10n: l10n,
          level: 3,
          name: 'Extensive',
          description: 'Full investigation with network mapping, ownership chains, AI analysis (~60s)',
          isAuto: false,
          isComplete: _screenings.any((s) => s['level'] == 'full' || s['level'] == 'extensive' || s['level'] == 'deep'),
          onRun: () => _runScreening('extensive'),
          color: const Color(0xFF6366F1),
        ),
      ],
    );
  }

  Widget _buildLevelCard({
    required AppLocalizations l10n,
    required int level,
    required String name,
    required String description,
    required bool isAuto,
    required bool isComplete,
    required VoidCallback onRun,
    Color? color,
  }) {
    final cardColor = isComplete
        ? const Color(0xFF059669)
        : color ?? (isAuto ? const Color(0xFF2563EB) : const Color(0xFF7C3AED));

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isComplete ? cardColor : AppTheme.borderOf(context),
          width: isComplete ? 2 : 1,
        ),
      ),
      child: Row(
        children: [
          // Level indicator
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: cardColor.withOpacity(0.1),
            ),
            child: Center(
              child: isComplete
                  ? Icon(Icons.check, color: cardColor, size: 20)
                  : Text(
                      '$level',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: cardColor,
                      ),
                    ),
            ),
          ),
          const SizedBox(width: 16),

          // Info
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      name,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.text1(context),
                      ),
                    ),
                    if (isAuto) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: const Color(0xFF2563EB).withOpacity(0.1),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text(
                          'AUTO',
                          style: TextStyle(
                            fontSize: 9,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF2563EB),
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  description,
                  style: TextStyle(
                    fontSize: 12,
                    color: AppTheme.text2(context),
                  ),
                ),
              ],
            ),
          ),

          // Action button
          if (!isComplete)
            ElevatedButton(
              onPressed: onRun,
              style: ElevatedButton.styleFrom(
                backgroundColor: cardColor,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              child: Text(l10n.run, style: const TextStyle(fontSize: 13)),
            )
          else
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: cardColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                l10n.complete,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: cardColor,
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildScreeningCard(Map<String, dynamic> screening) {
    final status = screening['status'] ?? 'pending';
    final statusColor = _getStatusColor(status);
    final level = screening['level'] ?? 'unknown';
    final matches = List<Map<String, dynamic>>.from(screening['match_details'] ?? []);
    final hasMatches = matches.isNotEmpty;
    final sourcesChecked = List<String>.from(screening['sources_checked'] ?? []);
    final durationMs = screening['duration_ms'] as int?;

    // Format level name for display
    String levelDisplay = level.toString().toUpperCase();
    if (level == 'enhanced') levelDisplay = 'STANDARD';
    if (level == 'deep') levelDisplay = 'EXTENSIVE';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: hasMatches ? statusColor : AppTheme.borderOf(context)),
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          childrenPadding: EdgeInsets.zero,
          initiallyExpanded: hasMatches,
          leading: Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: statusColor.withOpacity(0.1),
            ),
            child: Icon(
              _getStatusIcon(status),
              size: 18,
              color: statusColor,
            ),
          ),
          title: Text(
            levelDisplay,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: AppTheme.text1(context),
            ),
          ),
          subtitle: Text(
            '${screening['entities'] ?? 0} entities, ${screening['matches'] ?? 0} matches',
            style: TextStyle(
              fontSize: 12,
              color: AppTheme.text2(context),
            ),
          ),
          trailing: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '${(screening['score'] ?? 0).toStringAsFixed(0)}%',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: statusColor,
                ),
              ),
              Text(
                screening['completed']?.toString().split('T')[0] ?? '',
                style: TextStyle(
                  fontSize: 10,
                  color: AppTheme.textH(context),
                ),
              ),
            ],
          ),
          children: [
            // Sources checked section
            if (sourcesChecked.isNotEmpty)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: AppTheme.primaryDark.withOpacity(0.03),
                  border: Border(top: BorderSide(color: AppTheme.borderOf(context).withOpacity(0.5))),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.checklist, size: 14, color: AppTheme.primaryDark),
                        const SizedBox(width: 6),
                        Text(
                          'Sources Checked (${sourcesChecked.length})',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.primaryDark,
                            letterSpacing: 0.5,
                          ),
                        ),
                        const Spacer(),
                        if (durationMs != null)
                          Text(
                            '${(durationMs / 1000).toStringAsFixed(1)}s',
                            style: TextStyle(
                              fontSize: 10,
                              color: AppTheme.textH(context),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: sourcesChecked.map((source) => Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppTheme.success.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: AppTheme.success.withOpacity(0.3)),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.check_circle, size: 10, color: AppTheme.success),
                            const SizedBox(width: 4),
                            Text(
                              source,
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w500,
                                color: AppTheme.text1(context),
                              ),
                            ),
                          ],
                        ),
                      )).toList(),
                    ),
                  ],
                ),
              ),

            // Match details (if any)
            if (hasMatches)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.05),
                  border: Border(top: BorderSide(color: statusColor.withOpacity(0.2))),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.people_outline, size: 14, color: statusColor),
                        const SizedBox(width: 6),
                        Text(
                          'Match Details',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: statusColor,
                            letterSpacing: 0.5,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    ...matches.take(5).map((match) => _buildMatchDetailRow(match)),
                    if (matches.length > 5)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(
                          '+ ${matches.length - 5} more matches...',
                          style: TextStyle(
                            fontSize: 11,
                            color: statusColor,
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildMatchDetailRow(Map<String, dynamic> match) {
    final entityName = match['entity_name'] ?? match['query'] ?? 'Unknown Entity';
    final matchName = match['match_name'] ?? match['name'] ?? 'Unknown Match';
    final dataset = match['dataset'] ?? match['list'] ?? 'Unknown List';
    final score = (match['score'] ?? match['match_score'] ?? 0.0);
    final scorePercent = score is double ? (score * 100).toInt() : score;

    // Color based on score
    Color scoreColor;
    if (scorePercent >= 80) {
      scoreColor = const Color(0xFFDC2626); // Red for high match
    } else if (scorePercent >= 60) {
      scoreColor = const Color(0xFFF59E0B); // Orange for medium
    } else {
      scoreColor = const Color(0xFF6B7280); // Gray for low
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Entity screened
          Row(
            children: [
              Icon(Icons.search, size: 12, color: AppTheme.text2(context)),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  'Screened: $entityName',
                  style: TextStyle(
                    fontSize: 11,
                    color: AppTheme.text2(context),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          // Match found
          Row(
            children: [
              Icon(Icons.warning_amber, size: 12, color: scoreColor),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  'Matched: $matchName',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: scoreColor,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: scoreColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  '$scorePercent%',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    color: scoreColor,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          // Dataset/List
          Row(
            children: [
              Icon(Icons.list_alt, size: 12, color: AppTheme.textH(context)),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  'List: ${_formatDataset(dataset)}',
                  style: TextStyle(
                    fontSize: 10,
                    color: AppTheme.textH(context),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _formatDataset(String dataset) {
    // Format common dataset names for display
    final formatted = dataset
        .replaceAll('_', ' ')
        .replaceAll('sanctions', 'Sanctions')
        .replaceAll('ofac', 'OFAC')
        .replaceAll('eu', 'EU')
        .replaceAll('un', 'UN')
        .replaceAll('uk', 'UK');
    return formatted.length > 30 ? '${formatted.substring(0, 30)}...' : formatted;
  }

  Widget _buildErrorState(AppLocalizations l10n) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.error_outline, size: 64, color: Colors.red),
          const SizedBox(height: 16),
          Text(
            _error ?? l10n.error,
            style: const TextStyle(color: Colors.red),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: _loadSanctionsSummary,
            child: Text(l10n.retry),
          ),
        ],
      ),
    );
  }
}
