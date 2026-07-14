import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import 'dart:io';
import 'package:path_provider/path_provider.dart';
import 'package:open_file/open_file.dart';
import 'package:share_plus/share_plus.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Document Preview Screen - V3 Document Generator
/// Shows generated document with export and edit options
class DocumentPreviewScreen extends StatefulWidget {
  final String documentId;
  final String? assessmentId;

  const DocumentPreviewScreen({
    super.key,
    required this.documentId,
    this.assessmentId,
  });

  @override
  State<DocumentPreviewScreen> createState() => _DocumentPreviewScreenState();
}

class _DocumentPreviewScreenState extends State<DocumentPreviewScreen> {
  bool _isLoading = true;
  Map<String, dynamic>? _document;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadDocument();
  }

  Future<void> _loadDocument() async {
    try {
      setState(() {
        _isLoading = true;
        _error = null;
      });

      final response = await authService.get('/generated-documents/${widget.documentId}');

      if (response.statusCode == 200) {
        _document = jsonDecode(response.body);
      } else {
        _error = 'Failed to load document';
      }

      setState(() => _isLoading = false);
    } catch (e) {
      setState(() {
        _isLoading = false;
        _error = 'Error loading document: $e';
      });
    }
  }

  bool _isExporting = false;

  Future<void> _exportDocument(String format) async {
    if (_isExporting) return;

    // DOCX export not yet supported by backend
    if (format.toLowerCase() == 'docx') {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('DOCX export coming soon. Downloading as PDF instead.'),
          duration: Duration(seconds: 3),
        ),
      );
      // Fall back to PDF
      format = 'pdf';
    }

    setState(() => _isExporting = true);

    try {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Exporting as ${format.toUpperCase()}...')),
      );

      // First finalize the document if not already finalized
      final status = _document?['status'] as String? ?? '';
      if (status != 'finalized') {
        final finalizeRes = await authService.post(
          '/generated-documents/${widget.documentId}/finalize',
          body: {},
        );
        if (finalizeRes.statusCode != 200) {
          throw Exception('Failed to finalize document');
        }
      }

      // Download the PDF (backend only supports PDF for now)
      final response = await authService.get(
        '/generated-documents/${widget.documentId}/download',
      );

      if (!mounted) return;

      if (response.statusCode == 200) {
        // Get downloads directory
        final Directory? downloadsDir = Platform.isAndroid
            ? Directory('/storage/emulated/0/Download')
            : await getApplicationDocumentsDirectory();

        if (downloadsDir == null) {
          throw Exception('Could not access downloads directory');
        }

        // Create filename with timestamp
        final timestamp = DateTime.now().millisecondsSinceEpoch;
        final title = _document?['title'] as String? ?? 'document';
        final sanitizedTitle = title.replaceAll(RegExp(r'[^\w\s-]'), '').replaceAll(' ', '_');
        // Always save as PDF since backend only supports PDF export
        final filename = '${sanitizedTitle}_$timestamp.pdf';
        final filePath = '${downloadsDir.path}/$filename';

        // Write file
        final file = File(filePath);
        await file.writeAsBytes(response.bodyBytes);

        if (!mounted) return;

        // Show success dialog with options (always PDF)
        _showExportSuccessDialog(filePath, 'pdf');
      } else {
        throw Exception('Export failed: ${response.statusCode}');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Export failed: $e'),
            backgroundColor: AppTheme.error,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isExporting = false);
      }
    }
  }

  void _showExportSuccessDialog(String filePath, String format) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppTheme.success.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.check_circle, color: AppTheme.success),
            ),
            const SizedBox(width: 12),
            const Text('Export Successful'),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Your document has been exported as ${format.toUpperCase()}.',
              style: const TextStyle(fontSize: 14),
            ),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppTheme.background,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(
                    format == 'pdf' ? Icons.picture_as_pdf : Icons.description,
                    color: format == 'pdf' ? Colors.red : Colors.blue,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      filePath.split('/').last,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
          TextButton.icon(
            onPressed: () {
              Navigator.pop(context);
              _shareFile(filePath);
            },
            icon: const Icon(Icons.share, size: 18),
            label: const Text('Share'),
          ),
          ElevatedButton.icon(
            onPressed: () {
              Navigator.pop(context);
              _openFile(filePath);
            },
            icon: const Icon(Icons.open_in_new, size: 18),
            label: const Text('Open'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryDark,
              foregroundColor: Colors.white,
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _openFile(String filePath) async {
    try {
      final result = await OpenFile.open(filePath);
      if (result.type != ResultType.done && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Could not open file: ${result.message}'),
            backgroundColor: AppTheme.error,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error opening file: $e'),
            backgroundColor: AppTheme.error,
          ),
        );
      }
    }
  }

  Future<void> _shareFile(String filePath) async {
    try {
      await Share.shareXFiles(
        [XFile(filePath)],
        text: 'Document from InstantRisk',
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error sharing file: $e'),
            backgroundColor: AppTheme.error,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: AppTheme.surface,
        elevation: 0,
        leading: IconButton(
          onPressed: () => context.pop(),
          icon: const Icon(Icons.arrow_back_ios),
          color: AppTheme.textPrimary,
        ),
        title: const Text(
          'Document Ready',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
            fontFamily: 'Inter',
          ),
        ),
        centerTitle: true,
        actions: [
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert, color: AppTheme.textPrimary),
            onSelected: (value) {
              switch (value) {
                case 'pdf':
                  _exportDocument('pdf');
                  break;
                case 'docx':
                  _exportDocument('docx');
                  break;
                case 'edit':
                  context.push('/documents/edit/${widget.documentId}', extra: {
                    'assessmentId': widget.assessmentId,
                  });
                  break;
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'pdf',
                child: Row(
                  children: [
                    Icon(Icons.picture_as_pdf, size: 20),
                    SizedBox(width: 12),
                    Text('Export as PDF'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'docx',
                child: Row(
                  children: [
                    Icon(Icons.description, size: 20),
                    SizedBox(width: 12),
                    Text('Export as DOCX'),
                  ],
                ),
              ),
              const PopupMenuDivider(),
              const PopupMenuItem(
                value: 'edit',
                child: Row(
                  children: [
                    Icon(Icons.edit, size: 20),
                    SizedBox(width: 12),
                    Text('Edit Document'),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildErrorState()
              : _buildContent(),
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.error_outline,
              size: 64,
              color: AppTheme.error.withOpacity(0.5),
            ),
            const SizedBox(height: 16),
            Text(
              _error ?? 'Unknown error',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 16,
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _loadDocument,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent() {
    final title = _document?['title'] as String? ?? 'Untitled Document';
    final status = _document?['status'] as String? ?? 'draft';
    final confidence = (_document?['ai_confidence'] as num?)?.toDouble() ?? 0.0;
    // Parse draft_content sections if available, otherwise fallback to content string
    String content = '';
    final draftContent = _document?['draft_content'];
    if (draftContent != null && draftContent is Map) {
      final sections = draftContent['sections'] as List<dynamic>? ?? [];
      content = sections.map((section) {
        final heading = section['heading'] as String? ?? '';
        final body = section['content'] as String? ?? '';
        return heading.isNotEmpty ? '$heading\n\n$body' : body;
      }).join('\n\n');
    } else {
      content = _document?['content'] as String? ?? '';
    }
    final placeholders = _document?['placeholders_remaining'] as int? ?? 0;

    Color statusColor;
    switch (status) {
      case 'finalized':
        statusColor = AppTheme.success;
        break;
      case 'approved':
        statusColor = AppTheme.info;
        break;
      case 'review_required':
        statusColor = AppTheme.warning;
        break;
      default:
        statusColor = AppTheme.textSecondary;
    }

    return Column(
      children: [
        // Success header
        Container(
          padding: const EdgeInsets.all(16),
          color: AppTheme.success.withOpacity(0.1),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppTheme.success.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(
                  Icons.check_circle,
                  color: AppTheme.success,
                  size: 24,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Document Generated Successfully',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.success,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        const Text(
                          'AI Quality Score: ',
                          style: TextStyle(
                            fontSize: 13,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                        Text(
                          '${(confidence * 100).toInt()}%',
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.success,
                          ),
                        ),
                        const SizedBox(width: 16),
                        const Icon(
                          Icons.verified,
                          size: 14,
                          color: AppTheme.success,
                        ),
                        const SizedBox(width: 4),
                        const Text(
                          'Compliance Passed',
                          style: TextStyle(
                            fontSize: 12,
                            color: AppTheme.success,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),

        // Warning if placeholders remain
        if (placeholders > 0)
          Container(
            padding: const EdgeInsets.all(12),
            color: AppTheme.warning.withOpacity(0.1),
            child: Row(
              children: [
                Icon(
                  Icons.warning_amber,
                  color: AppTheme.warning,
                  size: 20,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    '$placeholders placeholder${placeholders > 1 ? 's' : ''} need attention',
                    style: TextStyle(
                      fontSize: 13,
                      color: AppTheme.warning,
                    ),
                  ),
                ),
                TextButton(
                  onPressed: () {
                    context.push('/documents/edit/${widget.documentId}', extra: {
                      'assessmentId': widget.assessmentId,
                    });
                  },
                  child: const Text('Fix Now'),
                ),
              ],
            ),
          ),

        // Document preview
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.border),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.05),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Document header
                  Center(
                    child: Column(
                      children: [
                        Text(
                          title.toUpperCase(),
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.textPrimary,
                            letterSpacing: 1.2,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: statusColor.withOpacity(0.1),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            status.toUpperCase().replaceAll('_', ' '),
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: statusColor,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),
                  const Divider(),
                  const SizedBox(height: 24),

                  // Document content preview
                  if (content.isNotEmpty)
                    Text(
                      content,
                      style: const TextStyle(
                        fontSize: 13,
                        height: 1.6,
                        color: AppTheme.textPrimary,
                      ),
                    )
                  else
                    Center(
                      child: Column(
                        children: [
                          Icon(
                            Icons.article_outlined,
                            size: 48,
                            color: AppTheme.textHint.withOpacity(0.5),
                          ),
                          const SizedBox(height: 12),
                          const Text(
                            'Document content will be displayed here',
                            style: TextStyle(
                              fontSize: 14,
                              color: AppTheme.textSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),

        // Action bar
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.surface,
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.05),
                blurRadius: 10,
                offset: const Offset(0, -4),
              ),
            ],
          ),
          child: SafeArea(
            child: Row(
              children: [
                // Export buttons
                Expanded(
                  child: Row(
                    children: [
                      _buildExportButton(
                        icon: Icons.picture_as_pdf,
                        label: 'PDF',
                        onTap: () => _exportDocument('pdf'),
                      ),
                      const SizedBox(width: 8),
                      _buildExportButton(
                        icon: Icons.description,
                        label: 'DOCX',
                        onTap: () => _exportDocument('docx'),
                      ),
                      const SizedBox(width: 8),
                      _buildExportButton(
                        icon: Icons.edit,
                        label: 'Edit',
                        onTap: () {
                          context.push('/documents/edit/${widget.documentId}', extra: {
                            'assessmentId': widget.assessmentId,
                          });
                        },
                      ),
                    ],
                  ),
                ),

                const SizedBox(width: 16),

                // Done button
                ElevatedButton(
                  onPressed: () => context.go('/documents'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryDark,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 24,
                      vertical: 14,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.check, color: Colors.white, size: 20),
                      SizedBox(width: 8),
                      Text(
                        'Done',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildExportButton({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return Material(
      color: AppTheme.background,
      borderRadius: BorderRadius.circular(10),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(10),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            border: Border.all(color: AppTheme.border),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 18, color: AppTheme.textSecondary),
              const SizedBox(width: 6),
              Text(
                label,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
