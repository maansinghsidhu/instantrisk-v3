// ignore: avoid_web_libraries_in_flutter, deprecated_member_use
import "dart:html" as html;

/// Web implementation of PlatformStorage using window.localStorage
/// This works on both HTTP and HTTPS (unlike FlutterSecureStorage which
/// requires HTTPS for encrypted IndexedDB).
class PlatformStorage {
  Future<void> write({required String key, required String? value}) async {
    if (value == null) {
      html.window.localStorage.remove(key);
    } else {
      html.window.localStorage[key] = value;
    }
  }

  Future<String?> read({required String key}) async {
    return html.window.localStorage[key];
  }

  Future<void> delete({required String key}) async {
    html.window.localStorage.remove(key);
  }
}

/// Get the same-origin API URL for browser builds.
///
/// CloudFront forwards `/api/*` to the FastAPI origin, so keeping requests on
/// the current origin preserves TLS and the Authorization header without CORS
/// or mixed-content fallbacks.
String getPlatformBaseUrl() {
  return "${html.window.location.origin}/api/v1";
}
