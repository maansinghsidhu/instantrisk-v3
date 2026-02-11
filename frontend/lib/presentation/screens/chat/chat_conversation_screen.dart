import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/chat_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Chat Conversation Screen - Real AI chat with streaming responses
class ChatConversationScreen extends StatefulWidget {
  final String? conversationId;

  const ChatConversationScreen({
    super.key,
    this.conversationId,
  });

  @override
  State<ChatConversationScreen> createState() => _ChatConversationScreenState();
}

class _ChatConversationScreenState extends State<ChatConversationScreen> {
  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final ChatService _chatService = ChatService();

  List<_ChatMessage> _messages = [];
  String? _conversationId;
  bool _isLoading = false;
  bool _isStreaming = false;
  String _thinkingMessage = '';
  String _streamingResponse = '';
  List<Map<String, dynamic>> _currentSources = [];

  @override
  void initState() {
    super.initState();
    _conversationId = widget.conversationId;
    _loadConversation();
  }

  Future<void> _loadConversation() async {
    if (_conversationId != null && _conversationId != 'new') {
      setState(() => _isLoading = true);

      try {
        final history = await _chatService.getHistory(_conversationId!);
        setState(() {
          _messages = history
              .map((m) => _ChatMessage(
                    text: m.content,
                    isUser: m.isUser,
                    timestamp: m.timestamp,
                    sources: (m.metadata?['sources'] as List?)?.cast<Map<String, dynamic>>(),
                  ))
              .toList();
          _isLoading = false;
        });
        _scrollToBottom();
      } catch (e) {
        setState(() => _isLoading = false);
        _showWelcomeMessage();
      }
    } else {
      _showWelcomeMessage();
    }
  }

  void _showWelcomeMessage() {
    setState(() {
      _messages = [
        _ChatMessage(
          text: '''Hello! I'm your AI insurance assistant powered by InstantRisk's knowledge base of:

• **34,000+** insurance clauses and policy wordings
• **Legal cases** and regulatory documents
• **Lloyd's market** regulations and practices
• **Actuarial data** and pricing models

How can I help you today?''',
          isUser: false,
          timestamp: DateTime.now(),
        ),
      ];
    });
  }

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
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
      _thinkingMessage = 'Connecting...';
      _streamingResponse = '';
      _currentSources = [];
    });

    _messageController.clear();
    _scrollToBottom();

    // Build message history
    final messageHistory = _messages
        .where((m) => m.text.isNotEmpty)
        .map((m) => {
              'role': m.isUser ? 'user' : 'assistant',
              'content': m.text,
            })
        .toList();

    try {
      await for (final event in _chatService.streamChat(
        messages: messageHistory,
        conversationId: _conversationId,
        useRag: true,
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
    final isNewConversation = _conversationId == null || _conversationId == 'new';

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: AppTheme.surface,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppTheme.textPrimary),
          onPressed: () => context.go('/chat'),
        ),
        title: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [AppTheme.primaryDark, AppTheme.accent],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.auto_awesome,
                color: Colors.white,
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    isNewConversation ? AppLocalizations.of(context).newChat : AppLocalizations.of(context).aiAssistant,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  Row(
                    children: [
                      Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: _isStreaming ? AppTheme.warning : AppTheme.success,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        _isStreaming
                            ? (_thinkingMessage.isNotEmpty ? _thinkingMessage : 'Responding...')
                            : 'Online • MiniMax M2.1 + RAG',
                        style: TextStyle(
                          fontSize: 11,
                          color: _isStreaming ? AppTheme.warning : AppTheme.success,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          if (_currentSources.isNotEmpty)
            IconButton(
              icon: Badge(
                label: Text('${_currentSources.length}'),
                child: const Icon(Icons.source_outlined, color: AppTheme.textPrimary),
              ),
              onPressed: _showSources,
            ),
          IconButton(
            icon: const Icon(Icons.refresh, color: AppTheme.textPrimary),
            onPressed: _conversationId != null ? _loadConversation : null,
          ),
        ],
      ),
      body: Column(
        children: [
          // Messages List
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(16),
                    itemCount: _messages.length + (_isStreaming ? 1 : 0),
                    itemBuilder: (context, index) {
                      if (index == _messages.length && _isStreaming) {
                        return _buildStreamingBubble();
                      }
                      return _buildMessageBubble(_messages[index]);
                    },
                  ),
          ),

          // Input Area
          _buildInputArea(),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(_ChatMessage message) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        mainAxisAlignment: message.isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!message.isUser) ...[
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: message.isError
                      ? [AppTheme.error, AppTheme.error]
                      : [AppTheme.primaryDark, AppTheme.accent],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                shape: BoxShape.circle,
              ),
              child: Icon(
                message.isError ? Icons.error_outline : Icons.auto_awesome,
                color: Colors.white,
                size: 16,
              ),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Column(
              crossAxisAlignment:
                  message.isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: message.isUser
                        ? AppTheme.primaryDark
                        : message.isError
                            ? AppTheme.error.withOpacity(0.1)
                            : AppTheme.surface,
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(16),
                      topRight: const Radius.circular(16),
                      bottomLeft: Radius.circular(message.isUser ? 16 : 4),
                      bottomRight: Radius.circular(message.isUser ? 4 : 16),
                    ),
                    border: message.isUser
                        ? null
                        : Border.all(
                            color: message.isError ? AppTheme.error : AppTheme.border,
                          ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SelectableText(
                        message.text,
                        style: TextStyle(
                          fontSize: 14,
                          color: message.isUser
                              ? Colors.white
                              : message.isError
                                  ? AppTheme.error
                                  : AppTheme.textPrimary,
                          height: 1.5,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            _formatTimestamp(message.timestamp),
                            style: TextStyle(
                              fontSize: 10,
                              color: message.isUser ? Colors.white60 : AppTheme.textHint,
                            ),
                          ),
                          if (!message.isUser && message.sources != null && message.sources!.isNotEmpty) ...[
                            const SizedBox(width: 8),
                            GestureDetector(
                              onTap: () => _showSourcesDialog(message.sources!),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(
                                    Icons.source_outlined,
                                    size: 12,
                                    color: AppTheme.accent,
                                  ),
                                  const SizedBox(width: 4),
                                  Text(
                                    '${message.sources!.length} sources',
                                    style: TextStyle(
                                      fontSize: 10,
                                      color: AppTheme.accent,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
                if (!message.isUser && !message.isError)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        _buildActionButton(Icons.copy, AppLocalizations.of(context).copy, () {
                          Clipboard.setData(ClipboardData(text: message.text));
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text(AppLocalizations.of(context).copiedToClipboard)),
                          );
                        }),
                        _buildActionButton(Icons.thumb_up_outlined, 'Good', () {}),
                        _buildActionButton(Icons.thumb_down_outlined, 'Bad', () {}),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          if (message.isUser) const SizedBox(width: 40),
        ],
      ),
    );
  }

  Widget _buildStreamingBubble() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [AppTheme.primaryDark, AppTheme.accent],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.auto_awesome,
              color: Colors.white,
              size: 16,
            ),
          ),
          const SizedBox(width: 8),
          Flexible(
            child: Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(16),
                  topRight: Radius.circular(16),
                  bottomLeft: Radius.circular(4),
                  bottomRight: Radius.circular(16),
                ),
                border: Border.all(color: AppTheme.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (_thinkingMessage.isNotEmpty) ...[
                    Row(
                      children: [
                        SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation(AppTheme.accent),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          _thinkingMessage,
                          style: TextStyle(
                            fontSize: 13,
                            color: AppTheme.textSecondary,
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                      ],
                    ),
                    if (_streamingResponse.isNotEmpty) const SizedBox(height: 12),
                  ],
                  if (_streamingResponse.isNotEmpty)
                    SelectableText(
                      _streamingResponse,
                      style: const TextStyle(
                        fontSize: 14,
                        color: AppTheme.textPrimary,
                        height: 1.5,
                      ),
                    ),
                  if (_streamingResponse.isEmpty && _thinkingMessage.isEmpty)
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        _buildTypingDot(0),
                        _buildTypingDot(1),
                        _buildTypingDot(2),
                      ],
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTypingDot(int index) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 600 + (index * 200)),
      builder: (context, value, child) {
        return Container(
          margin: const EdgeInsets.symmetric(horizontal: 3),
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            color: AppTheme.accent.withOpacity(0.5 + (value * 0.5)),
            shape: BoxShape.circle,
          ),
        );
      },
    );
  }

  Widget _buildActionButton(IconData icon, String tooltip, VoidCallback onTap) {
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.all(6),
          child: Icon(icon, size: 16, color: AppTheme.textHint),
        ),
      ),
    );
  }

  Widget _buildInputArea() {
    return Container(
      padding: const EdgeInsets.all(16),
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
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            IconButton(
              icon: const Icon(Icons.attach_file, color: AppTheme.textSecondary),
              onPressed: () {
                // TODO: Attach document for context
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Document attachment coming soon')),
                );
              },
            ),
            Expanded(
              child: Container(
                decoration: BoxDecoration(
                  color: AppTheme.background,
                  borderRadius: BorderRadius.circular(24),
                ),
                child: TextField(
                  controller: _messageController,
                  decoration: InputDecoration(
                    hintText: _isStreaming ? 'Wait for response...' : 'Ask about insurance...',
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  ),
                  maxLines: null,
                  textInputAction: TextInputAction.send,
                  enabled: !_isStreaming,
                  onSubmitted: (_) => _sendMessage(),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Container(
              decoration: BoxDecoration(
                gradient: _isStreaming
                    ? null
                    : LinearGradient(
                        colors: [AppTheme.primaryDark, AppTheme.accent],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                color: _isStreaming ? AppTheme.textHint : null,
                shape: BoxShape.circle,
              ),
              child: IconButton(
                icon: Icon(
                  _isStreaming ? Icons.hourglass_top : Icons.send,
                  color: Colors.white,
                  size: 20,
                ),
                onPressed: _isStreaming ? null : _sendMessage,
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showSources() {
    if (_currentSources.isNotEmpty) {
      _showSourcesDialog(_currentSources);
    }
  }

  void _showSourcesDialog(List<Map<String, dynamic>> sources) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppTheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.5,
        minChildSize: 0.3,
        maxChildSize: 0.9,
        expand: false,
        builder: (context, scrollController) => Column(
          children: [
            Container(
              margin: const EdgeInsets.only(top: 12),
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppTheme.border,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  const Icon(Icons.source_outlined, color: AppTheme.accent),
                  const SizedBox(width: 8),
                  Text(
                    '${AppLocalizations.of(context).knowledgeSources} (${sources.length})',
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            Expanded(
              child: ListView.builder(
                controller: scrollController,
                padding: const EdgeInsets.all(16),
                itemCount: sources.length,
                itemBuilder: (context, index) {
                  final source = sources[index];
                  return Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.background,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppTheme.border),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: AppTheme.accent.withOpacity(0.1),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                source['source_type']?.toString().toUpperCase() ?? 'SOURCE',
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w600,
                                  color: AppTheme.accent,
                                ),
                              ),
                            ),
                            const Spacer(),
                            Text(
                              '${((source['relevance'] ?? 0) * 100).toInt()}% match',
                              style: TextStyle(
                                fontSize: 11,
                                color: AppTheme.textHint,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          source['title'] ?? 'Document',
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          source['snippet'] ?? '',
                          style: const TextStyle(
                            fontSize: 13,
                            color: AppTheme.textSecondary,
                            height: 1.4,
                          ),
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _formatTimestamp(DateTime timestamp) {
    final hour = timestamp.hour.toString().padLeft(2, '0');
    final minute = timestamp.minute.toString().padLeft(2, '0');
    return '$hour:$minute';
  }
}

class _ChatMessage {
  final String text;
  final bool isUser;
  final DateTime timestamp;
  final List<Map<String, dynamic>>? sources;
  final bool isError;

  _ChatMessage({
    required this.text,
    required this.isUser,
    required this.timestamp,
    this.sources,
    this.isError = false,
  });
}
