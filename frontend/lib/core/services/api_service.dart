import 'dart:convert';
import 'package:http/http.dart' as http;
import 'auth_service.dart';

/// Generic API Service for making authenticated HTTP requests
class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  final AuthService _authService = AuthService();

  String get baseUrl => _authService.baseUrl;

  /// Make an authenticated GET request
  Future<Map<String, dynamic>?> get(String path) async {
    final token = _authService.token;
    if (token == null) return null;

    try {
      final response = await http.get(
        Uri.parse('$baseUrl$path'),
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else if (response.statusCode == 401) {
        AuthService.onUnauthorized?.call();
        return null;
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  /// Make an authenticated POST request
  Future<Map<String, dynamic>?> post(String path, Map<String, dynamic> body) async {
    final token = _authService.token;
    if (token == null) return null;

    try {
      final response = await http.post(
        Uri.parse('$baseUrl$path'),
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: jsonEncode(body),
      );

      if (response.statusCode == 200 || response.statusCode == 201) {
        return jsonDecode(response.body);
      } else if (response.statusCode == 401) {
        AuthService.onUnauthorized?.call();
        return null;
      }
      return null;
    } catch (e) {
      return null;
    }
  }
}
