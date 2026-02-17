import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/monitoring_service.dart';

/// RiskAlertsPanel - Shows all active monitoring alerts (HIBP, news, scoring changes)
/// Used on the monitoring dashboard and in results screens.
class RiskAlertsPanel extends StatefulWidget {
  final String? assessmentId;
  final bool showHeader;
  final int maxAlerts;
  final VoidCallback? onViewAll;

  const RiskAlertsPanel({
    super.key,
    this.assessmentId,
    this.showHeader = true,
    this.maxAlerts = 10,
    this.onViewAll,
  });

  @override
  State<RiskAlertsPanel> createState() => _RiskAlertsPanelState();
}

class _RiskAlertsPanelState extends State<RiskAlertsPanel> {
  List<Map<String, dynamic>> _alerts = [];
  bool _isLoading = true;
  String _filterSeverity = 'all';

  @override
  void initState() {
    super.initState();
    _loadAlerts();
  }

  Future<void> _loadAlerts() async {
    setState(() => _isLoading = true);
    final results = await monitoringService.getAlerts(
      severity: _filterSeverity == 'all' ? null : _filterSeverity,
      limit: widget.maxAlerts,
    );
    if (mounted) {
      setState(() {
        _alerts = results;
        _isLoading = false;
      });
    }
  }

  Color _severityColor(String severity) {
    switch (severity.toLowerCase()) {
      case 'critical':
        return const Color(0xFF7C3AED);
      case 'high':
        return AppTheme.danger;
      case 'medium':
        return AppTheme.warning;
      case 'low':
        return AppTheme.info;
      default:
        return AppTheme.textSecondary;
    }
  }

  IconData _alertTypeIcon(String type) {
    switch (type.toLowerCase()) {
      case 'breach':
      case 'hibp':
        return Icons.security;
      case 'news':
        return Icons.newspaper;
      case 'score_change':
        return Icons.trending_up;
      case 'sanctions':
        return Icons.gavel;
      default:
        return Icons.notifications_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (widget.showHeader) ...[
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: AppTheme.danger.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.notifications_active_outlined,
                      size: 18,
                      color: AppTheme.danger,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Risk Alerts',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.text1(context),
                      ),
                    ),
                  ),
                  if (_alerts.isNotEmpty)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: AppTheme.danger.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        '${_alerts.length}',
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.danger,
                        ),
                      ),
                    ),
                  const SizedBox(width: 8),
                  IconButton(
                    icon: const Icon(Icons.refresh, size: 18),
                    onPressed: _loadAlerts,
                    tooltip: 'Refresh alerts',
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                    color: AppTheme.text2(context),
                  ),
                ],
              ),
            ),

            // Severity filter chips
            SizedBox(
              height: 36,
              child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                children: ['all', 'critical', 'high', 'medium', 'low'].map((sev) {
                  final isSelected = _filterSeverity == sev;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(
                        sev[0].toUpperCase() + sev.substring(1),
                        style: TextStyle(
                          fontSize: 11,
                          color: isSelected ? Colors.white : AppTheme.text2(context),
                        ),
                      ),
                      selected: isSelected,
                      selectedColor: sev == 'all'
                          ? AppTheme.primaryDark
                          : _severityColor(sev),
                      onSelected: (_) {
                        setState(() => _filterSeverity = sev);
                        _loadAlerts();
                      },
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      visualDensity: VisualDensity.compact,
                    ),
                  );
                }).toList(),
              ),
            ),
            const SizedBox(height: 8),
            Divider(height: 1, color: AppTheme.borderOf(context)),
          ],

          if (_isLoading)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (_alerts.isEmpty)
            Padding(
              padding: const EdgeInsets.all(24),
              child: Center(
                child: Column(
                  children: [
                    Icon(Icons.check_circle_outline,
                        size: 36, color: AppTheme.success),
                    const SizedBox(height: 8),
                    Text(
                      'No active alerts',
                      style: TextStyle(
                        fontSize: 14,
                        color: AppTheme.text2(context),
                      ),
                    ),
                  ],
                ),
              ),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _alerts.length,
              separatorBuilder: (_, __) =>
                  Divider(height: 1, color: AppTheme.borderOf(context)),
              itemBuilder: (context, index) {
                final alert = _alerts[index];
                return _AlertTile(
                  alert: alert,
                  severityColor: _severityColor(
                    alert['severity']?.toString() ?? 'low',
                  ),
                  typeIcon: _alertTypeIcon(
                    alert['type']?.toString() ?? 'general',
                  ),
                  onAcknowledge: () async {
                    final id = alert['id']?.toString() ?? '';
                    if (id.isNotEmpty) {
                      await monitoringService.acknowledgeAlert(id);
                      _loadAlerts();
                    }
                  },
                );
              },
            ),

          if (widget.onViewAll != null && _alerts.length >= widget.maxAlerts)
            InkWell(
              onTap: widget.onViewAll,
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 12),
                alignment: Alignment.center,
                child: Text(
                  'View all alerts',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.primaryDark,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _AlertTile extends StatelessWidget {
  final Map<String, dynamic> alert;
  final Color severityColor;
  final IconData typeIcon;
  final VoidCallback onAcknowledge;

  const _AlertTile({
    required this.alert,
    required this.severityColor,
    required this.typeIcon,
    required this.onAcknowledge,
  });

  @override
  Widget build(BuildContext context) {
    final title = alert['title']?.toString() ?? alert['message']?.toString() ?? 'Alert';
    final description = alert['description']?.toString() ?? '';
    final severity = alert['severity']?.toString() ?? 'low';
    final timestamp = alert['created_at']?.toString() ?? alert['timestamp']?.toString() ?? '';

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Icon container
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: severityColor.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(typeIcon, size: 18, color: severityColor),
          ),
          const SizedBox(width: 12),

          // Content
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        title,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text1(context),
                        ),
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: severityColor.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        severity.toUpperCase(),
                        style: TextStyle(
                          fontSize: 9,
                          fontWeight: FontWeight.w700,
                          color: severityColor,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ),
                  ],
                ),
                if (description.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(
                      description,
                      style: TextStyle(
                        fontSize: 12,
                        color: AppTheme.text2(context),
                        height: 1.3,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                if (timestamp.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Row(
                      children: [
                        Text(
                          timestamp.length > 19
                              ? timestamp.substring(0, 19).replaceAll('T', ' ')
                              : timestamp,
                          style: TextStyle(
                            fontSize: 10,
                            color: AppTheme.textH(context),
                          ),
                        ),
                        const Spacer(),
                        GestureDetector(
                          onTap: onAcknowledge,
                          child: Text(
                            'Acknowledge',
                            style: TextStyle(
                              fontSize: 10,
                              color: AppTheme.highlightBlue,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
