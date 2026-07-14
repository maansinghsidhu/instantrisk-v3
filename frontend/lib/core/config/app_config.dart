/// InstantRisk V5 - Application Configuration
class AppConfig {
  // App Info
  static const String appName = 'InstantRisk';
  static const String appVersion = '5.0.0';
  static const String appTagline = 'Enterprise-grade risk analysis with AI-powered underwriting.';

  // API Configuration
  static const String apiBaseUrl = '/api/v1';
  static const String wsBaseUrl = '';

  // Download URLs
  static const String androidApkUrl = 'https://ir.alexandratechlab.com/downloads/instantrisk-v2.apk';
  static const String playStoreUrl = 'https://play.google.com/store/apps/details?id=com.alexandratechlab.instantrisk';
  static const String appStoreUrl = 'https://apps.apple.com/app/instantrisk/id6474538219';
  static const String webAppUrl = 'https://ir.alexandratechlab.com';

  // Support URLs
  static const String supportEmail = 'support@alexandratechlab.com';
  static const String docsUrl = 'https://ir.alexandratechlab.com/docs';
  static const String feedbackUrl = 'https://ir.alexandratechlab.com/feedback';

  // Subscription Tiers
  static const Map<String, Map<String, dynamic>> subscriptionTiers = {
    'standard': {
      'name': 'Standard',
      'price': 500,
      'currency': 'GBP',
      'queries': 100,
      'features': ['GO/NO-GO', 'Analysis', 'Advice', 'Pricing'],
    },
    'standard_plus': {
      'name': 'Standard+',
      'price': 600,
      'currency': 'GBP',
      'queries': 500,
      'features': ['GO/NO-GO', 'Analysis', 'Advice', 'Pricing', 'AI Chat', 'Fine-tuning'],
    },
    'premium': {
      'name': 'Premium',
      'price': 700,
      'currency': 'GBP',
      'queries': 2000,
      'features': ['GO/NO-GO', 'Analysis', 'Advice', 'Pricing', 'AI Chat', 'Fine-tuning', 'Contract Generation', 'Lloyd\'s Submission'],
    },
    'enterprise': {
      'name': 'Enterprise',
      'price': -1, // Custom
      'currency': 'GBP',
      'queries': -1, // Unlimited
      'features': ['All Features', 'Custom ML Training', 'White-label', 'Dedicated Support'],
    },
  };

  // Supported Languages
  static const List<Map<String, String>> supportedLanguages = [
    {'code': 'en', 'name': 'English', 'flag': '🇬🇧'},
    {'code': 'fr', 'name': 'Français', 'flag': '🇫🇷'},
    {'code': 'de', 'name': 'Deutsch', 'flag': '🇩🇪'},
    {'code': 'es', 'name': 'Español', 'flag': '🇪🇸'},
    {'code': 'ar', 'name': 'العربية', 'flag': '🇸🇦'},
    {'code': 'zh', 'name': '中文', 'flag': '🇨🇳'},
    {'code': 'ja', 'name': '日本語', 'flag': '🇯🇵'},
    {'code': 'ko', 'name': '한국어', 'flag': '🇰🇷'},
  ];

  // Document Types
  static const List<String> supportedDocumentTypes = [
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/heic',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  ];

  // Max File Size (10MB per file for security)
  static const int maxFileSizeBytes = 10 * 1024 * 1024;

  // Timeouts
  static const int apiTimeoutSeconds = 30;
  static const int uploadTimeoutSeconds = 120;
  static const int processingTimeoutSeconds = 180;
}
