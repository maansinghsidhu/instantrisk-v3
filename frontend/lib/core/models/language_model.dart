/// Supported Languages Enum - matches backend SupportedLanguage
enum SupportedLanguage {
  english('en'),
  french('fr'),
  german('de'),
  spanish('es'),
  italian('it'),
  portuguese('pt'),
  dutch('nl'),
  arabic('ar'),
  chinese('zh'),
  japanese('ja'),
  korean('ko'),
  hindi('hi');

  final String code;
  const SupportedLanguage(this.code);

  /// Get SupportedLanguage from code string
  static SupportedLanguage fromCode(String code) {
    return SupportedLanguage.values.firstWhere(
      (lang) => lang.code == code,
      orElse: () => SupportedLanguage.english,
    );
  }
}

/// Language information with display data
class LanguageInfo {
  final String code;
  final String name;
  final String nativeName;
  final String flag;
  final bool rtl;

  const LanguageInfo({
    required this.code,
    required this.name,
    required this.nativeName,
    required this.flag,
    this.rtl = false,
  });

  factory LanguageInfo.fromJson(Map<String, dynamic> json) {
    return LanguageInfo(
      code: json['code'] as String,
      name: json['name'] as String,
      nativeName: json['native_name'] as String,
      flag: json['flag'] ?? _getFlagForCode(json['code'] as String),
      rtl: json['rtl'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'code': code,
      'name': name,
      'native_name': nativeName,
      'flag': flag,
      'rtl': rtl,
    };
  }

  static String _getFlagForCode(String code) {
    const flags = {
      'en': 'GB',
      'fr': 'FR',
      'de': 'DE',
      'es': 'ES',
      'it': 'IT',
      'pt': 'PT',
      'nl': 'NL',
      'ar': 'SA',
      'zh': 'CN',
      'ja': 'JP',
      'ko': 'KR',
      'hi': 'IN',
    };
    return flags[code] ?? 'UN';
  }
}

/// All supported languages with their information
const List<LanguageInfo> supportedLanguages = [
  LanguageInfo(
    code: 'en',
    name: 'English',
    nativeName: 'English',
    flag: 'GB',
  ),
  LanguageInfo(
    code: 'fr',
    name: 'French',
    nativeName: 'Francais',
    flag: 'FR',
  ),
  LanguageInfo(
    code: 'de',
    name: 'German',
    nativeName: 'Deutsch',
    flag: 'DE',
  ),
  LanguageInfo(
    code: 'es',
    name: 'Spanish',
    nativeName: 'Espanol',
    flag: 'ES',
  ),
  LanguageInfo(
    code: 'it',
    name: 'Italian',
    nativeName: 'Italiano',
    flag: 'IT',
  ),
  LanguageInfo(
    code: 'pt',
    name: 'Portuguese',
    nativeName: 'Portugues',
    flag: 'PT',
  ),
  LanguageInfo(
    code: 'nl',
    name: 'Dutch',
    nativeName: 'Nederlands',
    flag: 'NL',
  ),
  LanguageInfo(
    code: 'ar',
    name: 'Arabic',
    nativeName: 'Al-Arabiyya',
    flag: 'SA',
    rtl: true,
  ),
  LanguageInfo(
    code: 'zh',
    name: 'Chinese',
    nativeName: 'Zhongwen',
    flag: 'CN',
  ),
  LanguageInfo(
    code: 'ja',
    name: 'Japanese',
    nativeName: 'Nihongo',
    flag: 'JP',
  ),
  LanguageInfo(
    code: 'ko',
    name: 'Korean',
    nativeName: '한국어',
    flag: 'KR',
  ),
  LanguageInfo(
    code: 'hi',
    name: 'Hindi',
    nativeName: 'हिन्दी',
    flag: 'IN',
  ),
];

/// Get LanguageInfo by code
LanguageInfo getLanguageInfo(String code) {
  return supportedLanguages.firstWhere(
    (lang) => lang.code == code,
    orElse: () => supportedLanguages.first,
  );
}
