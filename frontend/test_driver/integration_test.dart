import 'dart:io';
import 'package:integration_test/integration_test_driver_extended.dart';

Future<void> main() => integrationDriver(
  onScreenshot: (String name, List<int> bytes, [Map<String, Object?>? args]) async {
    final file = await File('screenshots/$name.png').create(recursive: true);
    file.writeAsBytesSync(bytes);
    print('[screenshot] Saved: screenshots/$name.png (${bytes.length} bytes)');
    return true;
  },
);
