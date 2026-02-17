import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/monitoring_service.dart';

/// BreachAlertBadge - Shows HIBP (Have I Been Pwned) breach count for an entity.
/// Tappable to expand breach details.
class BreachAlertBadge extends StatefulWidget {
  final String assessmentId;
  final VoidCallback? onViewAll;

  const BreachAlertBadge({
    super.key,
    required this.assessmentId,
    this.onViewAll,
  });

  @override
  State<BreachAlertBadge> createState() => _BreachAlertBadgeState();
}

class _BreachAlertBadgeState extends State<BreachAlertBadge> {
  List<Map<String, dynamic>> _breaches = [];
  bool _isLoading = true;
  bool _isExpanded = false;

  @override
  void initState() {
    super.initState();
    _loadBreaches();
  }

  Future<void> _loadBreaches() async {
    final results = await monitoringService.getBreachAlerts(
      assessmentId: widget.assessmentId,
    );
    if (mounted) {
      setState(() {
        _breaches = results;
        _isLoading = false;
      });
    }
  }

  Color get _badgeColor {
    if (_breaches.isEmpty) return AppTheme.success;
    if (_breaches.length >= 3) return AppTheme.danger;
    return AppTheme.warning;
  }

  IconData get _badgeIcon {
    if (_breaches.isEmpty) return Icons.shield_outlined;
    return Icons.warning_amber_rounded;
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: AppTheme.borderLightOf(context),
          borderRadius: BorderRadius.circular(8),
        ),
        child: const SizedBox(
          width: 16,
          height: 16,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Badge button
        InkWell(
          onTap: () => setState(() => _isExpanded = !_isExpanded),
          borderRadius: BorderRadius.circular(8),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: _badgeColor.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: _badgeColor.withOpacity(0.3)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(_badgeIcon, size: 16, color: _badgeColor),
                const SizedBox(width: 6),
                Text(
                  _breaches.isEmpty
                      ? 'No Breaches Found'
                      : '${_breaches.length} Data Breach${_breaches.length > 1 ? 'es' : ''}',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: _badgeColor,
                  ),
                ),
                if (_breaches.isNotEmpty) ...[
                  const SizedBox(width: 6),
                  Icon(
                    _isExpanded ? Icons.expand_less : Icons.expand_more,
                    size: 16,
                    color: _badgeColor,
                  ),
                ],
              ],
            ),
          ),
        ),

        // Expanded details
        if (_isExpanded && _breaches.isNotEmpty)
          Container(
            margin: const EdgeInsets.only(top: 8),
            decoration: BoxDecoration(
              color: AppTheme.surfaceOf(context),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppTheme.borderOf(context)),
            ),
            child: Column(
              children: [
                ...(_breaches.take(5).map((breach) => _BreachItem(breach: breach))),
                if (_breaches.length > 5 && widget.onViewAll != null)
                  InkWell(
                    onTap: widget.onViewAll,
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      child: Center(
                        child: Text(
                          'View all ${_breaches.length} breaches',
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppTheme.highlightBlue,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
      ],
    );
  }
}

class _BreachItem extends StatelessWidget {
  final Map<String, dynamic> breach;

  const _BreachItem({required this.breach});

  @override
  Widget build(BuildContext context) {
    final name = breach['name']?.toString() ?? breach['breach_name']?.toString() ?? 'Unknown Breach';
    final date = breach['date']?.toString() ?? breach['breach_date']?.toString() ?? '';
    final dataTypes = (breach['data_types'] as List?) ?? [];
    final severity = breach['severity']?.toString() ?? 'medium';

    Color severityColor;
    switch (severity.toLowerCase()) {
      case 'critical':
      case 'high':
        severityColor = AppTheme.danger;
        break;
      case 'medium':
        severityColor = AppTheme.warning;
        break;
      default:
        severityColor = AppTheme.info;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 8,
            height: 8,
            margin: const EdgeInsets.only(top: 4),
            decoration: BoxDecoration(
              color: severityColor,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.text1(context),
                  ),
                ),
                if (date.isNotEmpty)
                  Text(
                    date,
                    style: TextStyle(fontSize: 11, color: AppTheme.text2(context)),
                  ),
                if (dataTypes.isNotEmpty)
                  Wrap(
                    spacing: 4,
                    children: dataTypes.take(3).map((dt) {
                      return Chip(
                        label: Text(
                          dt.toString(),
                          style: const TextStyle(fontSize: 9),
                        ),
                        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        padding: EdgeInsets.zero,
                        labelPadding: const EdgeInsets.symmetric(horizontal: 4),
                        visualDensity: VisualDensity.compact,
                      );
                    }).toList(),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
