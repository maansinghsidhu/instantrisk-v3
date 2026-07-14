import 'package:flutter/material.dart';

/// InstantRisk Theme - Corporate Modern Design.
class AppTheme {
  // Font fallback for missing characters
  static const List<String> fontFallback = ['Roboto', 'sans-serif'];

  // Brand Colors
  static const Color primaryDark = Color(0xFF1E3A5F);    // Navy blue
  static const Color primaryLight = Color(0xFF2D5A87);
  static const Color accent = Color(0xFF00B894);         // Teal green (GO)
  static const Color accentSecondary = Color(0xFF00CEC9);

  // Status Colors
  static const Color success = Color(0xFF00B894);
  static const Color successLight = Color(0xFFE8F8F5);
  static const Color danger = Color(0xFFE74C3C);          // NO-GO
  static const Color error = Color(0xFFE74C3C);
  static const Color errorLight = Color(0xFFFDEDED);
  static const Color warning = Color(0xFFF39C12);         // REFER
  static const Color warningLight = Color(0xFFFEF5E7);
  static const Color info = Color(0xFF3498DB);
  static const Color infoLight = Color(0xFFEBF5FB);

  // Aliases
  static const Color primary = primaryDark;
  static const Color secondary = accent;

  // Neutral (light defaults)
  static const Color background = Color(0xFFF8F9FA);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color textPrimary = Color(0xFF2C3E50);
  static const Color textSecondary = Color(0xFF7F8C8D);
  static const Color textHint = Color(0xFFBDC3C7);
  static const Color border = Color(0xFFE0E6ED);

  // Analysis palette (used by entity/analysis widgets)
  static const Color analysisPurple = Color(0xFF8B5CF6);
  static const Color analysisIndigo = Color(0xFF6366F1);
  static const Color analysisCyan = Color(0xFF06B6D4);
  static const Color analysisClassifier = Color(0xFF8B5CF6);

  // ----- Context-aware helpers -----
  static bool isDark(BuildContext c) =>
      Theme.of(c).brightness == Brightness.dark;

  static Color bg(BuildContext c) =>
      isDark(c) ? const Color(0xFF0B1220) : background;

  static Color surfaceOf(BuildContext c) =>
      isDark(c) ? const Color(0xFF131A2C) : surface;

  static Color borderOf(BuildContext c) =>
      isDark(c) ? const Color(0xFF2A3450) : border;

  static Color text1(BuildContext c) =>
      isDark(c) ? const Color(0xFFE8ECF4) : textPrimary;

  static Color text2(BuildContext c) =>
      isDark(c) ? const Color(0xFF8A93A8) : textSecondary;

  static Color textH(BuildContext c) => text1(c);

  static List<BoxShadow> subtleShadow(BuildContext c) => [
        BoxShadow(
          color: Colors.black.withOpacity(isDark(c) ? 0.45 : 0.08),
          blurRadius: 12,
          offset: const Offset(0, 4),
        ),
      ];

  static CardThemeData cardTheme(BuildContext c) => CardThemeData(
        color: surfaceOf(c),
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
          side: BorderSide(color: borderOf(c), width: 1),
        ),
      );

  // ----- Light theme -----
  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      primaryColor: primaryDark,
      scaffoldBackgroundColor: background,
      colorScheme: const ColorScheme.light(
        primary: primaryDark,
        secondary: accent,
        surface: surface,
        error: danger,
        onPrimary: Colors.white,
        onSecondary: Colors.white,
        onSurface: textPrimary,
        onError: Colors.white,
      ),
      // Keep the rest minimal — full theme shape is out of scope for this
      // cutover.  Dark mode uses Material 3 default behaviour.
    );
  }

  // ----- Dark theme (kept consistent with light defaults) -----
  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      primaryColor: primaryDark,
      scaffoldBackgroundColor: const Color(0xFF0B1220),
      colorScheme: const ColorScheme.dark(
        primary: primaryDark,
        secondary: accent,
        surface: Color(0xFF131A2C),
        error: danger,
        onPrimary: Colors.white,
        onSecondary: Colors.white,
        onSurface: Color(0xFFE8ECF4),
        onError: Colors.white,
      ),
    );
  }

  static Color borderLightOf(BuildContext c) =>
      isDark(c) ? const Color(0xFF1F2A40) : const Color(0xFFEEF2F6);

  static Color cardAltOf(BuildContext c) =>
      isDark(c) ? const Color(0xFF1A2238) : const Color(0xFFFFFFFF);

  // Direct-Color getters (used as `AppTheme.darkBg` without parens)
  static const Color darkBg = Color(0xFF0B1220);
  static const Color highlightBlue = Color(0xFF3B82F6);
  static const Color surfaceVariant = Color(0xFFEEF2F6);
}
