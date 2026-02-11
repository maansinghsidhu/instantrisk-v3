import 'dart:io';
import 'package:path_provider/path_provider.dart';

/// Mobile implementation for file download
Future<void> downloadForWeb(List<int> bytes, String filename) async {
  // On mobile, fallback to mobile download
  await downloadForMobile(bytes, filename);
}

Future<void> downloadForMobile(List<int> bytes, String filename) async {
  // Get the downloads directory or app documents directory
  final directory = await getApplicationDocumentsDirectory();
  final downloadsPath = '${directory.path}/Downloads';

  // Create Downloads folder if it doesn't exist
  final downloadsDir = Directory(downloadsPath);
  if (!await downloadsDir.exists()) {
    await downloadsDir.create(recursive: true);
  }

  // Write the file
  final filePath = '$downloadsPath/$filename';
  final file = File(filePath);
  await file.writeAsBytes(bytes);
}
