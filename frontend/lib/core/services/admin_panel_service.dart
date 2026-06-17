import 'dart:convert';
import 'package:http/http.dart' as http;
import 'auth_service.dart';

/// Client for the InstantRisk admin panel API
/// (mounted at `/api/v1/admin/panel/*`).
///
/// All methods require an admin-role JWT. Non-admin calls will return 403
/// from the backend. Errors are surfaced as [AdminPanelException] with the
/// HTTP status code and parsed error detail.
class AdminPanelException implements Exception {
  final int statusCode;
  final String message;
  AdminPanelException(this.statusCode, this.message);

  @override
  String toString() => 'AdminPanelException($statusCode): $message';
}

class AdminPanelService {
  static final AdminPanelService _instance = AdminPanelService._internal();
  factory AdminPanelService() => _instance;
  AdminPanelService._internal();

  final AuthService _auth = AuthService();

  Map<String, dynamic> _decode(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) return <String, dynamic>{};
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    String detail = 'Request failed';
    try {
      final parsed = jsonDecode(response.body);
      if (parsed is Map && parsed['detail'] != null) {
        detail = parsed['detail'].toString();
      }
    } catch (_) {}
    throw AdminPanelException(response.statusCode, detail);
  }

  // ===========================================================================
  // Stats
  // ===========================================================================

  Future<Map<String, dynamic>> getStats() async {
    final r = await _auth.get('/admin/panel/stats');
    return _decode(r);
  }

  // ===========================================================================
  // Users
  // ===========================================================================

  Future<Map<String, dynamic>> listUsers({
    String? statusFilter,
    String? role,
    String? tier,
    String? search,
    int limit = 50,
    int offset = 0,
  }) async {
    final params = <String, String>{};
    if (statusFilter != null) params['status_filter'] = statusFilter;
    if (role != null) params['role'] = role;
    if (tier != null) params['tier'] = tier;
    if (search != null && search.isNotEmpty) params['search'] = search;
    params['limit'] = limit.toString();
    params['offset'] = offset.toString();

    final qs = params.entries
        .map((e) => '${e.key}=${Uri.encodeQueryComponent(e.value)}')
        .join('&');
    final r = await _auth.get('/admin/panel/users?$qs');
    return _decode(r);
  }

  Future<Map<String, dynamic>> getUserDetail(String userId) async {
    final r = await _auth.get('/admin/panel/users/$userId');
    return _decode(r);
  }

  Future<Map<String, dynamic>> approveUser(
    String userId, {
    required String subscriptionTier,
    String? notes,
  }) async {
    final r = await _auth.post(
      '/admin/panel/users/$userId/approve',
      body: {
        'subscription_tier': subscriptionTier,
        if (notes != null) 'notes': notes,
      },
    );
    return _decode(r);
  }

  Future<Map<String, dynamic>> rejectUser(
    String userId, {
    required String reason,
  }) async {
    final r = await _auth.post(
      '/admin/panel/users/$userId/reject',
      body: {'reason': reason},
    );
    return _decode(r);
  }

  Future<Map<String, dynamic>> changeTier(
    String userId, {
    required String subscriptionTier,
    String? reason,
  }) async {
    final r = await _auth.post(
      '/admin/panel/users/$userId/tier',
      body: {
        'subscription_tier': subscriptionTier,
        if (reason != null) 'reason': reason,
      },
    );
    return _decode(r);
  }

  Future<Map<String, dynamic>> deactivateUser(
    String userId, {
    String? reason,
  }) async {
    final r = await _auth.post(
      '/admin/panel/users/$userId/deactivate',
      body: {if (reason != null) 'reason': reason},
    );
    return _decode(r);
  }

  Future<Map<String, dynamic>> reactivateUser(String userId) async {
    final r = await _auth.post(
      '/admin/panel/users/$userId/reactivate',
      body: const {},
    );
    return _decode(r);
  }

  // ===========================================================================
  // Usage
  // ===========================================================================

  Future<Map<String, dynamic>> getUserUsage(String userId) async {
    final r = await _auth.get('/admin/panel/users/$userId/usage');
    return _decode(r);
  }

  // ===========================================================================
  // Billing
  // ===========================================================================

  Future<Map<String, dynamic>> getBillingSummary() async {
    final r = await _auth.get('/admin/panel/billing/summary');
    return _decode(r);
  }

  // ===========================================================================
  // Audit log
  // ===========================================================================

  Future<Map<String, dynamic>> listAuditLog({
    String? action,
    String? adminId,
    String? targetUserId,
    DateTime? since,
    int limit = 100,
    int offset = 0,
  }) async {
    final params = <String, String>{};
    if (action != null) params['action'] = action;
    if (adminId != null) params['admin_id'] = adminId;
    if (targetUserId != null) params['target_user_id'] = targetUserId;
    if (since != null) params['since'] = since.toUtc().toIso8601String();
    params['limit'] = limit.toString();
    params['offset'] = offset.toString();

    final qs = params.entries
        .map((e) => '${e.key}=${Uri.encodeQueryComponent(e.value)}')
        .join('&');
    final r = await _auth.get('/admin/panel/audit-log?$qs');
    return _decode(r);
  }
}
