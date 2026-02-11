// ignore: avoid_web_libraries_in_flutter
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

/// Get the base URL for the backend API.
/// When hosted on S3/CloudFront, use the ALB CloudFront (HTTPS).
/// When on localhost or ALB directly, use the same host.
String getPlatformBaseUrl() {
  final location = html.window.location;
  final host = location.host;

  // If on CloudFront or S3 website, use the ALB CloudFront for HTTPS
  if (host.contains('cloudfront') || host.contains('s3-website')) {
    return "https://d2f065h47nuk0c.cloudfront.net/api/v1";
  }

  // Otherwise use same host (localhost or ALB direct access)
  final protocol = location.protocol;
  return "$protocol//$host/api/v1";
}
