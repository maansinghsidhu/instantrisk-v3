import 'package:flutter/material.dart';

/// InstantRisk V2 Theme - Sleek Modern Corporate Design
class AppTheme {
  // Font fallback for missing characters
  static const List<String> fontFallback = ['Roboto', 'sans-serif'];

  // Brand Colors - Refined
  static const Color primaryDark = Color(0xFF6B00CC);  // Brand purple
  static const Color primaryLight = Color(0xFF8A2BE2);
  static const Color accent = Color(0xFFFF0080);  // Hot pink accent
  static const Color accentSecondary = Color(0xFFFF0080);

  // Status Colors
  static const Color success = Color(0xFF00B894);
  static const Color successLight = Color(0xFFF0FDF8);
  static const Color danger = Color(0xFFE74C3C);
  static const Color error = Color(0xFFE74C3C);
  static const Color errorLight = Color(0xFFFEF2F2);
  static const Color warning = Color(0xFFF39C12);
  static const Color warningLight = Color(0xFFFFFBEB);
  static const Color info = Color(0xFF3498DB);
  static const Color infoLight = Color(0xFFF0F9FF);

  // Alias
  static const Color primary = primaryDark;
  static const Color secondary = accent;

  // Neutral Colors - Refined for sleek look
  static const Color background = Color(0xFFF9FAFB);  // Slightly cooler
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surfaceVariant = Color(0xFFF3F4F6);  // For subtle bg
  static const Color textPrimary = Color(0xFF111827);  // Darker, crisper
  static const Color textSecondary = Color(0xFF6B7280);  // Softer gray
  static const Color textHint = Color(0xFF9CA3AF);
  static const Color border = Color(0xFFE5E7EB);  // Softer border
  static const Color borderLight = Color(0xFFF3F4F6);  // Very subtle border

  // Dark UI Colors
  static const Color darkBg = Color(0xFF111111);  // True dark - like ChatGPT
  static const Color darkSurface = Color(0xFF1A1A1A);  // Slightly lighter
  static const Color darkCard = Color(0xFF212121);
  static const Color darkCardAlt = Color(0xFF171717);
  static const Color darkBorder = Color(0xFF2D2D2D);  // Subtle dark border

  // Extended Brand
  static const Color corporateBlue = Color(0xFF1B4965);
  static const Color corporateBlueLight = Color(0xFF5FA8D3);
  static const Color highlightBlue = Color(0xFF0984E3);
  static const Color accentBright = Color(0xFF8B00FF);

  // Status Dark Variants
  static const Color successDark = Color(0xFF059669);
  static const Color warningAmber = Color(0xFFF59E0B);
  static const Color dangerDark = Color(0xFFDC2626);
  static const Color errorRed = Color(0xFFEF4444);

  // Pipeline Phase Colors
  static const Color phaseResearch = Color(0xFF3B82F6);
  static const Color phaseStructure = Color(0xFF8B5CF6);
  static const Color phaseCompose = Color(0xFF10B981);
  static const Color phaseValidate = Color(0xFFF59E0B);
  static const Color phaseRefine = Color(0xFFEC4899);
  static const Color phaseExport = Color(0xFF6366F1);

  // Analysis Type Colors
  static const Color analysisClassifier = Color(0xFF2563EB);
  static const Color analysisExtractor = Color(0xFF059669);
  static const Color analysisRisk = Color(0xFFDC2626);
  static const Color analysisPurple = Color(0xFF7C3AED);
  static const Color analysisCyan = Color(0xFF0891B2);
  static const Color analysisIndigo = Color(0xFF4F46E5);

  // LOB Category Colors
  static const List<Color> lobColors = [
    Color(0xFF00ACC1),
    Color(0xFF1E88E5),
    Color(0xFF7C4DFF),
    Color(0xFFFF7043),
    Color(0xFF26A69A),
    Color(0xFF5C6BC0),
    Color(0xFFFFA726),
    Color(0xFFAB47BC),
    Color(0xFFEC407A),
  ];

  // Modern shadows
  static List<BoxShadow> get subtleShadow => [
    BoxShadow(
      color: Colors.black.withOpacity(0.04),
      blurRadius: 6,
      offset: const Offset(0, 1),
    ),
    BoxShadow(
      color: Colors.black.withOpacity(0.02),
      blurRadius: 15,
      offset: const Offset(0, 4),
    ),
  ];

  static List<BoxShadow> get cardShadow => [
    BoxShadow(
      color: Colors.black.withOpacity(0.05),
      blurRadius: 10,
      offset: const Offset(0, 2),
    ),
    BoxShadow(
      color: Colors.black.withOpacity(0.03),
      blurRadius: 24,
      offset: const Offset(0, 8),
    ),
  ];

  static List<BoxShadow> get elevatedShadow => [
    BoxShadow(
      color: Colors.black.withOpacity(0.08),
      blurRadius: 16,
      offset: const Offset(0, 4),
    ),
    BoxShadow(
      color: Colors.black.withOpacity(0.04),
      blurRadius: 40,
      offset: const Offset(0, 12),
    ),
  ];

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

      appBarTheme: const AppBarTheme(
        elevation: 0,
        centerTitle: false,
        backgroundColor: surface,
        foregroundColor: textPrimary,
        surfaceTintColor: Colors.transparent,
        iconTheme: IconThemeData(color: textPrimary),
        titleTextStyle: TextStyle(
          fontFamily: 'Inter',
          fontSize: 17,
          fontWeight: FontWeight.w600,
          color: textPrimary,
          letterSpacing: -0.2,
        ),
      ),

      cardTheme: CardThemeData(
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: border, width: 0.5),
        ),
        color: surface,
        margin: EdgeInsets.zero,
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: textPrimary,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          textStyle: const TextStyle(
            fontFamily: 'Inter',
            fontSize: 14,
            fontWeight: FontWeight.w500,
            letterSpacing: -0.1,
          ),
        ),
      ),

      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          side: const BorderSide(color: border, width: 1),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          textStyle: const TextStyle(
            fontFamily: 'Inter',
            fontSize: 14,
            fontWeight: FontWeight.w500,
            letterSpacing: -0.1,
          ),
        ),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: border, width: 0.5),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: border, width: 0.5),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: primaryDark, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: danger, width: 0.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        hintStyle: const TextStyle(color: textHint, fontSize: 14),
      ),

      textTheme: TextTheme(
        displayLarge: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 30, fontWeight: FontWeight.w700, color: textPrimary, letterSpacing: -0.5),
        displayMedium: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 26, fontWeight: FontWeight.w700, color: textPrimary, letterSpacing: -0.4),
        displaySmall: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 22, fontWeight: FontWeight.w600, color: textPrimary, letterSpacing: -0.3),
        headlineMedium: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 18, fontWeight: FontWeight.w600, color: textPrimary, letterSpacing: -0.2),
        headlineSmall: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 16, fontWeight: FontWeight.w600, color: textPrimary, letterSpacing: -0.2),
        titleLarge: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 15, fontWeight: FontWeight.w600, color: textPrimary, letterSpacing: -0.1),
        titleMedium: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 14, fontWeight: FontWeight.w500, color: textPrimary),
        bodyLarge: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 15, fontWeight: FontWeight.w400, color: textPrimary, height: 1.5),
        bodyMedium: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 14, fontWeight: FontWeight.w400, color: textSecondary, height: 1.5),
        bodySmall: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 12, fontWeight: FontWeight.w400, color: textSecondary),
        labelLarge: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 13, fontWeight: FontWeight.w500, color: textPrimary, letterSpacing: 0.1),
      ),

      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: surface,
        selectedItemColor: primaryDark,
        unselectedItemColor: textHint,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
        selectedLabelStyle: TextStyle(fontFamily: 'Inter', fontSize: 11, fontWeight: FontWeight.w600),
        unselectedLabelStyle: TextStyle(fontFamily: 'Inter', fontSize: 11, fontWeight: FontWeight.w400),
      ),

      dividerTheme: const DividerThemeData(
        color: borderLight,
        thickness: 0.5,
        space: 0,
      ),

      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: textPrimary,
        foregroundColor: Colors.white,
        elevation: 2,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),

      chipTheme: ChipThemeData(
        backgroundColor: surfaceVariant,
        labelStyle: const TextStyle(fontFamily: 'Inter', fontSize: 12, fontWeight: FontWeight.w500, color: textSecondary),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        side: BorderSide.none,
      ),

      dialogTheme: DialogThemeData(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        elevation: 8,
        titleTextStyle: const TextStyle(fontFamily: 'Inter', fontSize: 17, fontWeight: FontWeight.w600, color: textPrimary),
      ),

      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        backgroundColor: textPrimary,
      ),
    );
  }

  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      primaryColor: primaryLight,
      scaffoldBackgroundColor: darkBg,

      colorScheme: const ColorScheme.dark(
        primary: primaryLight,
        secondary: accent,
        surface: darkSurface,
        error: danger,
        onPrimary: Colors.white,
        onSecondary: Colors.white,
        onSurface: Colors.white,
        onError: Colors.white,
      ),

      appBarTheme: const AppBarTheme(
        elevation: 0,
        centerTitle: false,
        backgroundColor: darkBg,
        foregroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        iconTheme: IconThemeData(color: Colors.white),
        titleTextStyle: TextStyle(fontFamily: 'Inter', fontSize: 17, fontWeight: FontWeight.w600, color: Colors.white, letterSpacing: -0.2),
      ),

      cardTheme: CardThemeData(
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: darkBorder, width: 0.5),
        ),
        color: darkSurface,
        margin: EdgeInsets.zero,
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.white,
          foregroundColor: darkBg,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          textStyle: const TextStyle(fontFamily: 'Inter', fontSize: 14, fontWeight: FontWeight.w500),
        ),
      ),

      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: Colors.white,
          side: BorderSide(color: darkBorder, width: 1),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          textStyle: const TextStyle(fontFamily: 'Inter', fontSize: 14, fontWeight: FontWeight.w500),
        ),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: darkCard,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: darkBorder, width: 0.5)),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: darkBorder, width: 0.5)),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: primaryLight, width: 1.5)),
        errorBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: danger, width: 0.5)),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        hintStyle: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 14),
      ),

      textTheme: TextTheme(
        displayLarge: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 30, fontWeight: FontWeight.w700, color: Colors.white, letterSpacing: -0.5),
        displayMedium: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 26, fontWeight: FontWeight.w700, color: Colors.white, letterSpacing: -0.4),
        displaySmall: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 22, fontWeight: FontWeight.w600, color: Colors.white, letterSpacing: -0.3),
        headlineMedium: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 18, fontWeight: FontWeight.w600, color: Colors.white, letterSpacing: -0.2),
        headlineSmall: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white, letterSpacing: -0.2),
        titleLarge: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 15, fontWeight: FontWeight.w600, color: Colors.white, letterSpacing: -0.1),
        titleMedium: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 14, fontWeight: FontWeight.w500, color: Colors.white),
        bodyLarge: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 15, fontWeight: FontWeight.w400, color: Colors.white, height: 1.5),
        bodyMedium: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 14, fontWeight: FontWeight.w400, color: Colors.white70, height: 1.5),
        bodySmall: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 12, fontWeight: FontWeight.w400, color: Colors.white70),
        labelLarge: TextStyle(fontFamily: 'Inter', fontFamilyFallback: fontFallback, fontSize: 13, fontWeight: FontWeight.w500, color: Colors.white, letterSpacing: 0.1),
      ),

      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: darkSurface,
        selectedItemColor: primaryLight,
        unselectedItemColor: Colors.white38,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
        selectedLabelStyle: TextStyle(fontFamily: 'Inter', fontSize: 11, fontWeight: FontWeight.w600),
        unselectedLabelStyle: TextStyle(fontFamily: 'Inter', fontSize: 11, fontWeight: FontWeight.w400),
      ),

      dividerTheme: DividerThemeData(color: darkBorder, thickness: 0.5, space: 0),

      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: Colors.white,
        foregroundColor: darkBg,
        elevation: 2,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),

      chipTheme: ChipThemeData(
        backgroundColor: darkCard,
        labelStyle: TextStyle(fontFamily: 'Inter', fontSize: 12, fontWeight: FontWeight.w500, color: Colors.white70),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        side: BorderSide.none,
      ),

      dialogTheme: DialogThemeData(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        elevation: 8,
        backgroundColor: darkSurface,
        titleTextStyle: const TextStyle(fontFamily: 'Inter', fontSize: 17, fontWeight: FontWeight.w600, color: Colors.white),
      ),

      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        backgroundColor: Colors.white,
      ),
    );
  }
}
