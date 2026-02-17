import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:io';
import 'dart:typed_data';

import '../../../core/theme/app_theme.dart';
import '../../../core/services/chat_service.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/api_service.dart';

/// Chat with Documents Screen - Split-screen chat with document viewer
/// Documents on one side, chat on the other
class ChatWithDocumentsScreen extends StatefulWidget {
  final String? conversationId;

  const ChatWithDocumentsScreen({
    super.key,
    this.conversationId,
  });

  @override
  State<ChatWithDocumentsScreen> createState() => _ChatWithDocumentsScreenState();
}

class _ChatWithDocumentsScreenState extends State<ChatWithDocumentsScreen> {
  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final ChatService _chatService = ChatService();
  final AuthService _authService = AuthService();
  final ApiService _apiService = ApiService();

  List<_ChatMessage> _messages = [];
  List<_DocumentFile> _documents = [];
  int? _selectedDocumentIndex;
  String? _conversationId;
  bool _isLoading = false;
  bool _isStreaming = false;
  bool _isUploadingDoc = false;
  String _thinkingMessage = '';
  String _streamingResponse = '';
  List<Map<String, dynamic>> _currentSources = [];

  // Assessment selection
  List<Map<String, dynamic>> _assessments = [];
  String? _selectedAssessmentId;
  bool _isLoadingAssessments = false;

  @override
  void initState() {
    super.initState();
    _conversationId = widget.conversationId;
    _loadAssessments();
    _showWelcomeMessage();
  }

  Future<void> _loadAssessments() async {
    setState(() => _isLoadingAssessments = true);
    try {
      final response = await _apiService.get('/assessments/?page_size=50');
      if (response != null && response['items'] != null) {
        setState(() {
          _assessments = List<Map<String, dynamic>>.from(response['items']);
        });
      }
    } catch (e) {
      debugPrint('Failed to load assessments: $e');
    } finally {
      setState(() => _isLoadingAssessments = false);
    }
  }

  void _showWelcomeMessage() {
    setState(() {
      _messages = [
        _ChatMessage(
          text: '''Hello! I can help you analyze documents and answer questions about them.

**Upload documents** on the left panel, then ask me questions like:
- "What are the key terms in this policy?"
- "Summarize the coverage limits"
- "Are there any exclusions I should be aware of?"

Let's get started!''',
          isUser: false,
          timestamp: DateTime.now(),
        ),
      ];
    });
  }

  Future<void> _pickDocument() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf', 'doc', 'docx', 'txt', 'png', 'jpg', 'jpeg'],
        allowMultiple: true,
        withData: true, // Required for web to get file bytes
      );

      if (result != null && result.files.isNotEmpty) {
        setState(() => _isUploadingDoc = true);

        int addedCount = 0;
        for (final file in result.files) {
          // On web, path is null but we have bytes
          // On native, we have path
          final docFile = _DocumentFile(
            name: file.name,
            path: file.path ?? '', // Empty string for web
            size: file.size,
            extension: file.extension ?? '',
            bytes: file.bytes, // Store bytes for web upload
          );

          setState(() {
            _documents.add(docFile);
            _selectedDocumentIndex = _documents.length - 1;
          });
          addedCount++;
        }

        setState(() => _isUploadingDoc = false);

        // Notify the chat
        if (addedCount > 0) {
          setState(() {
            _messages.add(_ChatMessage(
              text: 'Added $addedCount document(s): ${result.files.map((f) => f.name).join(", ")}.\n\nYou can now ask me questions about them!',
              isUser: false,
              timestamp: DateTime.now(),
              isSystem: true,
            ));
          });
          _scrollToBottom();
        }
      }
    } catch (e) {
      setState(() => _isUploadingDoc = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error picking file: $e'), backgroundColor: Colors.red),
      );
    }
  }

  void _removeDocument(int index) {
    setState(() {
      _documents.removeAt(index);
      if (_selectedDocumentIndex == index) {
        _selectedDocumentIndex = _documents.isNotEmpty ? 0 : null;
      } else if (_selectedDocumentIndex != null && _selectedDocumentIndex! > index) {
        _selectedDocumentIndex = _selectedDocumentIndex! - 1;
      }
    });
  }

  Future<void> _sendMessage() async {
    final text = _messageController.text.trim();
    if (text.isEmpty || _isStreaming) return;

    // Add user message
    setState(() {
      _messages.add(_ChatMessage(
        text: text,
        isUser: true,
        timestamp: DateTime.now(),
      ));
      _isStreaming = true;
      _thinkingMessage = 'Analyzing documents...';
      _streamingResponse = '';
      _currentSources = [];
    });

    _messageController.clear();
    _scrollToBottom();

    // Build message history with document context
    final messageHistory = _messages
        .where((m) => m.text.isNotEmpty && !m.isSystem)
        .map((m) => {
              'role': m.isUser ? 'user' : 'assistant',
              'content': m.text,
            })
        .toList();

    // Add document context to the message if documents are uploaded
    String documentContext = '';
    if (_documents.isNotEmpty) {
      documentContext = '\n\n[User has uploaded ${_documents.length} document(s): ${_documents.map((d) => d.name).join(", ")}]';
    }

    try {
      await for (final event in _chatService.streamChat(
        messages: messageHistory,
        conversationId: _conversationId,
        useRag: true,
        documentContext: documentContext,
        assessmentId: _selectedAssessmentId,
      )) {
        if (event is ChatEventStart) {
          setState(() {
            _conversationId = event.conversationId;
            _thinkingMessage = 'Thinking...';
          });
        } else if (event is ChatEventThinking) {
          setState(() {
            _thinkingMessage = event.message;
          });
        } else if (event is ChatEventSources) {
          setState(() {
            _currentSources = event.sources;
            _thinkingMessage = 'Found ${event.sources.length} relevant sources...';
          });
        } else if (event is ChatEventToken) {
          setState(() {
            _thinkingMessage = '';
            _streamingResponse += event.content;
          });
          _scrollToBottom();
        } else if (event is ChatEventDone) {
          setState(() {
            _messages.add(_ChatMessage(
              text: _streamingResponse,
              isUser: false,
              timestamp: DateTime.now(),
              sources: _currentSources,
            ));
            _isStreaming = false;
            _streamingResponse = '';
            _thinkingMessage = '';
          });
        } else if (event is ChatEventError) {
          setState(() {
            _messages.add(_ChatMessage(
              text: 'Error: ${event.message}',
              isUser: false,
              timestamp: DateTime.now(),
              isError: true,
            ));
            _isStreaming = false;
            _streamingResponse = '';
            _thinkingMessage = '';
          });
        }
      }
    } catch (e) {
      setState(() {
        _messages.add(_ChatMessage(
          text: 'Connection error. Please try again.',
          isUser: false,
          timestamp: DateTime.now(),
          isError: true,
        ));
        _isStreaming = false;
        _streamingResponse = '';
        _thinkingMessage = '';
      });
    }

    _scrollToBottom();
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;
    final isWideScreen = screenWidth > 800;

    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceOf(context),
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_ios, color: AppTheme.text1(context)),
          onPressed: () => context.pop(),
        ),
        title: Text(
          'Chat with Documents',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.text1(context),
          ),
        ),
        centerTitle: true,
        actions: [
          // Assessment selector dropdown
          if (_assessments.isNotEmpty)
            Container(
              margin: const EdgeInsets.only(right: 8),
              padding: const EdgeInsets.symmetric(horizontal: 8),
              decoration: BoxDecoration(
                color: AppTheme.primaryDark.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<String>(
                  value: _selectedAssessmentId,
                  hint: Text(
                    'Select Assessment',
                    style: TextStyle(fontSize: 12, color: AppTheme.text2(context)),
                  ),
                  icon: const Icon(Icons.arrow_drop_down, size: 20),
                  isDense: true,
                  items: [
                    const DropdownMenuItem<String>(
                      value: null,
                      child: Text('All Documents', style: TextStyle(fontSize: 12)),
                    ),
                    ..._assessments.map((a) => DropdownMenuItem<String>(
                      value: a['id']?.toString(),
                      child: SizedBox(
                        width: 150,
                        child: Text(
                          a['title'] ?? a['reference_number'] ?? 'Assessment',
                          style: const TextStyle(fontSize: 12),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    )),
                  ],
                  onChanged: (value) {
                    setState(() => _selectedAssessmentId = value);
                    if (value != null) {
                      // Add system message about assessment context
                      setState(() {
                        _messages.add(_ChatMessage(
                          text: 'Now chatting with assessment: ${_assessments.firstWhere((a) => a["id"]?.toString() == value)["title"] ?? value}',
                          isUser: false,
                          timestamp: DateTime.now(),
                          isSystem: true,
                        ));
                      });
                      _scrollToBottom();
                    }
                  },
                ),
              ),
            ),
          if (_documents.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Chip(
                label: Text(
                  '${_documents.length} doc${_documents.length > 1 ? 's' : ''}',
                  style: const TextStyle(fontSize: 12),
                ),
                backgroundColor: AppTheme.primaryDark.withOpacity(0.1),
              ),
            ),
        ],
      ),
      body: isWideScreen
          ? _buildWideLayout()
          : _buildNarrowLayout(),
    );
  }

  /// Wide screen layout (tablet/desktop): side-by-side
  Widget _buildWideLayout() {
    return Row(
      children: [
        // Documents panel (left)
        Container(
          width: 320,
          decoration: BoxDecoration(
            color: AppTheme.surfaceOf(context),
            border: Border(right: BorderSide(color: AppTheme.borderOf(context))),
          ),
          child: _buildDocumentsPanel(),
        ),
        // Chat panel (right)
        Expanded(
          child: _buildChatPanel(),
        ),
      ],
    );
  }

  /// Narrow screen layout (phone): stacked with collapsible documents
  Widget _buildNarrowLayout() {
    return Column(
      children: [
        // Documents panel (collapsible top)
        AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          height: _documents.isEmpty ? 120 : 180,
          decoration: BoxDecoration(
            color: AppTheme.surfaceOf(context),
            border: Border(bottom: BorderSide(color: AppTheme.borderOf(context))),
          ),
          child: _buildDocumentsPanel(compact: true),
        ),
        // Chat panel (bottom)
        Expanded(
          child: _buildChatPanel(),
        ),
      ],
    );
  }

  Widget _buildDocumentsPanel({bool compact = false}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              const Icon(Icons.folder_outlined, color: AppTheme.primaryDark),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Documents',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.text1(context),
                  ),
                ),
              ),
              // Add document button
              InkWell(
                onTap: _isUploadingDoc ? null : _pickDocument,
                borderRadius: BorderRadius.circular(8),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryDark,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: _isUploadingDoc
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            color: Colors.white,
                            strokeWidth: 2,
                          ),
                        )
                      : const Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.add, color: Colors.white, size: 18),
                            SizedBox(width: 4),
                            Text(
                              'Add',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ],
                        ),
                ),
              ),
            ],
          ),
        ),

        // Documents list
        Expanded(
          child: _documents.isEmpty
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.upload_file,
                          size: compact ? 32 : 48,
                          color: AppTheme.textH(context),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Upload documents to analyze',
                          style: TextStyle(
                            fontSize: compact ? 12 : 14,
                            color: AppTheme.text2(context),
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  scrollDirection: compact ? Axis.horizontal : Axis.vertical,
                  itemCount: _documents.length,
                  itemBuilder: (context, index) {
                    final doc = _documents[index];
                    final isSelected = _selectedDocumentIndex == index;

                    if (compact) {
                      // Compact horizontal card
                      return Container(
                        width: 140,
                        margin: const EdgeInsets.only(right: 8, bottom: 8),
                        child: _buildDocumentCard(doc, index, isSelected, compact: true),
                      );
                    }

                    // Full vertical card
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: _buildDocumentCard(doc, index, isSelected),
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildDocumentCard(_DocumentFile doc, int index, bool isSelected, {bool compact = false}) {
    return GestureDetector(
      onTap: () => setState(() => _selectedDocumentIndex = index),
      child: Container(
        padding: EdgeInsets.all(compact ? 10 : 12),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.primaryDark.withOpacity(0.1) : AppTheme.bg(context),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? AppTheme.primaryDark : AppTheme.borderOf(context),
            width: isSelected ? 2 : 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Icon(
                  _getDocumentIcon(doc.extension),
                  color: AppTheme.primaryDark,
                  size: compact ? 20 : 24,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    doc.name,
                    style: TextStyle(
                      fontSize: compact ? 12 : 14,
                      fontWeight: FontWeight.w500,
                      color: AppTheme.text1(context),
                    ),
                    maxLines: compact ? 1 : 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                InkWell(
                  onTap: () => _removeDocument(index),
                  child: Icon(
                    Icons.close,
                    size: compact ? 16 : 18,
                    color: AppTheme.textH(context),
                  ),
                ),
              ],
            ),
            if (!compact) ...[
              const SizedBox(height: 4),
              Text(
                _formatFileSize(doc.size),
                style: TextStyle(
                  fontSize: 12,
                  color: AppTheme.text2(context),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  IconData _getDocumentIcon(String extension) {
    switch (extension.toLowerCase()) {
      case 'pdf':
        return Icons.picture_as_pdf;
      case 'doc':
      case 'docx':
        return Icons.description;
      case 'png':
      case 'jpg':
      case 'jpeg':
        return Icons.image;
      default:
        return Icons.insert_drive_file;
    }
  }

  String _formatFileSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  Widget _buildChatPanel() {
    return Column(
      children: [
        // Messages
        Expanded(
          child: _isLoading
              ? const Center(child: CircularProgressIndicator())
              : ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(16),
                  itemCount: _messages.length + (_isStreaming ? 1 : 0),
                  itemBuilder: (context, index) {
                    if (index == _messages.length && _isStreaming) {
                      // Streaming response
                      return _buildStreamingMessage();
                    }
                    return _buildMessageBubble(_messages[index]);
                  },
                ),
        ),

        // Input area
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.surfaceOf(context),
            border: Border(top: BorderSide(color: AppTheme.borderOf(context))),
          ),
          child: SafeArea(
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _messageController,
                    decoration: InputDecoration(
                      hintText: 'Ask about your documents...',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: BorderSide.none,
                      ),
                      filled: true,
                      fillColor: AppTheme.bg(context),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 20,
                        vertical: 12,
                      ),
                    ),
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => _sendMessage(),
                  ),
                ),
                const SizedBox(width: 12),
                Container(
                  decoration: BoxDecoration(
                    color: AppTheme.primaryDark,
                    shape: BoxShape.circle,
                  ),
                  child: IconButton(
                    icon: const Icon(Icons.send, color: Colors.white),
                    onPressed: _isStreaming ? null : _sendMessage,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildMessageBubble(_ChatMessage message) {
    final isUser = message.isUser;
    final isError = message.isError;
    final isSystem = message.isSystem;

    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) ...[
            CircleAvatar(
              radius: 16,
              backgroundColor: isError
                  ? AppTheme.danger.withOpacity(0.1)
                  : isSystem
                      ? AppTheme.warning.withOpacity(0.1)
                      : AppTheme.primaryDark.withOpacity(0.1),
              child: Icon(
                isError
                    ? Icons.error_outline
                    : isSystem
                        ? Icons.info_outline
                        : Icons.smart_toy,
                size: 18,
                color: isError
                    ? AppTheme.danger
                    : isSystem
                        ? AppTheme.warning
                        : AppTheme.primaryDark,
              ),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: isUser
                    ? AppTheme.primaryDark
                    : isError
                        ? AppTheme.danger.withOpacity(0.1)
                        : isSystem
                            ? AppTheme.warning.withOpacity(0.1)
                            : AppTheme.surfaceOf(context),
                borderRadius: BorderRadius.circular(16),
                border: isUser ? null : Border.all(color: AppTheme.borderOf(context)),
              ),
              child: Text(
                message.text,
                style: TextStyle(
                  fontSize: 14,
                  color: isUser ? Colors.white : AppTheme.text1(context),
                  height: 1.4,
                ),
              ),
            ),
          ),
          if (isUser) const SizedBox(width: 8),
        ],
      ),
    );
  }

  Widget _buildStreamingMessage() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 16,
            backgroundColor: AppTheme.primaryDark.withOpacity(0.1),
            child: const Icon(
              Icons.smart_toy,
              size: 18,
              color: AppTheme.primaryDark,
            ),
          ),
          const SizedBox(width: 8),
          Flexible(
            child: Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppTheme.surfaceOf(context),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.borderOf(context)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (_thinkingMessage.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(
                        children: [
                          SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: AppTheme.primaryDark,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            _thinkingMessage,
                            style: TextStyle(
                              fontSize: 12,
                              color: AppTheme.text2(context),
                              fontStyle: FontStyle.italic,
                            ),
                          ),
                        ],
                      ),
                    ),
                  if (_streamingResponse.isNotEmpty)
                    Text(
                      _streamingResponse,
                      style: TextStyle(
                        fontSize: 14,
                        color: AppTheme.text1(context),
                        height: 1.4,
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }
}

/// Internal chat message model
class _ChatMessage {
  final String text;
  final bool isUser;
  final DateTime timestamp;
  final List<Map<String, dynamic>>? sources;
  final bool isError;
  final bool isSystem;

  _ChatMessage({
    required this.text,
    required this.isUser,
    required this.timestamp,
    this.sources,
    this.isError = false,
    this.isSystem = false,
  });
}

/// Internal document file model
class _DocumentFile {
  final String name;
  final String path;
  final int size;
  final String extension;
  final Uint8List? bytes; // For web support
  String? extractedText;

  _DocumentFile({
    required this.name,
    required this.path,
    required this.size,
    required this.extension,
    this.bytes,
    this.extractedText,
  });
}
