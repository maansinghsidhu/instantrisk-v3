import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';

/// Active Sessions Screen
/// Shows all logged-in devices and allows revoking sessions
class SessionsScreen extends StatefulWidget {
  const SessionsScreen({super.key});

  @override
  State<SessionsScreen> createState() => _SessionsScreenState();
}

class _SessionsScreenState extends State<SessionsScreen> {
  bool _isLoading = true;
  List<Map<String, dynamic>> _sessions = [];

  @override
  void initState() {
    super.initState();
    _loadSessions();
  }

  Future<void> _loadSessions() async {
    setState(() => _isLoading = true);
    try {
      final result = await authService.getActiveSessions();
      if (result['success'] == true) {
        setState(() {
          _sessions = List<Map<String, dynamic>>.from(result['sessions'] ?? []);
        });
      }
    } catch (e) {
      debugPrint('Error loading sessions: $e');
      // Show mock data for now
      setState(() {
        _sessions = [
          {
            'id': 'current',
            'device': 'This Device',
            'browser': 'Mobile App',
            'location': 'London, UK',
            'last_active': 'Now',
            'is_current': true,
          },
        ];
      });
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _revokeSession(String sessionId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Revoke Session'),
        content: const Text('This will log out this device. Continue?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Revoke', style: TextStyle(color: AppTheme.danger)),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        final result = await authService.revokeSession(sessionId);
        if (result['success'] == true) {
          _loadSessions();
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Session revoked'),
                backgroundColor: AppTheme.success,
              ),
            );
          }
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Failed to revoke session'),
              backgroundColor: AppTheme.danger,
            ),
          );
        }
      }
    }
  }

  Future<void> _revokeAllOther() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Revoke All Sessions'),
        content: const Text(
          'This will log out all other devices. You will remain logged in on this device.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Revoke All', style: TextStyle(color: AppTheme.danger)),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        final result = await authService.revokeAllSessions();
        if (result['success'] == true) {
          _loadSessions();
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('All other sessions revoked'),
                backgroundColor: AppTheme.success,
              ),
            );
          }
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Failed to revoke sessions'),
              backgroundColor: AppTheme.danger,
            ),
          );
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: AppTheme.surface,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppTheme.textPrimary),
          onPressed: () => context.pop(),
        ),
        title: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.devices, color: AppTheme.primaryDark, size: 22),
            SizedBox(width: 8),
            Text(
              'Active Sessions',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
            ),
          ],
        ),
        centerTitle: true,
        actions: [
          if (_sessions.length > 1)
            TextButton(
              onPressed: _revokeAllOther,
              child: const Text(
                'Revoke All',
                style: TextStyle(color: AppTheme.danger),
              ),
            ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadSessions,
              child: _sessions.isEmpty
                  ? _buildEmptyState()
                  : ListView.builder(
                      padding: const EdgeInsets.all(20),
                      itemCount: _sessions.length,
                      itemBuilder: (context, index) {
                        return _buildSessionCard(_sessions[index]);
                      },
                    ),
            ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.devices, size: 64, color: AppTheme.textHint.withOpacity(0.5)),
          const SizedBox(height: 16),
          const Text(
            'No Active Sessions',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'You\'re not logged in on any devices',
            style: TextStyle(color: AppTheme.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _buildSessionCard(Map<String, dynamic> session) {
    final bool isCurrent = session['is_current'] == true;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isCurrent ? AppTheme.primaryDark.withOpacity(0.3) : AppTheme.border,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: isCurrent
                      ? AppTheme.primaryDark.withOpacity(0.1)
                      : AppTheme.textHint.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  _getDeviceIcon(session['device'] ?? ''),
                  color: isCurrent ? AppTheme.primaryDark : AppTheme.textHint,
                  size: 22,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          session['device'] ?? 'Unknown Device',
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                        if (isCurrent) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: AppTheme.success,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              'Current',
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w600,
                                color: Colors.white,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      session['browser'] ?? '',
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              if (!isCurrent)
                IconButton(
                  icon: const Icon(Icons.logout, color: AppTheme.danger),
                  onPressed: () => _revokeSession(session['id']),
                  tooltip: 'Revoke',
                ),
            ],
          ),
          const SizedBox(height: 12),
          const Divider(height: 1),
          const SizedBox(height: 12),
          Row(
            children: [
              _buildDetailItem(Icons.location_on_outlined, session['location'] ?? 'Unknown'),
              const SizedBox(width: 24),
              _buildDetailItem(Icons.access_time, session['last_active'] ?? 'Unknown'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildDetailItem(IconData icon, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: AppTheme.textHint),
        const SizedBox(width: 4),
        Text(
          text,
          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
        ),
      ],
    );
  }

  IconData _getDeviceIcon(String device) {
    final lower = device.toLowerCase();
    if (lower.contains('mobile') || lower.contains('phone') || lower.contains('android') || lower.contains('ios')) {
      return Icons.phone_android;
    } else if (lower.contains('tablet') || lower.contains('ipad')) {
      return Icons.tablet_android;
    } else if (lower.contains('desktop') || lower.contains('windows') || lower.contains('mac')) {
      return Icons.desktop_windows;
    }
    return Icons.devices;
  }
}
