import 'package:flutter/foundation.dart' show Uint8List;
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
import 'package:dio/dio.dart';

class QRUploadScreen extends StatefulWidget {
  final String token;

  const QRUploadScreen({super.key, required this.token});

  @override
  State<QRUploadScreen> createState() => _QRUploadScreenState();
}

class _UploadingFile {
  final String name;
  final int size;
  int sentBytes;
  bool isComplete;
  bool hasError;
  String? errorMessage;
  String? documentId;
  String? url;

  _UploadingFile({
    required this.name,
    required this.size,
    this.sentBytes = 0,
    this.isComplete = false,
    this.hasError = false,
    this.errorMessage,
    this.documentId,
    this.url,
  });

  double get progress => size > 0 ? sentBytes / size : 0;
  String get progressText => '${(progress * 100).toStringAsFixed(0)}%';
  String get sizeText => _formatBytes(size);
  String get sentText => _formatBytes(sentBytes);

  static String _formatBytes(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
}

class _QRUploadScreenState extends State<QRUploadScreen> {
  final List<_UploadingFile> _files = [];
  bool _isComplete = false;
  String? _error;
  final String _apiBase = '/api/v1/upload-sessions';
  int _currentUploadIndex = -1;

  @override
  void initState() {
    super.initState();
    _validateSession();
  }

  Future<void> _validateSession() async {
    try {
      final dio = Dio();
      final response = await dio.get('$_apiBase/${widget.token}/validate');
      if (response.statusCode != 200) {
        setState(() => _error = response.data['detail'] ?? 'Session expired or invalid');
      }
    } catch (e) {
      if (e is DioException && e.response != null) {
        setState(() => _error = e.response?.data['detail'] ?? 'Session expired or invalid');
      } else {
        setState(() => _error = 'Connection failed. Check your internet.');
      }
    }
  }

  Future<void> _takePhoto() async {
    final picker = ImagePicker();
    final image = await picker.pickImage(source: ImageSource.camera, imageQuality: 85);
    if (image != null) {
      final bytes = await image.readAsBytes();
      await _uploadFile(bytes, image.name);
    }
  }

  Future<void> _pickFromGallery() async {
    final picker = ImagePicker();
    final images = await picker.pickMultiImage(imageQuality: 85);
    for (final image in images) {
      final bytes = await image.readAsBytes();
      await _uploadFile(bytes, image.name);
    }
  }

  Future<void> _pickFiles() async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: ['jpg', 'jpeg', 'png', 'pdf'],
      withData: true,
    );
    if (result != null) {
      for (final file in result.files) {
        if (file.bytes != null) {
          await _uploadFile(file.bytes!, file.name);
        }
      }
    }
  }

  Future<void> _uploadFile(Uint8List bytes, String filename) async {
    final file = _UploadingFile(name: filename, size: bytes.length);
    setState(() {
      _files.add(file);
      _currentUploadIndex = _files.length - 1;
    });

    try {
      final dio = Dio();
      dio.options.connectTimeout = const Duration(seconds: 30);
      dio.options.receiveTimeout = const Duration(minutes: 5);
      dio.options.sendTimeout = const Duration(minutes: 5);

      final formData = FormData.fromMap({
        'file': MultipartFile.fromBytes(bytes, filename: filename),
      });

      final response = await dio.post(
        '$_apiBase/${widget.token}/upload',
        data: formData,
        onSendProgress: (sent, total) {
          setState(() {
            file.sentBytes = sent;
          });
        },
      );

      if (response.statusCode == 200) {
        final data = response.data;
        setState(() {
          file.isComplete = true;
          file.sentBytes = file.size;
          file.documentId = data['document_id'];
          file.url = data['url'];
        });
      } else {
        setState(() {
          file.hasError = true;
          file.errorMessage = 'Upload failed: ${response.statusCode}';
        });
      }
    } catch (e) {
      setState(() {
        file.hasError = true;
        file.errorMessage = 'Upload failed: $e';
      });
    }
    setState(() => _currentUploadIndex = -1);
  }

  Future<void> _completeUpload() async {
    try {
      final dio = Dio();
      await dio.post('$_apiBase/${widget.token}/complete');
      setState(() => _isComplete = true);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to complete. Try again.'), backgroundColor: Colors.red),
        );
      }
    }
  }

  void _removeFile(int index) {
    setState(() => _files.removeAt(index));
  }

  void _retryFile(int index) async {
    final file = _files[index];
    setState(() {
      file.hasError = false;
      file.errorMessage = null;
      file.sentBytes = 0;
    });
    // Note: We don't have the original bytes here, so user needs to re-select the file
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Please select the file again to retry')),
    );
    _files.removeAt(index);
  }

  int get _completedCount => _files.where((f) => f.isComplete).length;
  int get _totalCount => _files.length;
  bool get _isUploading => _currentUploadIndex >= 0;
  bool get _hasErrors => _files.any((f) => f.hasError);

  @override
  Widget build(BuildContext context) {
    if (_isComplete) {
      return _buildCompleteScreen();
    }

    if (_error != null) {
      return _buildErrorScreen();
    }

    return Scaffold(
      backgroundColor: const Color(0xFF1E3A5F),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: const Text('Upload Documents'),
        centerTitle: true,
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              // Upload buttons
              _buildUploadButton(
                icon: Icons.camera_alt,
                label: 'Take Photo',
                onTap: _isUploading ? null : _takePhoto,
                primary: true,
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: _buildUploadButton(
                      icon: Icons.photo_library,
                      label: 'Gallery',
                      onTap: _isUploading ? null : _pickFromGallery,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildUploadButton(
                      icon: Icons.folder,
                      label: 'Files',
                      onTap: _isUploading ? null : _pickFiles,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              // Progress summary
              if (_files.isNotEmpty)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Documents',
                        style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 14),
                      ),
                      Row(
                        children: [
                          if (_isUploading) ...[
                            const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            ),
                            const SizedBox(width: 8),
                          ],
                          Text(
                            '$_completedCount / $_totalCount uploaded',
                            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),

              const SizedBox(height: 16),

              // Files list with progress
              Expanded(
                child: _files.isEmpty
                    ? _buildEmptyState()
                    : ListView.builder(
                        itemCount: _files.length,
                        itemBuilder: (context, index) => _buildFileItem(_files[index], index),
                      ),
              ),

              // Done button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _completedCount > 0 && !_isUploading ? _completeUpload : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: const Color(0xFF1E3A5F),
                    disabledBackgroundColor: Colors.white24,
                    disabledForegroundColor: Colors.white38,
                    padding: const EdgeInsets.symmetric(vertical: 18),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  ),
                  child: Text(
                    _isUploading
                        ? 'Uploading...'
                        : 'Done - Send to Desktop',
                    style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildUploadButton({
    required IconData icon,
    required String label,
    required VoidCallback? onTap,
    bool primary = false,
  }) {
    if (primary) {
      return ElevatedButton.icon(
        onPressed: onTap,
        icon: Icon(icon, size: 28),
        label: Text(label, style: const TextStyle(fontSize: 18)),
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF00B894),
          foregroundColor: Colors.white,
          disabledBackgroundColor: const Color(0xFF00B894).withOpacity(0.5),
          padding: const EdgeInsets.symmetric(vertical: 20),
          minimumSize: const Size.fromHeight(60),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
      );
    }

    return OutlinedButton.icon(
      onPressed: onTap,
      icon: Icon(icon),
      label: Text(label),
      style: OutlinedButton.styleFrom(
        foregroundColor: Colors.white,
        disabledForegroundColor: Colors.white38,
        side: BorderSide(color: onTap != null ? Colors.white24 : Colors.white12),
        padding: const EdgeInsets.symmetric(vertical: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.cloud_upload_outlined, size: 64, color: Colors.white.withOpacity(0.3)),
          const SizedBox(height: 16),
          Text(
            'Take photos or select files',
            style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 16),
          ),
          const SizedBox(height: 8),
          Text(
            'Progress will show here',
            style: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 14),
          ),
        ],
      ),
    );
  }

  Widget _buildFileItem(_UploadingFile file, int index) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.1),
        borderRadius: BorderRadius.circular(14),
        border: file.hasError
            ? Border.all(color: Colors.red.withOpacity(0.5), width: 1)
            : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // File info row
          Row(
            children: [
              // Icon
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: file.hasError
                      ? Colors.red.withOpacity(0.2)
                      : file.isComplete
                          ? const Color(0xFF00B894).withOpacity(0.2)
                          : Colors.white.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  file.hasError
                      ? Icons.error_outline
                      : file.isComplete
                          ? Icons.check_circle
                          : file.name.toLowerCase().endsWith('.pdf')
                              ? Icons.picture_as_pdf
                              : Icons.image,
                  color: file.hasError
                      ? Colors.red
                      : file.isComplete
                          ? const Color(0xFF00B894)
                          : Colors.white70,
                  size: 24,
                ),
              ),
              const SizedBox(width: 14),
              // File details
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      file.name,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      file.hasError
                          ? file.errorMessage ?? 'Upload failed'
                          : file.isComplete
                              ? 'Uploaded • ${file.sizeText}'
                              : '${file.sentText} / ${file.sizeText}',
                      style: TextStyle(
                        color: file.hasError
                            ? Colors.red.shade300
                            : file.isComplete
                                ? const Color(0xFF00B894)
                                : Colors.white60,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              // Progress or status
              if (!file.hasError && !file.isComplete) ...[
                Text(
                  file.progressText,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ] else if (file.hasError) ...[
                IconButton(
                  icon: const Icon(Icons.refresh, color: Colors.white54),
                  onPressed: () => _retryFile(index),
                  tooltip: 'Retry',
                ),
              ],
              IconButton(
                icon: const Icon(Icons.close, color: Colors.white38, size: 20),
                onPressed: () => _removeFile(index),
              ),
            ],
          ),
          // Progress bar
          if (!file.isComplete && !file.hasError) ...[
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: file.progress,
                backgroundColor: Colors.white.withOpacity(0.1),
                valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFF00B894)),
                minHeight: 6,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildCompleteScreen() {
    return Scaffold(
      backgroundColor: const Color(0xFF1E3A5F),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 100,
                height: 100,
                decoration: const BoxDecoration(
                  color: Color(0xFF00B894),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.check, color: Colors.white, size: 56),
              ),
              const SizedBox(height: 32),
              const Text(
                'Documents Sent!',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                '$_completedCount document${_completedCount != 1 ? 's' : ''} uploaded successfully.\nYou can close this screen.',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.white.withOpacity(0.7),
                  fontSize: 16,
                ),
              ),
              const SizedBox(height: 40),
              ElevatedButton.icon(
                onPressed: () => Navigator.of(context).pop(),
                icon: const Icon(Icons.done),
                label: const Text('Close'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: const Color(0xFF1E3A5F),
                  padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildErrorScreen() {
    return Scaffold(
      backgroundColor: const Color(0xFF1E3A5F),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: Colors.red.withOpacity(0.2),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.error_outline, color: Colors.red, size: 48),
              ),
              const SizedBox(height: 24),
              const Text(
                'Session Error',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                _error!,
                style: TextStyle(color: Colors.white.withOpacity(0.7)),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              ElevatedButton(
                onPressed: () => Navigator.of(context).pop(),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: const Color(0xFF1E3A5F),
                ),
                child: const Text('Go Back'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
