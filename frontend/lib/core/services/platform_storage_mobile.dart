import "package:flutter_secure_storage/flutter_secure_storage.dart";

/// Mobile implementation of PlatformStorage using FlutterSecureStorage.
/// FlutterSecureStorage works fine on mobile (iOS/Android) since it uses
/// the Keychain (iOS) or EncryptedSharedPreferences (Android).
class PlatformStorage {
  final FlutterSecureStorage _storage = const FlutterSecureStorage();

  Future<void> write({required String key, required String? value}) async {
    if (value == null) {
      await _storage.delete(key: key);
    } else {
      await _storage.write(key: key, value: value);
    }
  }

  Future<String?> read({required String key}) async {
    return await _storage.read(key: key);
  }

  Future<void> delete({required String key}) async {
    await _storage.delete(key: key);
  }
}

/// On mobile/desktop, use the ALB URL since there is no browser location.
String getPlatformBaseUrl() {
  return "http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com/api/v1";
}
