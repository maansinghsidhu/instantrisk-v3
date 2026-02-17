import 'dart:convert';
import 'dart:typed_data' show Uint8List;
import 'auth_service.dart';

/// VoiceService - Whisper-powered voice transcription for voice commands
class VoiceService {
  /// Transcribe audio bytes using Whisper API
  /// [audioBytes] - raw audio data (WAV or WebM)
  /// [mimeType] - 'audio/wav' or 'audio/webm'
  Future<String?> transcribeAudio({
    required Uint8List audioBytes,
    String mimeType = 'audio/wav',
    String language = 'en',
  }) async {
    try {
      // Use existing uploadFileBytes method
      final streamed = await authService.uploadFileBytes(
        '/voice/transcribe',
        audioBytes.toList(),
        'audio.wav',
        'audio',
        fields: {'language': language},
      );
      final response = await streamed.stream.toBytes();
      final data = jsonDecode(String.fromCharCodes(response));
      return data['transcript'] as String?;
    } catch (_) {}
    return null;
  }

  /// Send a voice command text and get the action to perform
  Future<Map<String, dynamic>?> processVoiceCommand(String transcript) async {
    try {
      final response = await authService.post(
        '/voice/command',
        body: jsonEncode({'transcript': transcript}),
      );
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return null;
  }

  /// Get supported voice commands list
  Future<List<Map<String, dynamic>>> getSupportedCommands() async {
    try {
      final response = await authService.get('/voice/commands');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return List<Map<String, dynamic>>.from(data['commands'] ?? []);
      }
    } catch (_) {}
    return _defaultCommands;
  }

  static const List<Map<String, dynamic>> _defaultCommands = [
    {
      'command': 'analyze',
      'description': 'Start a new analysis',
      'examples': ['analyze this submission', 'run analysis'],
    },
    {
      'command': 'search',
      'description': 'Search for precedents',
      'examples': ['find similar risks', 'search cyber claims'],
    },
    {
      'command': 'summarize',
      'description': 'Summarize current assessment',
      'examples': ['summarize findings', 'give me a summary'],
    },
    {
      'command': 'navigate',
      'description': 'Navigate to a screen',
      'examples': ['go to dashboard', 'open reports'],
    },
  ];
}

final voiceService = VoiceService();
