import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'auth_service.dart';

/// Subscription tiers available in the system
enum SubscriptionTier {
  trial,
  basic,
  premium,
}

/// Extension to parse tier from string
extension SubscriptionTierExtension on SubscriptionTier {
  String get value {
    switch (this) {
      case SubscriptionTier.trial:
        return 'trial';
      case SubscriptionTier.basic:
        return 'basic';
      case SubscriptionTier.premium:
        return 'premium';
    }
  }

  static SubscriptionTier fromString(String? value) {
    switch (value?.toLowerCase()) {
      case 'premium':
        return SubscriptionTier.premium;
      case 'basic':
        return SubscriptionTier.basic;
      case 'trial':
      default:
        return SubscriptionTier.trial;
    }
  }
}

/// Feature configuration for display
class FeatureInfo {
  final String name;
  final String description;
  final String icon;
  final bool hasAccess;

  FeatureInfo({
    required this.name,
    required this.description,
    required this.icon,
    required this.hasAccess,
  });

  factory FeatureInfo.fromJson(Map<String, dynamic> json) {
    return FeatureInfo(
      name: json['name'] ?? '',
      description: json['description'] ?? '',
      icon: json['icon'] ?? '',
      hasAccess: json['has_access'] ?? false,
    );
  }
}

/// Subscription service for managing user subscription state
class SubscriptionService {
  static final SubscriptionService _instance = SubscriptionService._internal();
  factory SubscriptionService() => _instance;
  SubscriptionService._internal();

  final AuthService _authService = AuthService();
  Box? _subscriptionBox;

  // Subscription state
  SubscriptionTier _currentTier = SubscriptionTier.trial;
  String _status = 'pending';
  Map<String, dynamic>? _limits;
  Map<String, dynamic>? _usage;
  Map<String, FeatureInfo>? _features;
  List<String>? _allowedAnalysisModes;
  DateTime? _expiresAt;

  // Getters
  SubscriptionTier get currentTier => _currentTier;
  String get status => _status;
  bool get isActive => _status == 'active';
  bool get isPremium => _currentTier == SubscriptionTier.premium;
  bool get isBasic => _currentTier == SubscriptionTier.basic;
  bool get isTrial => _currentTier == SubscriptionTier.trial;
  DateTime? get expiresAt => _expiresAt;

  /// Initialize the subscription service
  Future<void> init() async {
    try {
      _subscriptionBox = await Hive.openBox('subscription');
      await _loadFromCache();
    } catch (e) {
      debugPrint('Error initializing subscription service: $e');
    }
  }

  /// Load subscription from backend
  Future<void> loadSubscription() async {
    if (!_authService.isLoggedIn) return;

    try {
      final response = await _authService.get('/subscription');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _currentTier = SubscriptionTierExtension.fromString(data['tier']);
        _status = data['status'] ?? 'pending';
        _expiresAt = data['expires_at'] != null
            ? DateTime.tryParse(data['expires_at'])
            : null;
        await _saveToCache();
      }
    } catch (e) {
      debugPrint('Error loading subscription: $e');
    }
  }

  /// Load subscription limits and usage
  Future<void> loadLimits() async {
    if (!_authService.isLoggedIn) return;

    try {
      final response = await _authService.get('/subscription/limits');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _limits = data['limits'] as Map<String, dynamic>?;
        _usage = data['usage'] as Map<String, dynamic>?;
      }
    } catch (e) {
      debugPrint('Error loading subscription limits: $e');
    }
  }

  /// Load all features and their access status
  Future<void> loadFeatures() async {
    if (!_authService.isLoggedIn) return;

    try {
      final response = await _authService.get('/subscription/features');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _currentTier = SubscriptionTierExtension.fromString(data['tier']);
        _allowedAnalysisModes = List<String>.from(data['analysis_modes'] ?? []);

        final featuresData = data['features'] as Map<String, dynamic>?;
        if (featuresData != null) {
          _features = {};
          featuresData.forEach((key, value) {
            _features![key] = FeatureInfo.fromJson(value as Map<String, dynamic>);
          });
        }
      }
    } catch (e) {
      debugPrint('Error loading features: $e');
    }
  }

  /// Check if user has access to a specific feature
  bool hasFeature(String featureName) {
    // Premium users have all features
    if (_currentTier == SubscriptionTier.premium) {
      return true;
    }

    // Check from cached features
    if (_features != null && _features!.containsKey(featureName)) {
      return _features![featureName]!.hasAccess;
    }

    // Default feature access by tier
    final basicFeatures = [
      'go_no_go_decision',
      'risk_analysis',
      'underwriting_percentage',
      'premium_price',
      'quick_analysis',
      'go_no_go_analysis',
      'shareable_link',
    ];

    if (_currentTier == SubscriptionTier.basic) {
      return basicFeatures.contains(featureName);
    }

    // Trial has limited features - can see Go/No-Go decision only
    final trialFeatures = [
      'quick_analysis',
      'shareable_link',
      'go_no_go_decision', // Trial can see basic Go/No-Go, but not detailed rationale
    ];
    return trialFeatures.contains(featureName);
  }

  /// Check if user can use a specific analysis mode
  bool canUseAnalysisMode(String mode) {
    if (_allowedAnalysisModes != null) {
      return _allowedAnalysisModes!.contains(mode);
    }

    // Default modes by tier
    switch (_currentTier) {
      case SubscriptionTier.premium:
        return ['quick', 'go_no_go', 'deep'].contains(mode);
      case SubscriptionTier.basic:
        return ['quick', 'go_no_go'].contains(mode);
      case SubscriptionTier.trial:
        return ['quick'].contains(mode);
    }
  }

  /// Get remaining usage for a resource type
  int getRemainingUsage(String usageType) {
    if (_limits == null || _usage == null) return 0;

    final limit = _limits!['monthly_$usageType'] ?? 0;
    final used = _usage!['monthly_$usageType'] ?? 0;
    return (limit - used).clamp(0, limit);
  }

  /// Check if user is within usage limit
  bool isWithinLimit(String usageType) {
    return getRemainingUsage(usageType) > 0;
  }

  /// Get feature info for display
  FeatureInfo? getFeatureInfo(String featureName) {
    return _features?[featureName];
  }

  /// Get tier display name
  String getTierDisplayName() {
    switch (_currentTier) {
      case SubscriptionTier.premium:
        return 'Premium';
      case SubscriptionTier.basic:
        return 'Basic';
      case SubscriptionTier.trial:
        return 'Trial';
    }
  }

  /// Request subscription upgrade
  Future<Map<String, dynamic>?> requestUpgrade(String targetTier) async {
    try {
      final response = await _authService.post(
        '/subscription/upgrade',
        body: {'target_tier': targetTier},
      );
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
    } catch (e) {
      debugPrint('Error requesting upgrade: $e');
    }
    return null;
  }

  /// Save subscription data to local cache
  Future<void> _saveToCache() async {
    if (_subscriptionBox == null) return;
    await _subscriptionBox!.put('tier', _currentTier.value);
    await _subscriptionBox!.put('status', _status);
    if (_expiresAt != null) {
      await _subscriptionBox!.put('expiresAt', _expiresAt!.toIso8601String());
    }
  }

  /// Load subscription data from local cache
  Future<void> _loadFromCache() async {
    if (_subscriptionBox == null) return;
    final tierStr = _subscriptionBox!.get('tier');
    if (tierStr != null) {
      _currentTier = SubscriptionTierExtension.fromString(tierStr);
    }
    _status = _subscriptionBox!.get('status') ?? 'pending';
    final expiresAtStr = _subscriptionBox!.get('expiresAt');
    if (expiresAtStr != null) {
      _expiresAt = DateTime.tryParse(expiresAtStr);
    }
  }

  /// Clear subscription cache (on logout)
  Future<void> clear() async {
    _currentTier = SubscriptionTier.trial;
    _status = 'pending';
    _limits = null;
    _usage = null;
    _features = null;
    _allowedAnalysisModes = null;
    _expiresAt = null;
    if (_subscriptionBox != null) {
      await _subscriptionBox!.clear();
    }
  }
}

/// Global singleton instance
final subscriptionService = SubscriptionService();
