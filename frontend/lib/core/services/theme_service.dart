import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';

/// Theme Service - Handles theme mode persistence
class ThemeService {
  static const String _boxName = 'settings';
  static const String _themeKey = 'theme_mode';

  Box? _box;

  Future<void> init() async {
    _box = await Hive.openBox(_boxName);
  }

  /// Get saved theme mode string, defaults to 'system'
  String getSavedThemeMode() {
    return _box?.get(_themeKey, defaultValue: 'system') ?? 'system';
  }

  /// Save theme mode locally
  Future<void> saveThemeMode(String mode) async {
    await _box?.put(_themeKey, mode);
  }

  /// Convert string to ThemeMode
  static ThemeMode parseThemeMode(String mode) {
    switch (mode) {
      case 'light':
        return ThemeMode.light;
      case 'dark':
        return ThemeMode.dark;
      default:
        return ThemeMode.system;
    }
  }

  /// Convert ThemeMode to string
  static String themeModeToString(ThemeMode mode) {
    switch (mode) {
      case ThemeMode.light:
        return 'light';
      case ThemeMode.dark:
        return 'dark';
      case ThemeMode.system:
        return 'system';
    }
  }
}

/// Global theme service instance
final themeService = ThemeService();

/// Theme state for Riverpod
class ThemeState {
  final ThemeMode themeMode;
  final String themeModeString;

  const ThemeState({
    required this.themeMode,
    required this.themeModeString,
  });

  ThemeState copyWith({
    ThemeMode? themeMode,
    String? themeModeString,
  }) {
    return ThemeState(
      themeMode: themeMode ?? this.themeMode,
      themeModeString: themeModeString ?? this.themeModeString,
    );
  }
}

/// Theme state notifier for Riverpod
class ThemeNotifier extends StateNotifier<ThemeState> {
  ThemeNotifier()
      : super(const ThemeState(
          themeMode: ThemeMode.system,
          themeModeString: 'system',
        )) {
    _loadSavedTheme();
  }

  Future<void> _loadSavedTheme() async {
    final saved = themeService.getSavedThemeMode();
    state = ThemeState(
      themeMode: ThemeService.parseThemeMode(saved),
      themeModeString: saved,
    );
  }

  /// Set theme mode
  Future<void> setThemeMode(String mode) async {
    await themeService.saveThemeMode(mode);
    state = ThemeState(
      themeMode: ThemeService.parseThemeMode(mode),
      themeModeString: mode,
    );
  }
}

/// Riverpod provider for theme state
final themeProvider =
    StateNotifierProvider<ThemeNotifier, ThemeState>((ref) {
  return ThemeNotifier();
});
