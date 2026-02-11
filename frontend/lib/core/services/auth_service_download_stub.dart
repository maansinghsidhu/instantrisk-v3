/// Stub implementation for download (should never be used)
Future<void> downloadForWeb(List<int> bytes, String filename) async {
  throw UnsupportedError('Download not supported on this platform');
}

Future<void> downloadForMobile(List<int> bytes, String filename) async {
  throw UnsupportedError('Download not supported on this platform');
}
