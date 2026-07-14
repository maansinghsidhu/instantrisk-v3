import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';

/// VoiceCommandButton - Microphone button that activates Whisper voice input.
/// Shows recording animation when active. Calls [onTranscript] with the result.
///
/// Usage:
///   VoiceCommandButton(
///     onTranscript: (text) => _sendMessage(text),
///   )
class VoiceCommandButton extends StatefulWidget {
  final Function(String transcript) onTranscript;
  final bool compact;

  const VoiceCommandButton({
    super.key,
    required this.onTranscript,
    this.compact = false,
  });

  @override
  State<VoiceCommandButton> createState() => _VoiceCommandButtonState();
}

class _VoiceCommandButtonState extends State<VoiceCommandButton>
    with SingleTickerProviderStateMixin {
  bool _isRecording = false;
  bool _isProcessing = false;
  String _statusText = '';

  late AnimationController _pulseController;
  late Animation<double> _pulseAnim;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..repeat(reverse: true);
    _pulseAnim = Tween<double>(begin: 0.9, end: 1.1).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _handleVoicePress() async {
    if (_isRecording || _isProcessing) {
      // Stop recording
      setState(() {
        _isRecording = false;
        _isProcessing = true;
        _statusText = 'Processing...';
      });
      // In a real implementation, stop the audio recorder and get bytes
      // For now, simulate with a placeholder
      await Future.delayed(const Duration(milliseconds: 500));
      // Simulate transcription result
      setState(() {
        _isProcessing = false;
        _statusText = '';
      });
      // In production, call voiceService.transcribeAudio(audioBytes: ...)
      // and then widget.onTranscript(transcript)
      _showVoiceDialog();
    } else {
      // Start recording
      setState(() {
        _isRecording = true;
        _statusText = 'Listening...';
      });
    }
  }

  void _showVoiceDialog() {
    showDialog(
      context: context,
      builder: (ctx) => _VoiceInputDialog(
        onSubmit: (text) {
          if (text.trim().isNotEmpty) {
            widget.onTranscript(text.trim());
          }
        },
      ),
    );
    setState(() {
      _isRecording = false;
      _isProcessing = false;
      _statusText = '';
    });
  }

  @override
  Widget build(BuildContext context) {
    final isActive = _isRecording || _isProcessing;
    final activeColor = _isProcessing ? AppTheme.warning : AppTheme.danger;

    if (widget.compact) {
      return AnimatedBuilder(
        animation: _pulseAnim,
        builder: (context, child) {
          return Transform.scale(
            scale: isActive ? _pulseAnim.value : 1.0,
            child: IconButton(
              icon: Icon(
                _isProcessing
                    ? Icons.hourglass_empty
                    : isActive
                        ? Icons.mic
                        : Icons.mic_none,
                color: isActive ? activeColor : AppTheme.text2(context),
              ),
              onPressed: _handleVoicePress,
              tooltip: isActive ? _statusText : 'Voice input',
            ),
          );
        },
      );
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        AnimatedBuilder(
          animation: _pulseAnim,
          builder: (context, child) {
            return Transform.scale(
              scale: isActive ? _pulseAnim.value : 1.0,
              child: GestureDetector(
                onTap: _handleVoicePress,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: isActive
                        ? activeColor
                        : AppTheme.primaryDark,
                    boxShadow: isActive
                        ? [
                            BoxShadow(
                              color: activeColor.withOpacity(0.4),
                              blurRadius: 16,
                              spreadRadius: 4,
                            ),
                          ]
                        : AppTheme.subtleShadow(context),
                  ),
                  child: Icon(
                    _isProcessing
                        ? Icons.hourglass_empty
                        : isActive
                            ? Icons.mic
                            : Icons.mic_none,
                    color: Colors.white,
                    size: 26,
                  ),
                ),
              ),
            );
          },
        ),
        if (_statusText.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              _statusText,
              style: TextStyle(
                fontSize: 11,
                color: isActive ? activeColor : AppTheme.text2(context),
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
      ],
    );
  }
}

/// Dialog for typing/confirming voice input (fallback when mic isn't available)
class _VoiceInputDialog extends StatefulWidget {
  final Function(String text) onSubmit;

  const _VoiceInputDialog({required this.onSubmit});

  @override
  State<_VoiceInputDialog> createState() => _VoiceInputDialogState();
}

class _VoiceInputDialogState extends State<_VoiceInputDialog> {
  final TextEditingController _controller = TextEditingController();
  final List<String> _suggestions = [
    'Analyze this submission',
    'Find similar cyber risks',
    'Summarize the key findings',
    'What are the main exclusions?',
    'Compare with market rates',
  ];

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: AppTheme.primaryDark.withOpacity(0.1),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.mic, color: AppTheme.primaryDark, size: 20),
          ),
          const SizedBox(width: 10),
          const Text('Voice Command', style: TextStyle(fontSize: 16)),
        ],
      ),
      content: SizedBox(
        width: 320,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: _controller,
              autofocus: true,
              decoration: const InputDecoration(
                hintText: 'Type or speak your command...',
                border: OutlineInputBorder(),
              ),
              onSubmitted: (text) {
                widget.onSubmit(text);
                Navigator.pop(context);
              },
            ),
            const SizedBox(height: 12),
            Text(
              'SUGGESTIONS',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                color: AppTheme.text2(context),
                letterSpacing: 1,
              ),
            ),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: _suggestions.map((s) {
                return ActionChip(
                  label: Text(s, style: const TextStyle(fontSize: 11)),
                  onPressed: () {
                    _controller.text = s;
                  },
                  padding: const EdgeInsets.all(0),
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                );
              }).toList(),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton.icon(
          onPressed: () {
            widget.onSubmit(_controller.text);
            Navigator.pop(context);
          },
          icon: const Icon(Icons.send, size: 16),
          label: const Text('Send'),
          style: ElevatedButton.styleFrom(
            backgroundColor: AppTheme.primaryDark,
          ),
        ),
      ],
    );
  }
}
