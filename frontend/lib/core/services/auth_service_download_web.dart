import 'dart:typed_data';
// ignore: avoid_web_libraries_in_flutter
import 'dart:html' as html;

/// Web implementation for file download
Future<void> downloadForWeb(List<int> bytes, String filename) async {
  final blob = html.Blob([Uint8List.fromList(bytes)]);
  final url = html.Url.createObjectUrlFromBlob(blob);
  final anchor = html.AnchorElement()
    ..href = url
    ..download = filename
    ..style.display = 'none';
  html.document.body?.children.add(anchor);
  anchor.click();
  html.document.body?.children.remove(anchor);
  html.Url.revokeObjectUrl(url);
}

Future<void> downloadForMobile(List<int> bytes, String filename) async {
  // On web, always use web download
  await downloadForWeb(bytes, filename);
}
