import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'auth_service.dart';

/// Chat Service - Handles AI chat with streaming responses
class ChatService {
  static final ChatService _instance = ChatService._internal();
  factory ChatService() => _instance;
  ChatService._internal();

  String get _baseUrl => authService.baseUrl;

  /// Stream chat response token by token
  Stream<ChatEvent> streamChat({
    required List<Map<String, String>> messages,
    String? conversationId,
    bool useRag = true,
    String? assessmentId,  // UUID string for assessment context
    String? documentContext,  // Additional context about uploaded documents
    double temperature = 0.3,
    int maxTokens = 2048,
  }) async* {
    final token = authService.token;
    if (token == null) {
      yield ChatEvent.error('Not authenticated');
      return;
    }

    final request = http.Request(
      'POST',
      Uri.parse('$_baseUrl/chat/stream'),
    );

    request.headers.addAll({
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    });

    request.body = jsonEncode({
      'messages': messages,
      'conversation_id': conversationId,
      'use_rag': useRag,
      'assessment_id': assessmentId,
      'document_context': documentContext,
      'temperature': temperature,
      'max_tokens': maxTokens,
    });

    try {
      final client = http.Client();
      final response = await client.send(request);

      if (response.statusCode != 200) {
        yield ChatEvent.error('Server error: ${response.statusCode}');
        return;
      }

      String buffer = '';

      await for (final chunk in response.stream.transform(utf8.decoder)) {
        buffer += chunk;

        // Process complete SSE lines
        while (buffer.contains('\n\n')) {
          final index = buffer.indexOf('\n\n');
          final line = buffer.substring(0, index);
          buffer = buffer.substring(index + 2);

          if (line.startsWith('data: ')) {
            try {
              final data = jsonDecode(line.substring(6));
              final type = data['type'] as String?;

              switch (type) {
                case 'start':
                  yield ChatEvent.start(data['conversation_id'] ?? '');
                  break;
                case 'thinking':
                  yield ChatEvent.thinking(data['message'] ?? 'Thinking...');
                  break;
                case 'sources':
                  yield ChatEvent.sources(
                    (data['sources'] as List?)?.cast<Map<String, dynamic>>() ?? [],
                  );
                  break;
                case 'token':
                  yield ChatEvent.token(data['content'] ?? '');
                  break;
                case 'done':
                  yield ChatEvent.done(
                    data['conversation_id'] ?? '',
                    (data['sources'] as List?)?.cast<Map<String, dynamic>>() ?? [],
                  );
                  break;
                case 'error':
                  yield ChatEvent.error(data['message'] ?? 'Unknown error');
                  break;
                case 'claimsense':
                  yield ChatEvent.claimsense(
                    (data['data'] as Map<String, dynamic>?) ?? {},
                  );
                  break;
              }
            } catch (e) {
              // Skip malformed JSON
            }
          }
        }
      }

      client.close();
    } catch (e) {
      yield ChatEvent.error('Connection error: $e');
    }
  }

  /// Send chat message and get complete response (non-streaming)
  Future<ChatResponse> sendMessage({
    required List<Map<String, String>> messages,
    String? conversationId,
    bool useRag = true,
    String? assessmentId,  // UUID string for assessment context
  }) async {
    final token = await authService.token;
    if (token == null) {
      throw Exception('Not authenticated');
    }

    final response = await http.post(
      Uri.parse('$_baseUrl/chat/'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'messages': messages,
        'conversation_id': conversationId,
        'use_rag': useRag,
        'assessment_id': assessmentId,
      }),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return ChatResponse.fromJson(data);
    } else {
      throw Exception('Failed to send message: ${response.statusCode}');
    }
  }

  /// Get list of conversations
  Future<List<Conversation>> getConversations({int limit = 20}) async {
    final token = await authService.token;
    if (token == null) return [];

    final response = await http.get(
      Uri.parse('$_baseUrl/chat/conversations?limit=$limit'),
      headers: {'Authorization': 'Bearer $token'},
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      final conversations = data['conversations'] as List;
      return conversations.map((c) => Conversation.fromJson(c)).toList();
    }
    return [];
  }

  /// Get conversation history
  Future<List<ChatMessage>> getHistory(String conversationId) async {
    final token = await authService.token;
    if (token == null) return [];

    final response = await http.get(
      Uri.parse('$_baseUrl/chat/history/$conversationId'),
      headers: {'Authorization': 'Bearer $token'},
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      final messages = data['messages'] as List;
      return messages.map((m) => ChatMessage.fromJson(m)).toList();
    }
    return [];
  }

  /// Get suggested questions
  Future<List<String>> getSuggestions({String context = 'general'}) async {
    final token = await authService.token;
    if (token == null) return [];

    final response = await http.get(
      Uri.parse('$_baseUrl/chat/suggestions?context=$context'),
      headers: {'Authorization': 'Bearer $token'},
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return (data['suggestions'] as List).cast<String>();
    }
    return [];
  }

  /// Submit feedback on a response
  Future<void> submitFeedback(String messageId, int rating, {String? feedback}) async {
    final token = await authService.token;
    if (token == null) return;

    await http.post(
      Uri.parse('$_baseUrl/chat/feedback?message_id=$messageId&rating=$rating'),
      headers: {'Authorization': 'Bearer $token'},
    );
  }
}

/// Chat event types for streaming
abstract class ChatEvent {
  factory ChatEvent.start(String conversationId) = ChatEventStart;
  factory ChatEvent.thinking(String message) = ChatEventThinking;
  factory ChatEvent.sources(List<Map<String, dynamic>> sources) = ChatEventSources;
  factory ChatEvent.token(String content) = ChatEventToken;
  factory ChatEvent.done(String conversationId, List<Map<String, dynamic>> sources) = ChatEventDone;
  factory ChatEvent.error(String message) = ChatEventError;
  factory ChatEvent.claimsense(Map<String, dynamic> data) = ChatEventClaimSense;
}

class ChatEventStart implements ChatEvent {
  final String conversationId;
  ChatEventStart(this.conversationId);
}

class ChatEventThinking implements ChatEvent {
  final String message;
  ChatEventThinking(this.message);
}

class ChatEventSources implements ChatEvent {
  final List<Map<String, dynamic>> sources;
  ChatEventSources(this.sources);
}

class ChatEventToken implements ChatEvent {
  final String content;
  ChatEventToken(this.content);
}

class ChatEventDone implements ChatEvent {
  final String conversationId;
  final List<Map<String, dynamic>> sources;
  ChatEventDone(this.conversationId, this.sources);
}

class ChatEventError implements ChatEvent {
  final String message;
  ChatEventError(this.message);
}

class ChatEventClaimSense implements ChatEvent {
  final Map<String, dynamic> data;
  ChatEventClaimSense(this.data);
}

/// Chat response model
class ChatResponse {
  final String message;
  final String conversationId;
  final List<Map<String, dynamic>> sources;
  final int tokensUsed;
  final String model;

  ChatResponse({
    required this.message,
    required this.conversationId,
    this.sources = const [],
    this.tokensUsed = 0,
    this.model = '',
  });

  factory ChatResponse.fromJson(Map<String, dynamic> json) {
    return ChatResponse(
      message: json['message'] ?? '',
      conversationId: json['conversation_id'] ?? '',
      sources: (json['sources'] as List?)?.cast<Map<String, dynamic>>() ?? [],
      tokensUsed: json['tokens_used'] ?? 0,
      model: json['model'] ?? '',
    );
  }
}

/// Conversation model
class Conversation {
  final String id;
  final String title;
  final DateTime lastMessageAt;
  final int messageCount;

  Conversation({
    required this.id,
    required this.title,
    required this.lastMessageAt,
    required this.messageCount,
  });

  factory Conversation.fromJson(Map<String, dynamic> json) {
    return Conversation(
      id: json['id'] ?? '',
      title: json['title'] ?? 'New Conversation',
      lastMessageAt: DateTime.tryParse(json['last_message_at'] ?? '') ?? DateTime.now(),
      messageCount: json['message_count'] ?? 0,
    );
  }
}

/// Chat message model
class ChatMessage {
  final String id;
  final String role;
  final String content;
  final DateTime timestamp;
  final Map<String, dynamic>? metadata;

  ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.timestamp,
    this.metadata,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id'] ?? '',
      role: json['role'] ?? 'user',
      content: json['content'] ?? '',
      timestamp: DateTime.tryParse(json['timestamp'] ?? '') ?? DateTime.now(),
      metadata: json['metadata'],
    );
  }

  bool get isUser => role == 'user';
  bool get isAssistant => role == 'assistant';
}
