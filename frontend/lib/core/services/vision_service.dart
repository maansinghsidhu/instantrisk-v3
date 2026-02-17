import 'dart:convert';
import 'auth_service.dart';

/// VisionService - Computer vision analysis for property images and documents
class VisionService {
  /// Get vision analysis results for an assessment (property images, OCR)
  Future<Map<String, dynamic>?> getVisionAnalysis(String assessmentId) async {
    try {
      final response = await authService.get(
        '/assessments/$assessmentId/vision',
      );
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return null;
  }

  /// Get OCR confidence scores for documents in an assessment
  Future<List<Map<String, dynamic>>> getOcrResults(String assessmentId) async {
    try {
      final response = await authService.get(
        '/assessments/$assessmentId/ocr-results',
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return List<Map<String, dynamic>>.from(data['results'] ?? []);
      }
    } catch (_) {}
    return [];
  }

  /// Get property risk detections from images (flood zone, roof condition, etc.)
  Future<List<Map<String, dynamic>>> getPropertyRisks(
      String assessmentId) async {
    try {
      final response = await authService.get(
        '/assessments/$assessmentId/property-risks',
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return List<Map<String, dynamic>>.from(data['risks'] ?? []);
      }
    } catch (_) {}
    return [];
  }

  /// Trigger vision re-analysis for a given assessment
  Future<bool> triggerAnalysis(String assessmentId) async {
    try {
      final response = await authService.post(
        '/assessments/$assessmentId/vision/analyze',
      );
      return response.statusCode == 200 || response.statusCode == 202;
    } catch (_) {}
    return false;
  }
}

final visionService = VisionService();
