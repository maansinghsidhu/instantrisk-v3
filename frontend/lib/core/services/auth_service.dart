import "package:flutter/foundation.dart";
import "package:http/http.dart" as http;
import "package:dio/dio.dart";
import "dart:convert";

// Conditional imports for platform-specific download
import "auth_service_download_stub.dart"
    if (dart.library.io) "auth_service_download_mobile.dart"
    if (dart.library.html) "auth_service_download_web.dart" as download_impl;

// Conditional imports for platform-specific storage
// On web: uses window.localStorage (works on HTTP and HTTPS)
// On mobile: uses FlutterSecureStorage (Keychain/EncryptedSharedPreferences)
import "platform_storage_stub.dart"
    if (dart.library.io) "platform_storage_mobile.dart"
    if (dart.library.html) "platform_storage_web.dart" as platform_storage;

import "subscription_service.dart";

/// Authentication Service - Handles login, token storage, and API auth
class AuthService {
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  // Use dynamic base URL from platform (web: current host, mobile: hardcoded)
  static final String _baseUrl = platform_storage.getPlatformBaseUrl();
  static const String _tokenKey = "auth_token";
  static const String _userKey = "user_data";

  // Use platform-aware storage instead of FlutterSecureStorage directly
  final platform_storage.PlatformStorage _storage = platform_storage.PlatformStorage();

  String? _token;
  Map<String, dynamic>? _user;

  /// Callback to handle 401 errors - set by AppRouter
  static void Function()? onUnauthorized;

  String? get token => _token;
  Map<String, dynamic>? get user => _user;
  bool get isLoggedIn => _token != null;
  String get baseUrl => _baseUrl;

  /// Initialize - load saved token on app start
  Future<void> init() async {
    try {
      _token = await _storage.read(key: _tokenKey);
      final userData = await _storage.read(key: _userKey);
      if (userData != null) {
        _user = jsonDecode(userData);
      }

      // If user is logged in, load their subscription data
      if (_token != null) {
        try {
          await subscriptionService.loadSubscription();
          await subscriptionService.loadFeatures();
        } catch (e) {
          debugPrint("Auth init error loading subscription: $e");
        }
      }
    } catch (e) {
      debugPrint("Auth init error: $e");
    }
  }

  /// Login with email and password (optionally with 2FA code)
  Future<Map<String, dynamic>> login(String email, String password, {String? totpCode}) async {
    try {
      final body = {
        "email": email,
        "password": password,
      };
      if (totpCode != null && totpCode.isNotEmpty) {
        body["totp_code"] = totpCode;
      }

      final response = await http.post(
        Uri.parse("$_baseUrl/auth/login"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        // Check if 2FA is required
        if (data["requires_2fa"] == true) {
          return {
            "success": false,
            "requires_2fa": true,
            "user_id": data["user_id"],
            "message": data["message"] ?? "2FA verification required"
          };
        }

        _token = data["access_token"];
        _user = data["user"];

        // Save to storage (localStorage on web, secure storage on mobile)
        await _storage.write(key: _tokenKey, value: _token);
        await _storage.write(key: _userKey, value: jsonEncode(_user));

        // Store refresh token if provided
        if (data["refresh_token"] != null) {
          await _storeRefreshToken(data["refresh_token"]);
        }

        // Load subscription data after successful login
        try {
          await subscriptionService.loadSubscription();
          await subscriptionService.loadFeatures();
        } catch (e) {
          debugPrint("Error loading subscription after login: $e");
        }

        return {"success": true, "user": _user};
      } else {
        final error = jsonDecode(response.body);
        return {"success": false, "error": error["detail"] ?? "Login failed"};
      }
    } catch (e) {
      return {"success": false, "error": "Connection error: $e"};
    }
  }

  // ==========================================================================
  // Two-Factor Authentication Methods
  // ==========================================================================

  /// Get 2FA status for current user
  Future<Map<String, dynamic>> get2FAStatus() async {
    try {
      final response = await get("/2fa/status");
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      return {"enabled": false, "has_backup_codes": false};
    } catch (e) {
      debugPrint("Error getting 2FA status: $e");
      return {"enabled": false, "has_backup_codes": false};
    }
  }

  /// Setup 2FA - returns QR code and secret
  Future<Map<String, dynamic>> setup2FA() async {
    try {
      final response = await post("/2fa/setup");
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return {"success": true, ...data};
      } else {
        final error = jsonDecode(response.body);
        return {"success": false, "error": error["detail"] ?? "Setup failed"};
      }
    } catch (e) {
      return {"success": false, "error": "Connection error: $e"};
    }
  }

  /// Verify 2FA code and enable 2FA
  Future<Map<String, dynamic>> verify2FA(String code) async {
    try {
      final response = await http.post(
        Uri.parse("$_baseUrl/2fa/verify"),
        headers: authHeaders,
        body: jsonEncode({"code": code}),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return {"success": true, ...data};
      } else {
        final error = jsonDecode(response.body);
        return {"success": false, "error": error["detail"] ?? "Verification failed"};
      }
    } catch (e) {
      return {"success": false, "error": "Connection error: $e"};
    }
  }

  /// Disable 2FA
  Future<Map<String, dynamic>> disable2FA(String password, String code) async {
    try {
      final response = await http.post(
        Uri.parse("$_baseUrl/2fa/disable"),
        headers: authHeaders,
        body: jsonEncode({"password": password, "code": code}),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return {"success": true, ...data};
      } else {
        final error = jsonDecode(response.body);
        return {"success": false, "error": error["detail"] ?? "Disable failed"};
      }
    } catch (e) {
      return {"success": false, "error": "Connection error: $e"};
    }
  }

  /// Regenerate backup codes
  Future<Map<String, dynamic>> regenerateBackupCodes(String code) async {
    try {
      final response = await http.post(
        Uri.parse("$_baseUrl/2fa/regenerate-backup-codes"),
        headers: authHeaders,
        body: jsonEncode({"code": code}),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return {"success": true, ...data};
      } else {
        final error = jsonDecode(response.body);
        return {"success": false, "error": error["detail"] ?? "Regeneration failed"};
      }
    } catch (e) {
      return {"success": false, "error": "Connection error: $e"};
    }
  }

  /// Change password
  Future<Map<String, dynamic>> changePassword(String currentPassword, String newPassword) async {
    try {
      final response = await http.post(
        Uri.parse("$_baseUrl/auth/change-password"),
        headers: authHeaders,
        body: jsonEncode({
          "current_password": currentPassword,
          "new_password": newPassword,
        }),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        return {"success": true, "message": "Password changed successfully"};
      } else {
        final error = jsonDecode(response.body);
        return {"success": false, "error": error["detail"] ?? "Password change failed"};
      }
    } catch (e) {
      return {"success": false, "error": "Connection error: $e"};
    }
  }

  /// Get active sessions
  Future<Map<String, dynamic>> getActiveSessions() async {
    try {
      final response = await http.get(
        Uri.parse("$_baseUrl/auth/sessions"),
        headers: authHeaders,
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return {"success": true, "sessions": data["sessions"] ?? []};
      } else {
        return {"success": false, "sessions": []};
      }
    } catch (e) {
      return {"success": false, "error": "Connection error: $e", "sessions": []};
    }
  }

  /// Revoke a specific session
  Future<Map<String, dynamic>> revokeSession(String sessionId) async {
    try {
      final response = await http.delete(
        Uri.parse("$_baseUrl/auth/sessions/$sessionId"),
        headers: authHeaders,
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        return {"success": true};
      } else {
        final error = jsonDecode(response.body);
        return {"success": false, "error": error["detail"] ?? "Failed to revoke session"};
      }
    } catch (e) {
      return {"success": false, "error": "Connection error: $e"};
    }
  }

  /// Revoke all other sessions
  Future<Map<String, dynamic>> revokeAllSessions() async {
    try {
      final response = await http.post(
        Uri.parse("$_baseUrl/auth/sessions/revoke-all"),
        headers: authHeaders,
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        return {"success": true};
      } else {
        final error = jsonDecode(response.body);
        return {"success": false, "error": error["detail"] ?? "Failed to revoke sessions"};
      }
    } catch (e) {
      return {"success": false, "error": "Connection error: $e"};
    }
  }

  /// Register new user
  Future<Map<String, dynamic>> register(String email, String password, String fullName) async {
    try {
      final response = await http.post(
        Uri.parse("$_baseUrl/auth/register"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "email": email,
          "password": password,
          "full_name": fullName,
        }),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200 || response.statusCode == 201) {
        // Auto-login after registration
        return await login(email, password);
      } else {
        final error = jsonDecode(response.body);
        return {"success": false, "error": error["detail"] ?? "Registration failed"};
      }
    } catch (e) {
      return {"success": false, "error": "Connection error: $e"};
    }
  }

  /// Logout - clear token and user data
  Future<void> logout() async {
    _token = null;
    _user = null;
    _refreshToken = null;
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _userKey);
    await _storage.delete(key: _refreshTokenKey);
  }

  /// Get authenticated headers for API requests
  Map<String, String> get authHeaders => {
    "Content-Type": "application/json",
    if (_token != null) "Authorization": "Bearer $_token",
  };

  /// Refresh token storage key
  static const String _refreshTokenKey = "refresh_token";
  String? _refreshToken;
  bool _isRefreshing = false;

  /// Store refresh token
  Future<void> _storeRefreshToken(String token) async {
    _refreshToken = token;
    await _storage.write(key: _refreshTokenKey, value: token);
  }

  /// Load refresh token from storage
  Future<void> _loadRefreshToken() async {
    _refreshToken = await _storage.read(key: _refreshTokenKey);
  }

  /// Try to refresh the access token
  Future<bool> _tryRefreshToken() async {
    if (_isRefreshing) return false;
    if (_refreshToken == null) {
      await _loadRefreshToken();
      if (_refreshToken == null) return false;
    }

    _isRefreshing = true;
    try {
      final response = await http.post(
        Uri.parse("$_baseUrl/auth/refresh"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"refresh_token": _refreshToken}),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _token = data["access_token"];
        await _storage.write(key: _tokenKey, value: _token);

        // Store new refresh token if provided
        if (data["refresh_token"] != null) {
          await _storeRefreshToken(data["refresh_token"]);
        }

        debugPrint("Token refreshed successfully");
        _isRefreshing = false;
        return true;
      }
    } catch (e) {
      debugPrint("Token refresh failed: $e");
    }

    _isRefreshing = false;
    return false;
  }

  /// Handle response and check for 401 unauthorized
  /// Attempts token refresh before logging out
  Future<http.Response> _handleResponse(http.Response response, {String? endpoint, Map<String, dynamic>? body, bool isRetry = false}) async {
    if (response.statusCode == 401 && !isRetry) {
      // Try to refresh the token
      final refreshed = await _tryRefreshToken();
      if (refreshed && endpoint != null) {
        // Retry the original request with new token
        debugPrint("Retrying request after token refresh: $endpoint");
        if (body != null) {
          return post(endpoint, body: body);
        } else {
          return get(endpoint);
        }
      }

      // Refresh failed, logout
      await logout();
      onUnauthorized?.call();
    }
    return response;
  }

  /// Make authenticated GET request
  Future<http.Response> get(String endpoint, {bool isRetry = false, Duration timeout = const Duration(seconds: 60)}) async {
    final response = await http.get(
      Uri.parse("$_baseUrl$endpoint"),
      headers: authHeaders,
    ).timeout(timeout);
    return _handleResponse(response, endpoint: endpoint, isRetry: isRetry);
  }

  /// Make authenticated POST request
  Future<http.Response> post(String endpoint, {Map<String, dynamic>? body, bool isRetry = false}) async {
    final response = await http.post(
      Uri.parse("$_baseUrl$endpoint"),
      headers: authHeaders,
      body: body != null ? jsonEncode(body) : null,
    ).timeout(const Duration(seconds: 30));
    return _handleResponse(response, endpoint: endpoint, body: body, isRetry: isRetry);
  }

  /// Upload file with auth
  Future<http.StreamedResponse> uploadFile(String endpoint, String filePath, String fieldName, {Map<String, String>? fields}) async {
    final request = http.MultipartRequest("POST", Uri.parse("$_baseUrl$endpoint"));
    request.headers.addAll(authHeaders);
    request.files.add(await http.MultipartFile.fromPath(fieldName, filePath));
    if (fields != null) {
      request.fields.addAll(fields);
    }
    return await request.send().timeout(const Duration(minutes: 5));
  }

  /// Upload file from bytes with auth
  Future<http.StreamedResponse> uploadFileBytes(String endpoint, List<int> bytes, String filename, String fieldName, {Map<String, String>? fields}) async {
    final request = http.MultipartRequest("POST", Uri.parse("$_baseUrl$endpoint"));
    request.headers["Authorization"] = "Bearer $_token";
    request.files.add(http.MultipartFile.fromBytes(fieldName, bytes, filename: filename));
    if (fields != null) {
      request.fields.addAll(fields);
    }
    return await request.send().timeout(const Duration(minutes: 5));
  }

  /// Upload file with progress tracking using Dio
  /// Returns response data on success, throws on error
  /// [onProgress] callback receives (sent, total) bytes
  Future<Map<String, dynamic>> uploadWithProgress({
    required String endpoint,
    required Uint8List bytes,
    required String filename,
    required String fieldName,
    void Function(int sent, int total)? onProgress,
  }) async {
    final dio = Dio();
    dio.options.headers["Authorization"] = "Bearer $_token";
    dio.options.connectTimeout = const Duration(seconds: 30);
    dio.options.receiveTimeout = const Duration(minutes: 5);
    dio.options.sendTimeout = const Duration(minutes: 5);

    final formData = FormData.fromMap({
      fieldName: MultipartFile.fromBytes(bytes, filename: filename),
    });

    try {
      final response = await dio.post(
        "$_baseUrl$endpoint",
        data: formData,
        onSendProgress: (sent, total) {
          onProgress?.call(sent, total);
        },
      );

      if (response.statusCode == 200 || response.statusCode == 201) {
        return response.data is Map<String, dynamic>
            ? response.data
            : jsonDecode(response.data.toString());
      } else {
        throw Exception("Upload failed: ${response.statusCode}");
      }
    } on DioException catch (e) {
      throw Exception("Upload error: ${e.message}");
    }
  }

  /// Upload file from path with progress tracking using Dio
  Future<Map<String, dynamic>> uploadFileWithProgress({
    required String endpoint,
    required String filePath,
    required String fieldName,
    void Function(int sent, int total)? onProgress,
  }) async {
    final dio = Dio();
    dio.options.headers["Authorization"] = "Bearer $_token";
    dio.options.connectTimeout = const Duration(seconds: 30);
    dio.options.receiveTimeout = const Duration(minutes: 5);
    dio.options.sendTimeout = const Duration(minutes: 5);

    final formData = FormData.fromMap({
      fieldName: await MultipartFile.fromFile(filePath),
    });

    try {
      final response = await dio.post(
        "$_baseUrl$endpoint",
        data: formData,
        onSendProgress: (sent, total) {
          onProgress?.call(sent, total);
        },
      );

      if (response.statusCode == 200 || response.statusCode == 201) {
        return response.data is Map<String, dynamic>
            ? response.data
            : jsonDecode(response.data.toString());
      } else {
        throw Exception("Upload failed: ${response.statusCode}");
      }
    } on DioException catch (e) {
      throw Exception("Upload error: ${e.message}");
    }
  }

  /// Upload file without auth (public endpoint) with progress tracking
  Future<Map<String, dynamic>> uploadPublicWithProgress({
    required String url,
    required Uint8List bytes,
    required String filename,
    required String fieldName,
    void Function(int sent, int total)? onProgress,
  }) async {
    final dio = Dio();
    dio.options.connectTimeout = const Duration(seconds: 30);
    dio.options.receiveTimeout = const Duration(minutes: 5);
    dio.options.sendTimeout = const Duration(minutes: 5);

    final formData = FormData.fromMap({
      fieldName: MultipartFile.fromBytes(bytes, filename: filename),
    });

    try {
      final response = await dio.post(
        url,
        data: formData,
        onSendProgress: (sent, total) {
          onProgress?.call(sent, total);
        },
      );

      if (response.statusCode == 200 || response.statusCode == 201) {
        return response.data is Map<String, dynamic>
            ? response.data
            : jsonDecode(response.data.toString());
      } else {
        throw Exception("Upload failed: ${response.statusCode}");
      }
    } on DioException catch (e) {
      throw Exception("Upload error: ${e.message}");
    }
  }

  /// Make authenticated POST request with longer timeout (for processing)
  Future<http.Response> postLong(String endpoint, {Map<String, dynamic>? body, Duration timeout = const Duration(minutes: 5)}) async {
    final response = await http.post(
      Uri.parse("$_baseUrl$endpoint"),
      headers: authHeaders,
      body: body != null ? jsonEncode(body) : null,
    ).timeout(timeout);
    return _handleResponse(response);
  }

  /// Make authenticated PUT request
  Future<http.Response> put(String endpoint, {Map<String, dynamic>? body}) async {
    final response = await http.put(
      Uri.parse("$_baseUrl$endpoint"),
      headers: authHeaders,
      body: body != null ? jsonEncode(body) : null,
    ).timeout(const Duration(seconds: 30));
    return _handleResponse(response);
  }

  /// Make authenticated PATCH request
  Future<http.Response> patch(String endpoint, {Map<String, dynamic>? body}) async {
    final response = await http.patch(
      Uri.parse("$_baseUrl$endpoint"),
      headers: authHeaders,
      body: body != null ? jsonEncode(body) : null,
    ).timeout(const Duration(seconds: 30));
    return _handleResponse(response);
  }

  /// Make authenticated DELETE request
  Future<http.Response> delete(String endpoint) async {
    final response = await http.delete(
      Uri.parse("$_baseUrl$endpoint"),
      headers: authHeaders,
    ).timeout(const Duration(seconds: 30));
    return _handleResponse(response);
  }

  /// Get the auth token
  Future<String?> getToken() async {
    return _token;
  }

  /// Download a file with authentication
  /// For web: uses HTML anchor element with blob URL
  /// For mobile: saves to downloads folder
  Future<void> downloadFile(String url, String filename) async {
    final dio = Dio();
    dio.options.headers["Authorization"] = "Bearer $_token";
    dio.options.responseType = ResponseType.bytes;
    dio.options.receiveTimeout = const Duration(minutes: 5);

    try {
      final response = await dio.get<List<int>>(url);

      if (response.statusCode == 200 && response.data != null) {
        final bytes = response.data!;

        // For web, create a download link
        if (kIsWeb) {
          await _downloadForWeb(bytes, filename);
        } else {
          // For mobile, save to downloads
          await _downloadForMobile(bytes, filename);
        }
      } else {
        throw Exception("Download failed: ${response.statusCode}");
      }
    } on DioException catch (e) {
      throw Exception("Download error: ${e.message}");
    }
  }

  Future<void> _downloadForWeb(List<int> bytes, String filename) async {
    // Web download implementation - uses conditional import
    try {
      await download_impl.downloadForWeb(bytes, filename);
      debugPrint("Web download completed: $filename (${bytes.length} bytes)");
    } catch (e) {
      debugPrint("Web download error: $e");
      rethrow;
    }
  }

  Future<void> _downloadForMobile(List<int> bytes, String filename) async {
    // Mobile download implementation - uses conditional import
    try {
      await download_impl.downloadForMobile(bytes, filename);
      debugPrint("Mobile download completed: $filename (${bytes.length} bytes)");
    } catch (e) {
      debugPrint("Mobile download error: $e");
      rethrow;
    }
  }
}

// Global instance
final authService = AuthService();
