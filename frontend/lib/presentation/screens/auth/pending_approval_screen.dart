import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/services/auth_service.dart';

/// Screen shown when user's account is pending admin approval
class PendingApprovalScreen extends StatefulWidget {
  const PendingApprovalScreen({super.key});

  @override
  State<PendingApprovalScreen> createState() => _PendingApprovalScreenState();
}

class _PendingApprovalScreenState extends State<PendingApprovalScreen> {
  final AuthService _authService = AuthService();
  bool _isChecking = false;
  String _status = 'pending';
  String? _message;
  String? _rejectionReason;

  @override
  void initState() {
    super.initState();
    _checkStatus();
  }

  Future<void> _checkStatus() async {
    setState(() {
      _isChecking = true;
    });

    try {
      final response = await _authService.get('/approval/status');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _status = data['status'] ?? 'pending';
          _message = data['message'];
          _rejectionReason = data['rejection_reason'];
        });

        // If approved, redirect to home
        if (_status == 'approved' && mounted) {
          context.go('/home');
        }
      }
    } catch (e) {
      debugPrint('Error checking approval status: $e');
    } finally {
      if (mounted) {
        setState(() {
          _isChecking = false;
        });
      }
    }
  }

  Future<void> _logout() async {
    await _authService.logout();
    if (mounted) {
      context.go('/login');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Spacer(),
              _buildStatusIcon(),
              const SizedBox(height: 32),
              _buildStatusTitle(),
              const SizedBox(height: 16),
              _buildStatusMessage(),
              if (_status == 'rejected' && _rejectionReason != null) ...[
                const SizedBox(height: 16),
                _buildRejectionReason(),
              ],
              const Spacer(),
              _buildActions(),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatusIcon() {
    IconData icon;
    Color color;
    Color bgColor;

    switch (_status) {
      case 'approved':
        icon = Icons.check_circle;
        color = Colors.green;
        bgColor = Colors.green.withOpacity(0.1);
        break;
      case 'rejected':
        icon = Icons.cancel;
        color = Colors.red;
        bgColor = Colors.red.withOpacity(0.1);
        break;
      default:
        icon = Icons.hourglass_empty;
        color = Colors.orange;
        bgColor = Colors.orange.withOpacity(0.1);
    }

    return Container(
      width: 120,
      height: 120,
      decoration: BoxDecoration(
        color: bgColor,
        shape: BoxShape.circle,
      ),
      child: Icon(
        icon,
        size: 64,
        color: color,
      ),
    );
  }

  Widget _buildStatusTitle() {
    String title;
    switch (_status) {
      case 'approved':
        title = 'Account Approved!';
        break;
      case 'rejected':
        title = 'Account Rejected';
        break;
      default:
        title = 'Account Pending Approval';
    }

    return Text(
      title,
      style: const TextStyle(
        fontSize: 28,
        fontWeight: FontWeight.bold,
      ),
      textAlign: TextAlign.center,
    );
  }

  Widget _buildStatusMessage() {
    String message;
    switch (_status) {
      case 'approved':
        message = 'Your account has been approved. You can now access the platform.';
        break;
      case 'rejected':
        message = 'Unfortunately, your account registration was rejected.';
        break;
      default:
        message = 'Your registration is being reviewed by an administrator.\n\nYou will be notified once your account is approved.';
    }

    return Text(
      _message ?? message,
      style: TextStyle(
        fontSize: 16,
        color: Colors.grey[600],
        height: 1.5,
      ),
      textAlign: TextAlign.center,
    );
  }

  Widget _buildRejectionReason() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.red.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.red.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.info_outline, color: Colors.red, size: 20),
              SizedBox(width: 8),
              Text(
                'Reason',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  color: Colors.red,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            _rejectionReason!,
            style: TextStyle(color: Colors.grey[700]),
          ),
        ],
      ),
    );
  }

  Widget _buildActions() {
    return Column(
      children: [
        if (_status == 'pending') ...[
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _isChecking ? null : _checkStatus,
              icon: _isChecking
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                      ),
                    )
                  : const Icon(Icons.refresh),
              label: Text(_isChecking ? 'Checking...' : 'Check Status'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
        ],
        if (_status == 'approved')
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: () => context.go('/home'),
              icon: const Icon(Icons.arrow_forward),
              label: const Text('Continue to Dashboard'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
                backgroundColor: Colors.green,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ),
        if (_status == 'rejected')
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: () {
                // Open email client or support page
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Please contact support@instantrisk.io for assistance'),
                  ),
                );
              },
              icon: const Icon(Icons.email),
              label: const Text('Contact Support'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ),
        const SizedBox(height: 12),
        TextButton(
          onPressed: _logout,
          child: const Text('Sign Out'),
        ),
      ],
    );
  }
}
