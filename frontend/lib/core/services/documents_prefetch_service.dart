import 'dart:convert';
import 'dart:async';
import 'package:flutter/foundation.dart';
import 'auth_service.dart';

/// Documents Prefetch Service
/// Pre-loads documents data in the background for instant display when user
/// navigates to the Documents tab.
class DocumentsPrefetchService {
  static final DocumentsPrefetchService _instance = DocumentsPrefetchService._internal();
  factory DocumentsPrefetchService() => _instance;
  DocumentsPrefetchService._internal();

  // Cached data
  List<Map<String, dynamic>> _recentDocuments = [];
  List<Map<String, dynamic>> _assessments = [];
  DateTime? _lastFetchTime;

  // Loading state
  bool _isLoading = false;
  bool _hasFetched = false;

  // Cache duration
  static const Duration _cacheDuration = Duration(minutes: 5);

  // Getters
  List<Map<String, dynamic>> get recentDocuments => _recentDocuments;
  List<Map<String, dynamic>> get assessments => _assessments;
  bool get isLoading => _isLoading;
  bool get hasCachedData => _hasFetched && _recentDocuments.isNotEmpty;
  bool get isCacheValid =>
      _lastFetchTime != null &&
      DateTime.now().difference(_lastFetchTime!) < _cacheDuration;

  /// Pre-fetch documents data in the background
  /// Call this after successful authentication
  Future<void> prefetch() async {
    if (_isLoading) return;

    _isLoading = true;

    try {
      debugPrint('[DocumentsPrefetch] Starting prefetch...');

      // Load recent generated documents
      final docsResponse = await authService.get('/generated-documents/?page_size=10');
      if (docsResponse.statusCode == 200) {
        final data = jsonDecode(docsResponse.body);
        _recentDocuments = List<Map<String, dynamic>>.from(data['items'] ?? []);
        debugPrint('[DocumentsPrefetch] Loaded ${_recentDocuments.length} recent documents');
      }

      // Load assessments
      final assessResponse = await authService.get('/assessments/?page_size=20');
      if (assessResponse.statusCode == 200) {
        final data = jsonDecode(assessResponse.body);
        _assessments = List<Map<String, dynamic>>.from(data['items'] ?? []);

        // Load document counts for each assessment (in parallel for speed)
        await Future.wait(_assessments.map((assessment) async {
          final assessmentId = assessment['id'];
          try {
            // Load uploaded documents count
            final uploadedRes =
                await authService.get('/assessments/$assessmentId/documents');
            if (uploadedRes.statusCode == 200) {
              final uploadedData = jsonDecode(uploadedRes.body);
              assessment['uploaded_count'] =
                  (uploadedData['items'] as List?)?.length ?? 0;
              assessment['uploaded_docs'] = uploadedData['items'] ?? [];
            }
          } catch (_) {
            assessment['uploaded_count'] = 0;
            assessment['uploaded_docs'] = [];
          }

          try {
            // Load generated documents count
            final generatedRes =
                await authService.get('/assessments/$assessmentId/generated');
            if (generatedRes.statusCode == 200) {
              final generatedData = jsonDecode(generatedRes.body);
              assessment['generated_count'] =
                  (generatedData['items'] as List?)?.length ?? 0;
              assessment['generated_docs'] = generatedData['items'] ?? [];
            }
          } catch (_) {
            assessment['generated_count'] = 0;
            assessment['generated_docs'] = [];
          }
        }));

        debugPrint('[DocumentsPrefetch] Loaded ${_assessments.length} assessments');
      }

      _lastFetchTime = DateTime.now();
      _hasFetched = true;
      debugPrint('[DocumentsPrefetch] Prefetch complete');
    } catch (e) {
      debugPrint('[DocumentsPrefetch] Error: $e');
    } finally {
      _isLoading = false;
    }
  }

  /// Refresh data in background
  Future<void> refresh() async {
    await prefetch();
  }

  /// Clear cache (call on logout)
  void clearCache() {
    _recentDocuments = [];
    _assessments = [];
    _lastFetchTime = null;
    _hasFetched = false;
    debugPrint('[DocumentsPrefetch] Cache cleared');
  }

  /// Check if should prefetch
  bool get shouldPrefetch => !_hasFetched || !isCacheValid;
}

// Global singleton instance
final documentsPrefetchService = DocumentsPrefetchService();
