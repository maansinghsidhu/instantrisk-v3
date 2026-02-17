import 'dart:convert';
import 'auth_service.dart';

/// PrecedentService - Search for similar historical risks using vector similarity
class PrecedentService {
  /// Search for similar precedent cases given an assessment ID
  Future<List<Map<String, dynamic>>> searchPrecedents({
    required String assessmentId,
    int limit = 5,
  }) async {
    try {
      final response = await authService.get(
        '/assessments/$assessmentId/precedents?limit=$limit',
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return List<Map<String, dynamic>>.from(data['precedents'] ?? []);
      }
    } catch (_) {}
    return [];
  }

  /// Search precedents by free-form query text
  Future<List<Map<String, dynamic>>> searchByQuery({
    required String query,
    String? lob,
    int limit = 5,
  }) async {
    try {
      final params = {
        'q': query,
        if (lob != null) 'lob': lob,
        'limit': '$limit',
      };
      final queryStr = params.entries
          .map((e) => '${Uri.encodeComponent(e.key)}=${Uri.encodeComponent(e.value)}')
          .join('&');
      final response = await authService.get('/precedents/search?$queryStr');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return List<Map<String, dynamic>>.from(data['results'] ?? []);
      }
    } catch (_) {}
    return [];
  }

  /// Get detailed view of a single precedent
  Future<Map<String, dynamic>?> getPrecedentDetail(String precedentId) async {
    try {
      final response = await authService.get('/precedents/$precedentId');
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return null;
  }
}

final precedentService = PrecedentService();
