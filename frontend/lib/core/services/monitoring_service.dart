import 'dart:convert';
import 'auth_service.dart';

/// MonitoringService - 24/7 risk monitoring, HIBP breach alerts, news alerts
class MonitoringService {
  /// Get all active alerts for the current user's portfolio
  Future<List<Map<String, dynamic>>> getAlerts({
    String? severity,
    int limit = 50,
  }) async {
    try {
      final params = <String, String>{
        'limit': '$limit',
        if (severity != null) 'severity': severity,
      };
      final queryStr = params.entries
          .map((e) => '${Uri.encodeComponent(e.key)}=${Uri.encodeComponent(e.value)}')
          .join('&');
      final response = await authService.get('/monitoring/alerts?$queryStr');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return List<Map<String, dynamic>>.from(data['alerts'] ?? []);
      }
    } catch (_) {}
    return [];
  }

  /// Get HIBP (Have I Been Pwned) breach alerts for a specific entity
  Future<List<Map<String, dynamic>>> getBreachAlerts({
    required String assessmentId,
  }) async {
    try {
      final response = await authService.get(
        '/assessments/$assessmentId/breach-alerts',
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return List<Map<String, dynamic>>.from(data['breaches'] ?? []);
      }
    } catch (_) {}
    return [];
  }

  /// Get monitoring dashboard summary (counts by severity)
  Future<Map<String, dynamic>> getDashboardSummary() async {
    try {
      final response = await authService.get('/monitoring/dashboard');
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return {
      'critical': 0,
      'high': 0,
      'medium': 0,
      'low': 0,
      'total': 0,
      'last_updated': null,
    };
  }

  /// Get news monitoring alerts (external news about insured entities)
  Future<List<Map<String, dynamic>>> getNewsAlerts({
    String? assessmentId,
    int limit = 20,
  }) async {
    try {
      final params = <String, String>{
        'limit': '$limit',
        if (assessmentId != null) 'assessment_id': assessmentId,
      };
      final queryStr = params.entries
          .map((e) => '${Uri.encodeComponent(e.key)}=${Uri.encodeComponent(e.value)}')
          .join('&');
      final response = await authService.get('/monitoring/news?$queryStr');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return List<Map<String, dynamic>>.from(data['articles'] ?? []);
      }
    } catch (_) {}
    return [];
  }

  /// Mark an alert as acknowledged
  Future<bool> acknowledgeAlert(String alertId) async {
    try {
      final response = await authService.post(
        '/monitoring/alerts/$alertId/acknowledge',
      );
      return response.statusCode == 200;
    } catch (_) {}
    return false;
  }
}

final monitoringService = MonitoringService();
