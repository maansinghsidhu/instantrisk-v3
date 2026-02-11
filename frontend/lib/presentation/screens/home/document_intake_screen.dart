import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:go_router/go_router.dart';
import 'package:file_picker/file_picker.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:qr_flutter/qr_flutter.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Document Intake Screen - Upload and manage documents for assessment
class DocumentIntakeScreen extends StatefulWidget {
  const DocumentIntakeScreen({super.key});

  @override
  State<DocumentIntakeScreen> createState() => _DocumentIntakeScreenState();
}

class _DocumentIntakeScreenState extends State<DocumentIntakeScreen> {
  final List<UploadedDocument> _documents = [];
  bool _isUploading = false;
  bool _isCreatingSession = false;
  String? _qrUrl;
  String? _qrToken;
  bool _isPolling = false;
  final ImagePicker _imagePicker = ImagePicker();

  @override
  void initState() {
    super.initState();
    _checkAuth();
  }

  void _checkAuth() {
    if (!authService.isLoggedIn) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          context.go('/login');
        }
      });
    }
  }

  Future<void> _showQRCodeForMobileUpload() async {
    setState(() => _isCreatingSession = true);

    try {
      final response = await authService.post('/upload-sessions/demo');

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = jsonDecode(response.body);
        setState(() {
          _qrToken = data['token'];
          _qrUrl = data['qr_url'];
        });
        if (mounted) {
          _showQRDialog();
        }
      } else if (response.statusCode == 401) {
        if (mounted) {
          context.go('/login');
        }
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Failed to create upload session')),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    }

    setState(() => _isCreatingSession = false);
  }

  Future<void> _pollForUploads(Function(int, List<dynamic>) onUpdate, Function() onComplete) async {
    _isPolling = true;
    int lastCount = 0;

    while (_isPolling && _qrToken != null) {
      try {
        final response = await authService.get('/upload-sessions/${_qrToken!}/status');

        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);
          final documents = data['documents'] as List<dynamic>? ?? [];
          final status = data['status'] as String?;

          if (documents.length != lastCount) {
            lastCount = documents.length;
            onUpdate(lastCount, documents);
          }

          if (status == 'complete') {
            _isPolling = false;
            onComplete();
            break;
          }
        } else if (response.statusCode == 401) {
          _isPolling = false;
          break;
        }
      } catch (e) {
        // Ignore polling errors, just continue
      }

      if (_isPolling) {
        await Future.delayed(const Duration(seconds: 2));
      }
    }
  }

  void _stopPolling() {
    _isPolling = false;
  }

  void _showQRDialog() {
    int uploadedCount = 0;
    List<dynamic> uploadedDocs = [];

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) {
          // Start polling when dialog opens
          if (!_isPolling && _qrToken != null) {
            _pollForUploads(
              (count, docs) {
                setDialogState(() {
                  uploadedCount = count;
                  uploadedDocs = docs;
                });
              },
              () {
                // Auto-close and add documents
                Navigator.pop(ctx);
                _addDocumentsFromSession(uploadedDocs);
              },
            );
          }

          return AlertDialog(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
            title: Row(
              children: [
                Icon(Icons.phone_android, color: AppTheme.primaryDark),
                const SizedBox(width: 12),
                const Text('Upload from Phone'),
              ],
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 220,
                  height: 220,
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.border, width: 2),
                  ),
                  child: _qrUrl != null
                      ? QrImageView(
                          data: _qrUrl!,
                          version: QrVersions.auto,
                          size: 200,
                          backgroundColor: Colors.white,
                          errorCorrectionLevel: QrErrorCorrectLevel.M,
                        )
                      : const Center(child: CircularProgressIndicator()),
                ),
                const SizedBox(height: 16),
                if (uploadedCount > 0)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    decoration: BoxDecoration(
                      color: AppTheme.success.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppTheme.success.withOpacity(0.3)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.check_circle, color: AppTheme.success, size: 20),
                        const SizedBox(width: 8),
                        Text(
                          '$uploadedCount document${uploadedCount > 1 ? 's' : ''} received',
                          style: const TextStyle(
                            color: AppTheme.success,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  )
                else
                  const Text(
                    'Scan with your phone camera\nto capture and upload documents',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: AppTheme.textSecondary, fontSize: 14),
                  ),
                const SizedBox(height: 12),
                if (_qrUrl != null && uploadedCount == 0)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryDark.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: SelectableText(
                      _qrUrl!,
                      style: TextStyle(fontSize: 10, color: AppTheme.primaryDark),
                      textAlign: TextAlign.center,
                    ),
                  ),
              ],
            ),
            actions: [
              if (uploadedCount > 0)
                ElevatedButton(
                  onPressed: () {
                    _stopPolling();
                    Navigator.pop(ctx);
                    _addDocumentsFromSession(uploadedDocs);
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryDark,
                    foregroundColor: Colors.white,
                  ),
                  child: Text('Done ($uploadedCount)'),
                )
              else
                TextButton(
                  onPressed: () {
                    _stopPolling();
                    Navigator.pop(ctx);
                  },
                  child: const Text('Cancel'),
                ),
            ],
          );
        },
      ),
    ).then((_) => _stopPolling());
  }

  void _addDocumentsFromSession(List<dynamic> docs) {
    for (final doc in docs) {
      final filename = doc['filename'] as String? ?? 'document';
      final url = doc['url'] as String? ?? '';
      final ext = filename.split('.').last.toUpperCase();

      setState(() {
        _documents.add(UploadedDocument(
          name: filename,
          size: 'From phone',
          type: ext,
          path: url,
        ));
      });
    }

    if (docs.isNotEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('${docs.length} document${docs.length > 1 ? 's' : ''} added from phone'),
          backgroundColor: AppTheme.success,
        ),
      );
    }
  }

  Future<void> _pickFiles() async {
    setState(() => _isUploading = true);

    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        allowMultiple: true,
        type: FileType.custom,
        allowedExtensions: ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'png', 'jpg', 'jpeg'],
        withData: kIsWeb, // On web, we need bytes since path is unavailable
      );

      if (result != null) {
        for (var file in result.files) {
          final sizeInMB = (file.size / (1024 * 1024)).toStringAsFixed(2);
          setState(() {
            _documents.add(UploadedDocument(
              name: file.name,
              size: '$sizeInMB MB',
              type: file.extension?.toUpperCase() ?? 'FILE',
              bytes: file.bytes,
              path: kIsWeb ? null : file.path, // path is unavailable on web
            ));
          });
        }
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error picking files: $e'),
          backgroundColor: AppTheme.danger,
        ),
      );
    }

    setState(() => _isUploading = false);
  }

  Future<void> _takePhoto() async {
    setState(() => _isUploading = true);

    try {
      final XFile? photo = await _imagePicker.pickImage(
        source: ImageSource.camera,
        imageQuality: 85,
        maxWidth: 1920,
        maxHeight: 1920,
      );

      if (photo != null) {
        final bytes = await photo.readAsBytes();
        final sizeInMB = (bytes.length / (1024 * 1024)).toStringAsFixed(2);
        setState(() {
          _documents.add(UploadedDocument(
            name: 'Photo_${DateTime.now().millisecondsSinceEpoch}.jpg',
            size: '$sizeInMB MB',
            type: 'JPG',
            bytes: bytes,
            path: photo.path,
          ));
        });
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error taking photo: $e'),
          backgroundColor: AppTheme.danger,
        ),
      );
    }

    setState(() => _isUploading = false);
  }

  Future<void> _pickFromGallery() async {
    setState(() => _isUploading = true);

    try {
      final List<XFile> images = await _imagePicker.pickMultiImage(
        imageQuality: 85,
        maxWidth: 1920,
        maxHeight: 1920,
      );

      for (var image in images) {
        final bytes = await image.readAsBytes();
        final sizeInMB = (bytes.length / (1024 * 1024)).toStringAsFixed(2);
        final ext = image.path.split('.').last.toUpperCase();
        setState(() {
          _documents.add(UploadedDocument(
            name: image.name,
            size: '$sizeInMB MB',
            type: ext,
            bytes: bytes,
            path: image.path,
          ));
        });
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error picking images: $e'),
          backgroundColor: AppTheme.danger,
        ),
      );
    }

    setState(() => _isUploading = false);
  }

  void _showUploadOptions() {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => Container(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppTheme.border,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 24),
            const Text(
              'Add Documents',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 24),
            // On web, show QR code option instead of camera
            if (kIsWeb) ...[
              _buildOptionTile(
                icon: Icons.qr_code_scanner,
                title: 'Scan QR with Phone',
                subtitle: 'Use phone camera to capture documents',
                onTap: () {
                  Navigator.pop(context);
                  _showQRCodeForMobileUpload();
                },
                isLoading: _isCreatingSession,
              ),
            ] else ...[
              _buildOptionTile(
                icon: Icons.camera_alt_outlined,
                title: 'Take Photo',
                subtitle: 'Capture document with camera',
                onTap: () {
                  Navigator.pop(context);
                  _takePhoto();
                },
              ),
              const SizedBox(height: 12),
              _buildOptionTile(
                icon: Icons.photo_library_outlined,
                title: 'Photo Gallery',
                subtitle: 'Select from your photos',
                onTap: () {
                  Navigator.pop(context);
                  _pickFromGallery();
                },
              ),
            ],
            const SizedBox(height: 12),
            _buildOptionTile(
              icon: Icons.folder_outlined,
              title: 'Browse Files',
              subtitle: 'PDF, DOC, XLS and more',
              onTap: () {
                Navigator.pop(context);
                _pickFiles();
              },
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  Widget _buildOptionTile({
    required IconData icon,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
    bool isLoading = false,
  }) {
    return InkWell(
      onTap: isLoading ? null : onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.border),
        ),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: AppTheme.primaryDark.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: isLoading
                  ? const Padding(
                      padding: EdgeInsets.all(12),
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Icon(icon, color: AppTheme.primaryDark, size: 24),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      fontSize: 13,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(Icons.arrow_forward_ios, color: AppTheme.textHint, size: 16),
          ],
        ),
      ),
    );
  }

  void _removeDocument(int index) {
    setState(() {
      _documents.removeAt(index);
    });
  }

  Future<void> _startProcessing() async {
    if (_documents.isEmpty) return;

    if (!authService.isLoggedIn) {
      context.go('/login');
      return;
    }

    setState(() => _isUploading = true);

    try {
      String token;

      // If we have a QR token with docs already uploaded, use that
      if (_qrToken != null && _documents.any((d) => d.path?.startsWith('http') == true)) {
        token = _qrToken!;
      } else {
        // Create new upload session
        final sessionResponse = await authService.post('/upload-sessions/demo');

        if (sessionResponse.statusCode == 401) {
          if (mounted) {
            context.go('/login');
          }
          return;
        }

        if (sessionResponse.statusCode != 200 && sessionResponse.statusCode != 201) {
          throw Exception('Failed to create session');
        }

        final sessionData = jsonDecode(sessionResponse.body);
        token = sessionData['token'] as String;
      }

      // Upload documents that aren't already uploaded (not from QR)
      for (final doc in _documents) {
        // Skip docs from QR session (they have http URLs)
        if (doc.path?.startsWith('http') == true) continue;

        if (doc.bytes != null) {
          // Upload from bytes (web) - use authenticated upload
          await authService.uploadFileBytes(
            '/upload-sessions/$token/upload',
            doc.bytes!,
            doc.name,
            'file',
          );
        } else if (doc.path != null) {
          // Upload from file path (mobile) - use authenticated upload
          await authService.uploadFile(
            '/upload-sessions/$token/upload',
            doc.path!,
            'file',
          );
        }
      }

      // Start deep analysis directly (skip mode selection)
      final processResponse = await authService.post(
        '/upload-sessions/$token/process-async?mode=deep',
      );

      if (processResponse.statusCode == 200) {
        final processData = jsonDecode(processResponse.body);
        final assessmentId = processData['assessment_id']?.toString() ?? token;
        final sessionId = processData['session_id']?.toString();

        // Navigate directly to results screen with processing flag
        if (mounted) {
          context.go(
            '/assessments/$assessmentId/results',
            extra: {
              'isProcessing': true,
              'sessionId': sessionId,
              'sessionToken': token,
              'documentCount': _documents.length,
            },
          );
        }
      } else {
        throw Exception('Failed to start analysis: ${processResponse.statusCode}');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload failed: $e'), backgroundColor: AppTheme.danger),
        );
      }
    }

    setState(() => _isUploading = false);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppTheme.textPrimary),
          onPressed: () => context.go('/home'),
        ),
        title: Text(
          l10n.newAssessment,
          style: const TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
            fontFamily: 'Inter',
          ),
        ),
        centerTitle: true,
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(20.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // AI Auto-Detection Info
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            AppTheme.primaryDark.withOpacity(0.1),
                            AppTheme.accent.withOpacity(0.1),
                          ],
                        ),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppTheme.primaryDark.withOpacity(0.2)),
                      ),
                      child: Row(
                        children: [
                          Container(
                            width: 40,
                            height: 40,
                            decoration: BoxDecoration(
                              color: AppTheme.primaryDark.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: const Icon(
                              Icons.auto_awesome,
                              color: AppTheme.primaryDark,
                              size: 20,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  l10n.aiPoweredAnalysis,
                                  style: const TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w600,
                                    color: AppTheme.textPrimary,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  l10n.riskTypeAutoDetected,
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: AppTheme.textSecondary,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),

                    // Upload Section
                    Text(
                      l10n.uploadDocuments,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textPrimary,
                        fontFamily: 'Inter',
                      ),
                    ),
                    const SizedBox(height: 12),

                    // Upload Area
                    InkWell(
                      onTap: _isUploading ? null : _showUploadOptions,
                      borderRadius: BorderRadius.circular(16),
                      child: Container(
                        width: double.infinity,
                        padding: const EdgeInsets.symmetric(vertical: 40),
                        decoration: BoxDecoration(
                          color: AppTheme.primaryDark.withOpacity(0.05),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                            color: AppTheme.primaryDark.withOpacity(0.2),
                            width: 2,
                            strokeAlign: BorderSide.strokeAlignInside,
                          ),
                        ),
                        child: Column(
                          children: [
                            Container(
                              width: 64,
                              height: 64,
                              decoration: BoxDecoration(
                                color: AppTheme.primaryDark.withOpacity(0.1),
                                shape: BoxShape.circle,
                              ),
                              child: _isUploading
                                  ? const Padding(
                                      padding: EdgeInsets.all(16.0),
                                      child: CircularProgressIndicator(
                                        color: AppTheme.primaryDark,
                                        strokeWidth: 3,
                                      ),
                                    )
                                  : const Icon(
                                      Icons.add_photo_alternate_outlined,
                                      color: AppTheme.primaryDark,
                                      size: 32,
                                    ),
                            ),
                            const SizedBox(height: 16),
                            Text(
                              _isUploading ? l10n.processing : l10n.tapToAddDocuments,
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                                color: AppTheme.primaryDark,
                                fontFamily: 'Inter',
                              ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              l10n.takePhotoBrowseOrGallery,
                              style: const TextStyle(
                                fontSize: 14,
                                color: AppTheme.textSecondary,
                                fontFamily: 'Inter',
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),

                    // Uploaded Documents List
                    if (_documents.isNotEmpty) ...[
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            l10n.uploadedDocuments,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.textPrimary,
                              fontFamily: 'Inter',
                            ),
                          ),
                          Text(
                            l10n.filesCount(_documents.length),
                            style: const TextStyle(
                              fontSize: 14,
                              color: AppTheme.textSecondary,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      ...List.generate(
                        _documents.length,
                        (index) => _buildDocumentItem(_documents[index], index),
                      ),
                    ],

                    // Required Documents Info
                    const SizedBox(height: 24),
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: AppTheme.info.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        children: [
                          const Icon(
                            Icons.info_outline,
                            color: AppTheme.info,
                            size: 24,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  l10n.recommendedDocuments,
                                  style: const TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w600,
                                    color: AppTheme.textPrimary,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  l10n.applicationFormLossHistory,
                                  style: const TextStyle(
                                    fontSize: 13,
                                    color: AppTheme.textSecondary,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Bottom Action Button
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.05),
                    blurRadius: 10,
                    offset: const Offset(0, -5),
                  ),
                ],
              ),
              child: SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _documents.isNotEmpty ? _startProcessing : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryDark,
                    foregroundColor: Colors.white,
                    disabledBackgroundColor: AppTheme.border,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.analytics_outlined, size: 20),
                      const SizedBox(width: 8),
                      Text(
                        l10n.startRiskAssessment,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDocumentItem(UploadedDocument doc, int index) {
    IconData iconData;
    Color iconColor;

    switch (doc.type.toLowerCase()) {
      case 'pdf':
        iconData = Icons.picture_as_pdf;
        iconColor = AppTheme.danger;
        break;
      case 'doc':
      case 'docx':
        iconData = Icons.description;
        iconColor = AppTheme.info;
        break;
      case 'xls':
      case 'xlsx':
        iconData = Icons.table_chart;
        iconColor = AppTheme.success;
        break;
      case 'jpg':
      case 'jpeg':
      case 'png':
        iconData = Icons.image;
        iconColor = AppTheme.accent;
        break;
      default:
        iconData = Icons.insert_drive_file;
        iconColor = AppTheme.textSecondary;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: iconColor.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              iconData,
              color: iconColor,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  doc.name,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    color: AppTheme.textPrimary,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  '${doc.type} • ${doc.size}',
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(
              Icons.close,
              color: AppTheme.textSecondary,
              size: 20,
            ),
            onPressed: () => _removeDocument(index),
          ),
        ],
      ),
    );
  }
}

class UploadedDocument {
  final String name;
  final String size;
  final String type;
  final List<int>? bytes;
  final String? path;

  UploadedDocument({
    required this.name,
    required this.size,
    required this.type,
    this.bytes,
    this.path,
  });
}
