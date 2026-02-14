import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/chat_service.dart';
import '../../../core/services/subscription_service.dart';

/// Unified AI Chat Screen - Claude/ChatGPT-style interface
///
/// Two states:
/// 1. Welcome state: centered input, suggestion grid, recent conversations
/// 2. Conversation state: message list + context bar + rich cards + input
class UnifiedChatScreen extends StatefulWidget {
  final String? conversationId;

  const UnifiedChatScreen({super.key, this.conversationId});

  @override
  State<UnifiedChatScreen> createState() => _UnifiedChatScreenState();
}

class _UnifiedChatScreenState extends State<UnifiedChatScreen> {
  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _inputFocusNode = FocusNode();
  final ChatService _chatService = ChatService();

  List<_ChatItem> _messages = [];
  List<Conversation> _recentConversations = [];
  String? _conversationId;
  bool _isLoading = false;
  bool _isStreaming = false;
  String _thinkingMessage = '';
  String _streamingResponse = '';
  List<Map<String, dynamic>> _currentSources = [];
  Map<String, dynamic>? _claimsenseData;

  // Context attachments
  String? _attachedAssessmentId;
  String? _attachedAssessmentTitle;

  bool get _isWelcomeState =>
      _messages.isEmpty && _conversationId == null && !_isLoading;

  @override
  void initState() {
    super.initState();
    _conversationId = widget.conversationId;
    if (_conversationId != null && _conversationId != 'new') {
      _loadConversation();
    } else {
      _conversationId = null;
      _loadRecentConversations();
    }
  }

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    _inputFocusNode.dispose();
    super.dispose();
  }

  Future<void> _loadRecentConversations() async {
    try {
      final convos = await _chatService.getConversations(limit: 10);
      if (mounted) setState(() => _recentConversations = convos);
    } catch (_) {}
  }

  Future<void> _loadConversation() async {
    if (_conversationId == null) return;
    setState(() => _isLoading = true);

    try {
      final history = await _chatService.getHistory(_conversationId!);
      setState(() {
        _messages = history
            .map((m) => _ChatItem(
                  text: m.content,
                  isUser: m.isUser,
                  timestamp: m.timestamp,
                  sources: (m.metadata?['sources'] as List?)
                      ?.cast<Map<String, dynamic>>(),
                ))
            .toList();
        _isLoading = false;
      });
      _scrollToBottom();
    } catch (e) {
      setState(() => _isLoading = false);
    }
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

  Future<void> _sendMessage([String? overrideText]) async {
    final text = overrideText ?? _messageController.text.trim();
    if (text.isEmpty || _isStreaming) return;

    _messageController.clear();

    setState(() {
      _messages.add(_ChatItem(text: text, isUser: true, timestamp: DateTime.now()));
      _isStreaming = true;
      _streamingResponse = '';
      _thinkingMessage = 'Connecting...';
      _currentSources = [];
      _claimsenseData = null;
    });
    _scrollToBottom();

    final messages = _messages
        .where((m) => m.isUser || (!m.isUser && m.text.isNotEmpty))
        .map((m) => {'role': m.isUser ? 'user' : 'assistant', 'content': m.text})
        .toList();

    await for (final event in _chatService.streamChat(
      messages: messages,
      conversationId: _conversationId,
      useRag: true,
      assessmentId: _attachedAssessmentId,
    )) {
      if (!mounted) break;

      if (event is ChatEventStart) {
        setState(() => _conversationId = event.conversationId);
      } else if (event is ChatEventThinking) {
        setState(() => _thinkingMessage = event.message);
      } else if (event is ChatEventSources) {
        setState(() => _currentSources = event.sources);
      } else if (event is ChatEventToken) {
        setState(() {
          _streamingResponse += event.content;
          _thinkingMessage = '';
        });
        _scrollToBottom();
      } else if (event is ChatEventClaimSense) {
        setState(() => _claimsenseData = event.data);
      } else if (event is ChatEventDone) {
        setState(() {
          _messages.add(_ChatItem(
            text: _streamingResponse,
            isUser: false,
            timestamp: DateTime.now(),
            sources: _currentSources,
            claimsenseData: _claimsenseData,
          ));
          _isStreaming = false;
          _streamingResponse = '';
          _thinkingMessage = '';
          _conversationId = event.conversationId;
        });
        _scrollToBottom();
      } else if (event is ChatEventError) {
        setState(() {
          _messages.add(_ChatItem(
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
  }

  @override
  Widget build(BuildContext context) {
    // Premium gate - chat is premium-only
    if (!SubscriptionService().isPremium) {
      return Scaffold(
        backgroundColor: AppTheme.darkCardAlt,
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: LinearGradient(
                        colors: [AppTheme.accent.withValues(alpha: 0.2), AppTheme.primaryDark.withValues(alpha: 0.2)],
                      ),
                    ),
                    child: const Icon(Icons.chat_bubble_outline, size: 48, color: AppTheme.accentBright),
                  ),
                  const SizedBox(height: 24),
                  const Text('InstantRisk Assistant', style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w700, fontFamily: 'Inter')),
                  const SizedBox(height: 12),
                  Text('Get instant answers about insurance policies, risk analysis, and underwriting decisions.',
                      textAlign: TextAlign.center, style: TextStyle(color: Colors.white.withValues(alpha: 0.6), fontSize: 14, height: 1.5)),
                  const SizedBox(height: 32),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppTheme.primaryDark.withValues(alpha: 0.3)),
                      color: AppTheme.primaryDark.withValues(alpha: 0.08),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.workspace_premium, color: AppTheme.accentBright, size: 20),
                        const SizedBox(width: 12),
                        const Expanded(
                          child: Text('Premium Feature', style: TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600)),
                        ),
                        TextButton(
                          onPressed: () => context.go('/settings/subscription'),
                          child: const Text('Upgrade', style: TextStyle(color: AppTheme.accentBright, fontWeight: FontWeight.w600)),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: AppTheme.darkCardAlt,
      appBar: _isWelcomeState ? null : _buildAppBar(),
      body: SafeArea(
        child: Column(
          children: [
            // Context bar (when assessment is attached)
            if (_attachedAssessmentId != null) _buildContextBar(),
            // Main content
            Expanded(
              child: _isWelcomeState ? _buildWelcomeState() : _buildConversationState(),
            ),
            // Input area
            _buildInputArea(),
          ],
        ),
      ),
    );
  }

  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      backgroundColor: AppTheme.darkCardAlt,
      elevation: 0,
      leading: IconButton(
        icon: const Icon(Icons.arrow_back, color: Colors.white70),
        onPressed: () {
          if (_messages.isNotEmpty) {
            setState(() {
              _messages.clear();
              _conversationId = null;
              _loadRecentConversations();
            });
          } else {
            context.pop();
          }
        },
      ),
      title: const Text(
        'AI Assistant',
        style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w600),
      ),
      actions: [
        IconButton(
          icon: const Icon(Icons.add_circle_outline, color: Colors.white70),
          tooltip: 'Attach context',
          onPressed: _showContextPicker,
        ),
      ],
    );
  }

  Widget _buildContextBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: AppTheme.darkCard,
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: AppTheme.primaryDark.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppTheme.primaryDark.withValues(alpha: 0.3)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.assessment, size: 14, color: AppTheme.primaryDark),
                const SizedBox(width: 6),
                Text(
                  _attachedAssessmentTitle ?? 'Assessment',
                  style: TextStyle(color: AppTheme.primaryDark, fontSize: 12),
                ),
                const SizedBox(width: 4),
                InkWell(
                  onTap: () => setState(() {
                    _attachedAssessmentId = null;
                    _attachedAssessmentTitle = null;
                  }),
                  child: Icon(Icons.close, size: 14, color: Colors.white38),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWelcomeState() {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        children: [
          const SizedBox(height: 60),
          // AI Logo
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [AppTheme.primaryDark, AppTheme.analysisPurple],
              ),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Icon(Icons.auto_awesome, color: Colors.white, size: 32),
          ),
          const SizedBox(height: 20),
          const Text(
            'What can I help you with?',
            style: TextStyle(
              color: Colors.white,
              fontSize: 24,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Insurance AI with 112K+ knowledge base records',
            style: TextStyle(color: Colors.white38, fontSize: 14),
          ),
          const SizedBox(height: 32),
          // Recent Conversations
          if (_recentConversations.isNotEmpty) ...[
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Recent Conversations',
                style: TextStyle(
                  color: Colors.white54,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.5,
                ),
              ),
            ),
            const SizedBox(height: 12),
            ..._recentConversations.take(5).map(_buildConversationTile),
          ],
          const SizedBox(height: 100),
        ],
      ),
    );
  }

  Widget _buildConversationTile(Conversation convo) {
    final timeAgo = _formatTimeAgo(convo.lastMessageAt);
    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      leading: Container(
        width: 36,
        height: 36,
        decoration: BoxDecoration(
          color: AppTheme.darkCard,
          borderRadius: BorderRadius.circular(10),
        ),
        child: const Icon(Icons.chat_bubble_outline, color: Colors.white38, size: 16),
      ),
      title: Text(
        convo.title,
        style: const TextStyle(color: Colors.white70, fontSize: 13),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      trailing: Text(timeAgo, style: const TextStyle(color: Colors.white24, fontSize: 11)),
      onTap: () {
        setState(() {
          _conversationId = convo.id;
          _loadConversation();
        });
      },
    );
  }

  Widget _buildConversationState() {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      itemCount: _messages.length + (_isStreaming ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _messages.length && _isStreaming) {
          // Streaming bubble
          return _buildStreamingBubble();
        }
        return _buildMessageBubble(_messages[index]);
      },
    );
  }

  Widget _buildMessageBubble(_ChatItem message) {
    if (message.isUser) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 16, left: 48),
        child: Align(
          alignment: Alignment.centerRight,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [AppTheme.primaryDark, AppTheme.analysisIndigo],
              ),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(18),
                topRight: Radius.circular(18),
                bottomLeft: Radius.circular(18),
                bottomRight: Radius.circular(4),
              ),
            ),
            child: Text(
              message.text,
              style: const TextStyle(color: Colors.white, fontSize: 14, height: 1.5),
            ),
          ),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 16, right: 32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ClaimSense card (if benchmark data present)
          if (message.claimsenseData != null) _buildClaimSenseCard(message.claimsenseData!),
          // Message text
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: AppTheme.darkCard,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(4),
                topRight: Radius.circular(18),
                bottomLeft: Radius.circular(18),
                bottomRight: Radius.circular(18),
              ),
            ),
            child: SelectableText(
              message.text,
              style: TextStyle(
                color: message.isError ? Colors.redAccent : Colors.white.withValues(alpha: 0.9),
                fontSize: 14,
                height: 1.6,
              ),
            ),
          ),
          // Sources
          if (message.sources != null && message.sources!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Wrap(
                spacing: 6,
                children: message.sources!.take(3).map((s) {
                  final name = s['name'] ?? s['source'] ?? 'Source';
                  final score = s['score'] ?? s['relevance'] ?? 0;
                  return Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.05),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      '$name ${(score * 100).toInt()}%',
                      style: const TextStyle(color: Colors.white24, fontSize: 10),
                    ),
                  );
                }).toList(),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildClaimSenseCard(Map<String, dynamic> data) {
    final policyType = data['policy_type'] ?? 'GL';
    final totalClaims = data['total_claims'] ?? data['count'] ?? 0;
    final avgSeverity = data['avg_severity'] ?? data['average_severity'] ?? 0;
    final frequency = data['frequency_rate'] ?? data['frequency'] ?? 0;
    final state = data['state'] ?? '';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [AppTheme.darkCard, AppTheme.darkCard],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.primaryDark.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.insights, color: AppTheme.primaryDark, size: 18),
              const SizedBox(width: 8),
              Text(
                '$policyType Claims${state.isNotEmpty ? ' — $state' : ''}',
                style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppTheme.primaryDark.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text(
                  'ClaimSense',
                  style: TextStyle(color: AppTheme.phaseResearch, fontSize: 10, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              _buildMetricTile('Total Claims', _formatNumber(totalClaims)),
              _buildMetricTile('Avg Severity', '\$${_formatNumber(avgSeverity)}'),
              _buildMetricTile('Frequency', frequency.toStringAsFixed(3)),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Based on ${_formatNumber(totalClaims)} benchmark records',
            style: const TextStyle(color: Colors.white24, fontSize: 10),
          ),
        ],
      ),
    );
  }

  Widget _buildMetricTile(String label, String value) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: Colors.white38, fontSize: 10)),
          const SizedBox(height: 4),
          Text(value, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }

  Widget _buildStreamingBubble() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16, right: 32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_claimsenseData != null) _buildClaimSenseCard(_claimsenseData!),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: AppTheme.darkCard,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(4),
                topRight: Radius.circular(18),
                bottomLeft: Radius.circular(18),
                bottomRight: Radius.circular(18),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_thinkingMessage.isNotEmpty)
                  Row(
                    children: [
                      SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.primaryDark),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        _thinkingMessage,
                        style: TextStyle(color: AppTheme.primaryDark, fontSize: 13),
                      ),
                    ],
                  ),
                if (_streamingResponse.isNotEmpty)
                  SelectableText(
                    _streamingResponse,
                    style: TextStyle(color: Colors.white.withValues(alpha: 0.9), fontSize: 14, height: 1.6),
                  ),
                if (_streamingResponse.isEmpty && _thinkingMessage.isEmpty)
                  Row(
                    children: [
                      _buildDot(0),
                      _buildDot(1),
                      _buildDot(2),
                    ],
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDot(int index) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 2),
      width: 8,
      height: 8,
      decoration: BoxDecoration(
        color: Colors.white24,
        shape: BoxShape.circle,
      ),
    );
  }

  Widget _buildInputArea() {
    return Container(
      padding: EdgeInsets.fromLTRB(16, 12, 16, MediaQuery.of(context).padding.bottom + 12),
      decoration: const BoxDecoration(
        color: AppTheme.darkBg,
        border: Border(top: BorderSide(color: Colors.white10)),
      ),
      child: Row(
        children: [
          // Attach button
          IconButton(
            icon: const Icon(Icons.attach_file, color: Colors.white38, size: 22),
            onPressed: _showContextPicker,
          ),
          // Text input
          Expanded(
            child: Container(
              constraints: const BoxConstraints(maxHeight: 120),
              decoration: BoxDecoration(
                color: AppTheme.darkCard,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: Colors.white10),
              ),
              child: TextField(
                controller: _messageController,
                focusNode: _inputFocusNode,
                style: const TextStyle(color: Colors.white, fontSize: 14),
                maxLines: null,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _sendMessage(),
                decoration: InputDecoration(
                  hintText: _isWelcomeState ? 'Ask about insurance...' : 'Type a message...',
                  hintStyle: const TextStyle(color: Colors.white24, fontSize: 14),
                  border: InputBorder.none,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          // Send button
          Container(
            decoration: BoxDecoration(
              gradient: _isStreaming
                  ? null
                  : LinearGradient(colors: [AppTheme.primaryDark, AppTheme.analysisIndigo]),
              color: _isStreaming ? Colors.white10 : null,
              shape: BoxShape.circle,
            ),
            child: IconButton(
              icon: Icon(
                _isStreaming ? Icons.stop : Icons.send,
                color: Colors.white,
                size: 20,
              ),
              onPressed: _isStreaming ? null : () => _sendMessage(),
            ),
          ),
        ],
      ),
    );
  }

  void _showContextPicker() {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppTheme.darkCard,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Attach Context',
                style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 16),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryDark.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(Icons.assessment, color: AppTheme.primaryDark),
                ),
                title: const Text('Browse Assessments', style: TextStyle(color: Colors.white)),
                subtitle: const Text('Attach an assessment for context', style: TextStyle(color: Colors.white38, fontSize: 12)),
                onTap: () {
                  Navigator.pop(context);
                  _showAssessmentPicker();
                },
              ),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.green.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.upload_file, color: Colors.green),
                ),
                title: const Text('Upload Document', style: TextStyle(color: Colors.white)),
                subtitle: const Text('PDF, DOCX, or images', style: TextStyle(color: Colors.white38, fontSize: 12)),
                onTap: () {
                  Navigator.pop(context);
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Document upload coming soon'), duration: Duration(seconds: 2)),
                  );
                },
              ),
              const SizedBox(height: 16),
            ],
          ),
        );
      },
    );
  }

  Future<void> _showAssessmentPicker() async {
    try {
      final response = await authService.get('/assessments/?page=1&page_size=20');
      if (response.statusCode != 200 || !mounted) return;
      final data = jsonDecode(response.body);
      final items = (data['items'] as List?) ?? [];
      if (!mounted) return;

      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: AppTheme.darkCard,
          title: const Text('Select Assessment', style: TextStyle(color: Colors.white)),
          content: SizedBox(
            width: double.maxFinite,
            height: 400,
            child: items.isEmpty
                ? const Center(child: Text('No assessments found', style: TextStyle(color: Colors.white54)))
                : ListView.builder(
                    itemCount: items.length,
                    itemBuilder: (context, index) {
                      final item = items[index];
                      final title = item['title'] ?? item['insured_name'] ?? 'Assessment';
                      final status = item['status'] ?? '';
                      final decision = item['decision'] ?? '';
                      return ListTile(
                        leading: Icon(
                          decision == 'go' ? Icons.check_circle : decision == 'no_go' ? Icons.cancel : Icons.pending,
                          color: decision == 'go' ? Colors.green : decision == 'no_go' ? Colors.red : Colors.orange,
                          size: 20,
                        ),
                        title: Text(title, style: const TextStyle(color: Colors.white, fontSize: 14), maxLines: 1, overflow: TextOverflow.ellipsis),
                        subtitle: Text('$status ${decision.isNotEmpty ? "· $decision" : ""}', style: const TextStyle(color: Colors.white38, fontSize: 12)),
                        onTap: () {
                          Navigator.pop(ctx);
                          setState(() {
                            _attachedAssessmentId = item['id']?.toString();
                            _attachedAssessmentTitle = title;
                          });
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Attached: $title'), duration: const Duration(seconds: 2)),
                          );
                        },
                      );
                    },
                  ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
          ],
        ),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to load assessments')),
        );
      }
    }
  }

  String _formatTimeAgo(DateTime date) {
    final diff = DateTime.now().difference(date);
    if (diff.inMinutes < 60) return '${diff.inMinutes}m';
    if (diff.inHours < 24) return '${diff.inHours}h';
    if (diff.inDays < 7) return '${diff.inDays}d';
    return '${(diff.inDays / 7).floor()}w';
  }

  String _formatNumber(dynamic n) {
    if (n is int) {
      if (n >= 1000000) return '${(n / 1000000).toStringAsFixed(1)}M';
      if (n >= 1000) return '${(n / 1000).toStringAsFixed(1)}K';
      return n.toString();
    }
    if (n is double) {
      if (n >= 1000000) return '${(n / 1000000).toStringAsFixed(1)}M';
      if (n >= 1000) return '${(n / 1000).toStringAsFixed(1)}K';
      return n.toStringAsFixed(0);
    }
    return n.toString();
  }
}

class _ChatItem {
  final String text;
  final bool isUser;
  final DateTime timestamp;
  final List<Map<String, dynamic>>? sources;
  final Map<String, dynamic>? claimsenseData;
  final bool isError;

  _ChatItem({
    required this.text,
    required this.isUser,
    required this.timestamp,
    this.sources,
    this.claimsenseData,
    this.isError = false,
  });
}
