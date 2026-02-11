import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'dart:convert';

import '../models/language_model.dart';
import 'auth_service.dart';

/// Language Service - Handles language persistence and API integration
class LanguageService {
  static const String _boxName = 'settings';
  static const String _languageKey = 'language_code';

  Box? _box;

  Future<void> init() async {
    _box = await Hive.openBox(_boxName);
  }

  /// Get saved language code, defaults to 'en'
  String getSavedLanguageCode() {
    return _box?.get(_languageKey, defaultValue: 'en') ?? 'en';
  }

  /// Save language code locally
  Future<void> saveLanguageCode(String code) async {
    await _box?.put(_languageKey, code);
  }

  /// Get locale from saved language code
  Locale getSavedLocale() {
    final code = getSavedLanguageCode();
    return Locale(code);
  }

  /// Fetch user's language preference from backend
  Future<String?> fetchUserLanguagePreference() async {
    try {
      final response = await authService.get('/language/user/preference');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['language'] as String?;
      }
    } catch (e) {
      debugPrint('Error fetching language preference: $e');
    }
    return null;
  }

  /// Save language preference to backend
  Future<bool> saveLanguagePreferenceToBackend(String languageCode) async {
    try {
      final response = await authService.put(
        '/language/user/preference',
        body: {'language': languageCode},
      );
      return response.statusCode == 200;
    } catch (e) {
      debugPrint('Error saving language preference: $e');
      return false;
    }
  }

  /// Fetch all supported languages from backend
  Future<List<LanguageInfo>> fetchSupportedLanguages() async {
    try {
      final response = await authService.get('/language/supported');
      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        return data.map((json) => LanguageInfo.fromJson(json)).toList();
      }
    } catch (e) {
      debugPrint('Error fetching supported languages: $e');
    }
    // Return default list if API fails
    return supportedLanguages;
  }
}

/// Global language service instance
final languageService = LanguageService();

/// Language state for Riverpod
class LanguageState {
  final String languageCode;
  final Locale locale;
  final bool isLoading;
  final bool hasUnsavedChanges;
  final String? originalLanguageCode;

  const LanguageState({
    required this.languageCode,
    required this.locale,
    this.isLoading = false,
    this.hasUnsavedChanges = false,
    this.originalLanguageCode,
  });

  LanguageState copyWith({
    String? languageCode,
    Locale? locale,
    bool? isLoading,
    bool? hasUnsavedChanges,
    String? originalLanguageCode,
  }) {
    return LanguageState(
      languageCode: languageCode ?? this.languageCode,
      locale: locale ?? this.locale,
      isLoading: isLoading ?? this.isLoading,
      hasUnsavedChanges: hasUnsavedChanges ?? this.hasUnsavedChanges,
      originalLanguageCode: originalLanguageCode ?? this.originalLanguageCode,
    );
  }
}

/// Language state notifier for Riverpod
class LanguageNotifier extends StateNotifier<LanguageState> {
  LanguageNotifier() : super(const LanguageState(
    languageCode: 'en',
    locale: Locale('en'),
  )) {
    _loadSavedLanguage();
  }

  Future<void> _loadSavedLanguage() async {
    final savedCode = languageService.getSavedLanguageCode();
    state = state.copyWith(
      languageCode: savedCode,
      locale: Locale(savedCode),
      originalLanguageCode: savedCode,
    );
  }

  /// Initialize from backend preference
  Future<void> initFromBackend() async {
    if (!authService.isLoggedIn) return;

    state = state.copyWith(isLoading: true);
    try {
      final backendCode = await languageService.fetchUserLanguagePreference();
      if (backendCode != null) {
        await languageService.saveLanguageCode(backendCode);
        state = state.copyWith(
          languageCode: backendCode,
          locale: Locale(backendCode),
          originalLanguageCode: backendCode,
          isLoading: false,
          hasUnsavedChanges: false,
        );
      } else {
        state = state.copyWith(isLoading: false);
      }
    } catch (e) {
      state = state.copyWith(isLoading: false);
    }
  }

  /// Select a new language (marks as pending)
  void selectLanguage(String languageCode) {
    state = state.copyWith(
      languageCode: languageCode,
      locale: Locale(languageCode),
      hasUnsavedChanges: languageCode != state.originalLanguageCode,
    );
  }

  /// Save the selected language to backend and local storage
  Future<bool> saveLanguage() async {
    state = state.copyWith(isLoading: true);

    try {
      // Save to backend if logged in
      if (authService.isLoggedIn) {
        final success = await languageService.saveLanguagePreferenceToBackend(state.languageCode);
        if (!success) {
          state = state.copyWith(isLoading: false);
          return false;
        }
      }

      // Save locally
      await languageService.saveLanguageCode(state.languageCode);

      state = state.copyWith(
        isLoading: false,
        hasUnsavedChanges: false,
        originalLanguageCode: state.languageCode,
      );

      return true;
    } catch (e) {
      state = state.copyWith(isLoading: false);
      return false;
    }
  }

  /// Cancel selection and revert to original
  void cancelSelection() {
    if (state.originalLanguageCode != null) {
      state = state.copyWith(
        languageCode: state.originalLanguageCode!,
        locale: Locale(state.originalLanguageCode!),
        hasUnsavedChanges: false,
      );
    }
  }

  /// Get current language code
  String get currentLanguageCode => state.languageCode;
}

/// Riverpod provider for language state
final languageProvider = StateNotifierProvider<LanguageNotifier, LanguageState>((ref) {
  return LanguageNotifier();
});

/// Provider to get current language info
final currentLanguageInfoProvider = Provider<LanguageInfo>((ref) {
  final state = ref.watch(languageProvider);
  return getLanguageInfo(state.languageCode);
});

/// Provider to check if there are unsaved changes
final hasUnsavedLanguageChangesProvider = Provider<bool>((ref) {
  return ref.watch(languageProvider).hasUnsavedChanges;
});
