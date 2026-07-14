/// Stub implementation for platform storage
/// This is the default - overridden by web or mobile implementations

class PlatformStorage {
  Future<void> write({required String key, required String? value}) async {
    throw UnsupportedError("PlatformStorage not supported on this platform");
  }

  Future<String?> read({required String key}) async {
    throw UnsupportedError("PlatformStorage not supported on this platform");
  }

  Future<void> delete({required String key}) async {
    throw UnsupportedError("PlatformStorage not supported on this platform");
  }
}

/// Get the base URL for the current platform
String getPlatformBaseUrl() {
  return "https://ir.alexandratechlab.com/api/v1";
}
