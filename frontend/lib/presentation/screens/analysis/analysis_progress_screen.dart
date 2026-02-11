import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import 'dart:async';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Analysis Progress Screen
/// Shows real-time progress of AI analysis with agent steps
class AnalysisProgressScreen extends StatefulWidget {
  final String assessmentId;
  final String mode;
  final int documentCount;
  final int totalChars;

  const AnalysisProgressScreen({
    super.key,
    required this.assessmentId,
    required this.mode,
    this.documentCount = 1,
    this.totalChars = 2000,
  });

  @override
  State<AnalysisProgressScreen> createState() => _AnalysisProgressScreenState();
}

class _AnalysisProgressScreenState extends State<AnalysisProgressScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;

  String _currentAgent = '';
  String _currentDescription = 'Initializing...';
  int _agentIndex = 0;
  int _totalAgents = 5;
  double _progressPercent = 0;
  int _elapsedSeconds = 0;
  int _estimatedRemaining = 0;
  bool _isComplete = false;
  bool _hasError = false;
  String? _errorMessage;
  Map<String, dynamic>? _result;
  List<Map<String, dynamic>> _completedSteps = [];

  Timer? _elapsedTimer;
  DateTime? _startTime;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
    _startTime = DateTime.now();
    // Initialize document count from widget parameters
    _totalDocuments = widget.documentCount;
    _currentDocument = 1;
    _startElapsedTimer();
    _startAnalysis();
  }

  void _startElapsedTimer() {
    _elapsedTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (_startTime != null && !_isComplete && !_hasError) {
        setState(() {
          _elapsedSeconds = DateTime.now().difference(_startTime!).inSeconds;
        });
      }
    });
  }

  String? _assessmentId;

  Future<void> _startAnalysis() async {
    try {
      // Set initial progress based on mode
      _setInitialProgress();

      // Update UI to show processing started
      setState(() {
        _currentAgent = 'Document Classifier';
        _currentDescription = 'Starting analysis...';
        _progressPercent = 5;
      });

      // Use async endpoint for real-time WebSocket updates
      final response = await authService.post(
        '/upload-sessions/${widget.assessmentId}/process-async?mode=${widget.mode}',
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _assessmentId = data['assessment_id']?.toString();
        final sessionId = data['session_id']?.toString();

        if (data['success'] == true && sessionId != null) {
          // Connect WebSocket for real-time progress updates
          _connectWebSocket(sessionId);
        } else {
          // Fallback to sync endpoint if async fails
          _startSyncAnalysis();
        }
      } else if (response.statusCode == 401) {
        _handleError('Session expired. Please log in again.');
      } else {
        // Fallback to sync endpoint
        _startSyncAnalysis();
      }
    } catch (e) {
      // Fallback to sync endpoint on error
      _startSyncAnalysis();
    }
  }

  /// Fallback synchronous analysis (used if async/WebSocket fails)
  Future<void> _startSyncAnalysis() async {
    try {
      setState(() {
        _currentDescription = 'Processing documents...';
      });

      final response = await authService.postLong(
        '/upload-sessions/${widget.assessmentId}/process?mode=${widget.mode}',
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _assessmentId = data['assessment_id']?.toString();

        if (data['success'] == true) {
          final analysis = data['analysis'] ?? {};
          final agentResults = analysis['agent_results'] ?? {};

          setState(() {
            _isComplete = true;
            _progressPercent = 100;
            _result = {
              'decision': analysis['decision'] ??
                         agentResults['underwriter']?['decision'] ??
                         'REFER',
              'confidence': analysis['confidence_score'] ?? 0.7,
              'agent_results': agentResults,
            };
          });
          _elapsedTimer?.cancel();
        } else {
          _handleError('Processing returned unsuccessful');
        }
      } else if (response.statusCode == 401) {
        _handleError('Session expired. Please log in again.');
      } else {
        final errorData = jsonDecode(response.body);
        _handleError(errorData['detail'] ?? 'Failed to start analysis: ${response.statusCode}');
      }
    } catch (e) {
      _handleError('Error starting analysis: $e');
    }
  }

  void _setInitialProgress() {
    setState(() {
      switch (widget.mode) {
        case 'quick':
          _totalAgents = 2;
          break;
        case 'go_no_go':
          _totalAgents = 4;  // DocumentClassifier, DataExtractor, RiskAnalyst, Underwriter
          break;
        case 'deep':
          _totalAgents = 9;  // All 9 agents from backend
          break;
      }
    });
  }

  void _connectWebSocket(String sessionId) {
    try {
      final wsUrl = authService.baseUrl
          .replaceFirst('https://', 'wss://')
          .replaceFirst('http://', 'ws://');

      _channel = WebSocketChannel.connect(
        Uri.parse('$wsUrl/analysis/ws/$sessionId'),
      );

      _subscription = _channel!.stream.listen(
        (data) {
          try {
            final message = jsonDecode(data as String);
            _handleWebSocketMessage(message);
          } catch (e) {
            // Ignore parse errors
          }
        },
        onError: (error) {
          // WebSocket error - continue polling instead
          _startPolling();
        },
        onDone: () {
          // WebSocket closed
          if (!_isComplete && !_hasError) {
            _startPolling();
          }
        },
      );
    } catch (e) {
      // Fall back to polling if WebSocket fails
      _startPolling();
    }
  }

  // Additional state for detailed sub-steps
  String _currentSubStepDesc = '';
  int _subStepIndex = 0;
  int _totalSubSteps = 0;

  // Document-level progress
  int _currentDocument = 0;
  int _totalDocuments = 0;
  String _documentName = '';

  void _handleWebSocketMessage(Map<String, dynamic> message) {
    final type = message['type'] as String?;

    switch (type) {
      case 'progress':
        setState(() {
          _currentAgent = message['current_agent'] ?? '';
          _agentIndex = message['agent_index'] ?? 0;
          _totalAgents = message['total_agents'] ?? _totalAgents;
          _currentDescription = message['description'] ?? 'Processing...';
          _progressPercent = (message['progress_percent'] ?? 0).toDouble();
          _estimatedRemaining = message['estimated_remaining'] ?? 0;

          // Handle detailed sub-step information
          _currentSubStepDesc = message['sub_step_description'] ?? '';
          _subStepIndex = message['sub_step_index'] ?? 0;
          _totalSubSteps = message['total_sub_steps'] ?? 0;

          // Handle document-level progress
          _currentDocument = message['current_document'] ?? 0;
          _totalDocuments = message['total_documents'] ?? widget.documentCount;
          _documentName = message['document_name'] ?? '';

          // Use overall progress from backend (cumulative, never resets)
          if (message['progress_percent'] != null) {
            _progressPercent = (message['progress_percent'] as num).toDouble();
          }

          // Add to completed steps
          if (message['status'] == 'completed') {
            _completedSteps.add({
              'agent': _currentAgent,
              'description': _currentDescription,
              'completed_at': DateTime.now().toIso8601String(),
            });
          }
        });
        break;

      case 'complete':
        // Update assessment ID from message
        if (message['assessment_id'] != null) {
          _assessmentId = message['assessment_id'].toString();
        }
        setState(() {
          _isComplete = true;
          _progressPercent = 100;
          _result = {
            'decision': message['decision'] ?? 'REFER',
            'confidence': message['confidence'] ?? 0.7,
            'risk_score': message['risk_score'] ?? 50,
            'processing_time': message['processing_time'] ?? _elapsedSeconds,
          };
        });
        _elapsedTimer?.cancel();
        break;

      case 'error':
        _handleError(message['message'] ?? 'Unknown error');
        break;
    }
  }

  Timer? _pollTimer;

  void _startPolling() {
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      await _pollProgress();
    });
  }

  Future<void> _pollProgress() async {
    try {
      final response = await authService.get(
        '/assessments/${widget.assessmentId}/status',
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        if (data['status'] == 'completed') {
          _pollTimer?.cancel();
          setState(() {
            _isComplete = true;
            _progressPercent = 100;
            _result = data['result'];
          });
          _elapsedTimer?.cancel();
        } else if (data['status'] == 'failed') {
          _pollTimer?.cancel();
          _handleError(data['error'] ?? 'Analysis failed');
        } else {
          // Update progress based on status
          setState(() {
            _currentAgent = data['current_agent'] ?? _currentAgent;
            _currentDescription = data['description'] ?? _currentDescription;
            if (data['progress'] != null) {
              _progressPercent = (data['progress'] as num).toDouble();
            }
          });
        }
      }
    } catch (e) {
      // Ignore polling errors
    }
  }

  void _handleError(String message) {
    setState(() {
      _hasError = true;
      _errorMessage = message;
    });
    _elapsedTimer?.cancel();
    _pollTimer?.cancel();
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _subscription?.cancel();
    _channel?.sink.close();
    _elapsedTimer?.cancel();
    _pollTimer?.cancel();
    super.dispose();
  }

  String _formatTime(int seconds) {
    final minutes = seconds ~/ 60;
    final secs = seconds % 60;
    return '${minutes.toString().padLeft(2, '0')}:${secs.toString().padLeft(2, '0')}';
  }

  Color _getModeColor() {
    switch (widget.mode) {
      case 'quick':
        return const Color(0xFFF59E0B);
      case 'go_no_go':
        return const Color(0xFF2563EB);
      case 'deep':
        return const Color(0xFF7C3AED);
      default:
        return AppTheme.primaryDark;
    }
  }

  String _getModeName(AppLocalizations l10n) {
    switch (widget.mode) {
      case 'quick':
        return l10n.quickAnalysis;
      case 'go_no_go':
        return 'Go/No-Go ${l10n.analysis}';
      case 'deep':
        return l10n.deepAnalysis;
      default:
        return l10n.analysis;
    }
  }

  void _handleBack() {
    if (!_isComplete && !_hasError) {
      _showCancelConfirmation();
    } else {
      // Navigate to home since we might have arrived via go() not push()
      context.go('/home');
    }
  }

  @override
  Widget build(BuildContext context) {
    final modeColor = _getModeColor();
    final l10n = AppLocalizations.of(context);

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) {
          _handleBack();
        }
      },
      child: Scaffold(
        backgroundColor: AppTheme.background,
        appBar: AppBar(
          backgroundColor: AppTheme.surface,
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.close, color: AppTheme.textPrimary),
            onPressed: _handleBack,
          ),
          title: Text(
            _getModeName(l10n),
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: modeColor,
              fontFamily: 'Inter',
            ),
          ),
          centerTitle: true,
        ),
        body: _hasError
            ? _buildErrorState(l10n)
            : _isComplete
                ? _buildCompleteState(l10n)
                : _buildProgressState(modeColor, l10n),
      ),
    );
  }

  Widget _buildProgressState(Color modeColor, AppLocalizations l10n) {
    return Column(
      children: [
        // Progress header
        Container(
          padding: const EdgeInsets.all(24),
          color: AppTheme.surface,
          child: Column(
            children: [
              // Animated progress indicator
              SizedBox(
                width: 120,
                height: 120,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    // Background circle
                    SizedBox(
                      width: 120,
                      height: 120,
                      child: CircularProgressIndicator(
                        value: 1,
                        strokeWidth: 8,
                        color: AppTheme.border,
                      ),
                    ),
                    // Progress circle
                    SizedBox(
                      width: 120,
                      height: 120,
                      child: CircularProgressIndicator(
                        value: _progressPercent / 100,
                        strokeWidth: 8,
                        color: modeColor,
                        strokeCap: StrokeCap.round,
                      ),
                    ),
                    // Percentage
                    Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          '${_progressPercent.toInt()}%',
                          style: TextStyle(
                            fontSize: 28,
                            fontWeight: FontWeight.w700,
                            color: modeColor,
                            fontFamily: 'Inter',
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          _formatTime(_elapsedSeconds),
                          style: const TextStyle(
                            fontSize: 14,
                            color: AppTheme.textSecondary,
                            fontFamily: 'Courier',
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 16),

              // Document & Agent progress indicator (always show if multiple docs)
              if (_totalDocuments > 1 || widget.documentCount > 1)
                Container(
                  width: double.infinity,
                  margin: const EdgeInsets.only(bottom: 16),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: modeColor.withOpacity(0.08),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: modeColor.withOpacity(0.3)),
                  ),
                  child: Column(
                    children: [
                      // Document progress row
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: modeColor.withOpacity(0.15),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Icon(
                              Icons.description,
                              size: 24,
                              color: modeColor,
                            ),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'DOCUMENT ${_currentDocument > 0 ? _currentDocument : 1} OF ${_totalDocuments > 0 ? _totalDocuments : widget.documentCount}',
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w700,
                                    color: modeColor,
                                    letterSpacing: 0.5,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                if (_documentName.isNotEmpty)
                                  Text(
                                    _documentName,
                                    style: const TextStyle(
                                      fontSize: 12,
                                      color: AppTheme.textSecondary,
                                    ),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                              ],
                            ),
                          ),
                          // Documents remaining badge
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(color: modeColor.withOpacity(0.3)),
                            ),
                            child: Text(
                              '${(_totalDocuments > 0 ? _totalDocuments : widget.documentCount) - (_currentDocument > 0 ? _currentDocument : 1)} left',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: modeColor,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      // Current agent badge
                      if (_currentAgent.isNotEmpty)
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Row(
                            children: [
                              Icon(Icons.smart_toy_outlined, size: 16, color: modeColor),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  'Agent: $_currentAgent',
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600,
                                    color: modeColor,
                                  ),
                                ),
                              ),
                              if (_currentSubStepDesc.isNotEmpty)
                                Expanded(
                                  child: Text(
                                    _currentSubStepDesc,
                                    style: const TextStyle(
                                      fontSize: 11,
                                      color: AppTheme.textSecondary,
                                    ),
                                    textAlign: TextAlign.right,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),

              // Current agent indicator
              AnimatedBuilder(
                animation: _pulseController,
                builder: (context, child) {
                  return Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: modeColor.withOpacity(0.05 + (_pulseController.value * 0.05)),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: modeColor.withOpacity(0.2)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 10,
                          height: 10,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: modeColor,
                            boxShadow: [
                              BoxShadow(
                                color: modeColor.withOpacity(0.5),
                                blurRadius: 8,
                                spreadRadius: _pulseController.value * 2,
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 12),
                        Text(
                          _currentAgent.isEmpty ? 'Initializing' : _currentAgent,
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: modeColor,
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),

              const SizedBox(height: 12),

              // Main description
              Text(
                _currentDescription,
                style: const TextStyle(
                  fontSize: 14,
                  color: AppTheme.textSecondary,
                ),
                textAlign: TextAlign.center,
              ),

              // Detailed sub-step description (if available)
              if (_currentSubStepDesc.isNotEmpty) ...[
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: modeColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      SizedBox(
                        width: 12,
                        height: 12,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: modeColor,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        _currentSubStepDesc,
                        style: TextStyle(
                          fontSize: 12,
                          color: modeColor,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),

        // Analysis summary
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              // Analysis summary - what's being done
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.border),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.analytics_outlined, size: 18, color: modeColor),
                        const SizedBox(width: 8),
                        Text(
                          'ANALYSIS SUMMARY',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: modeColor,
                            letterSpacing: 1,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    _buildSummaryRow('Mode', _getModeName(l10n)),
                    _buildSummaryRow('Documents', '${_totalDocuments > 0 ? _totalDocuments : widget.documentCount}'),
                    _buildSummaryRow('Characters', '${widget.totalChars > 0 ? "${widget.totalChars ~/ 1000}K" : "Calculating..."}'),
                    _buildSummaryRow('Agents', '$_totalAgents'),
                    _buildSummaryRow('Progress', '${_progressPercent.toInt()}%'),
                  ],
                ),
              ),
            ],
          ),
        ),

        // Background continuation banner
        Container(
          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.blue.withOpacity(0.08),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.blue.withOpacity(0.2)),
          ),
          child: Row(
            children: [
              Icon(Icons.info_outline, color: Colors.blue.shade600, size: 20),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  l10n.analysisCanContinueInBackground,
                  style: TextStyle(
                    color: Colors.blue.shade700,
                    fontSize: 13,
                    height: 1.3,
                  ),
                ),
              ),
            ],
          ),
        ),

        // Bottom info
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.surface,
            border: Border(top: BorderSide(color: AppTheme.border)),
          ),
          child: SafeArea(
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.timer_outlined, size: 16, color: AppTheme.textSecondary),
                const SizedBox(width: 6),
                Text(
                  _estimatedRemaining > 0
                      ? 'Estimated: ${_formatTime(_estimatedRemaining)} remaining'
                      : 'Processing...',
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  List<Widget> _buildAgentSteps(Color modeColor) {
    final agents = _getAgentsForMode();

    return agents.asMap().entries.map((entry) {
      final index = entry.key;
      final agent = entry.value;
      final isCompleted = index < _agentIndex;
      final isCurrent = index == _agentIndex - 1 || (index == 0 && _agentIndex == 0 && _currentAgent.isNotEmpty);
      final isPending = index >= _agentIndex;

      return Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: isCurrent ? modeColor.withOpacity(0.05) : AppTheme.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isCurrent ? modeColor : AppTheme.border,
            width: isCurrent ? 2 : 1,
          ),
        ),
        child: Row(
          children: [
            // Status indicator
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isCompleted
                    ? const Color(0xFF059669)
                    : isCurrent
                        ? modeColor
                        : AppTheme.background,
                border: Border.all(
                  color: isCompleted
                      ? const Color(0xFF059669)
                      : isCurrent
                          ? modeColor
                          : AppTheme.border,
                  width: 2,
                ),
              ),
              child: isCompleted
                  ? const Icon(Icons.check, color: Colors.white, size: 18)
                  : isCurrent
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            color: Colors.white,
                            strokeWidth: 2,
                          ),
                        )
                      : Text(
                          '${index + 1}',
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.textSecondary,
                          ),
                        ),
            ),
            const SizedBox(width: 16),

            // Agent info
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    agent['name'] as String,
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: isPending ? AppTheme.textSecondary : AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    agent['description'] as String,
                    style: TextStyle(
                      fontSize: 12,
                      color: isPending ? AppTheme.textHint : AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ),

            // Status text
            if (isCompleted)
              const Text(
                'Done',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: Color(0xFF059669),
                ),
              )
            else if (isCurrent)
              Text(
                'Running',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: modeColor,
                ),
              )
            else
              const Text(
                'Pending',
                style: TextStyle(
                  fontSize: 12,
                  color: AppTheme.textHint,
                ),
              ),
          ],
        ),
      );
    }).toList();
  }

  Widget _buildSummaryRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 13,
              color: AppTheme.textSecondary,
            ),
          ),
          Text(
            value,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            ),
          ),
        ],
      ),
    );
  }

  List<Map<String, String>> _getAgentsForMode() {
    switch (widget.mode) {
      case 'quick':
        return [
          {'name': 'Document Classifier', 'description': 'Identify document type'},
          {'name': 'Underwriter', 'description': 'Make decision'},
        ];
      case 'go_no_go':
        return [
          {'name': 'Document Classifier', 'description': 'Identify document type'},
          {'name': 'Data Extractor', 'description': 'Extract insurance data'},
          {'name': 'Risk Analyst', 'description': 'Analyze risk factors'},
          {'name': 'Underwriter', 'description': 'Make decision'},
        ];
      case 'deep':
      default:
        return [
          {'name': 'Document Classifier', 'description': 'Identify document type'},
          {'name': 'Data Extractor', 'description': 'Extract insurance data'},
          {'name': 'Financial Analyst', 'description': 'Analyze financial data'},
          {'name': 'Risk Analyst', 'description': 'Analyze risk factors'},
          {'name': 'Compliance Agent', 'description': 'Check regulatory compliance'},
          {'name': 'Exposure Analyst', 'description': 'Assess exposure levels'},
          {'name': 'Underwriter', 'description': 'Make decision'},
          {'name': 'Verification Agent', 'description': 'Verify data accuracy'},
          {'name': 'Quality Assurance', 'description': 'Final validation'},
        ];
    }
  }

  Widget _buildCompleteState(AppLocalizations l10n) {
    final decision = _result?['decision'] ?? 'REFER';
    final confidence = (_result?['confidence'] ?? 0.5) * 100;

    Color decisionColor;
    IconData decisionIcon;
    String decisionText;

    switch (decision) {
      case 'GO':
        decisionColor = const Color(0xFF059669);
        decisionIcon = Icons.check_circle;
        decisionText = 'Approved';
        break;
      case 'NO_GO':
        decisionColor = const Color(0xFFDC2626);
        decisionIcon = Icons.cancel;
        decisionText = 'Declined';
        break;
      default:
        decisionColor = const Color(0xFFF59E0B);
        decisionIcon = Icons.pending;
        decisionText = 'Refer';
    }

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Success icon
            Container(
              width: 100,
              height: 100,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: decisionColor.withOpacity(0.1),
              ),
              child: Icon(
                decisionIcon,
                size: 56,
                color: decisionColor,
              ),
            ),

            const SizedBox(height: 24),

            // Decision
            Text(
              decisionText,
              style: TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.w700,
                color: decisionColor,
                fontFamily: 'Inter',
              ),
            ),

            const SizedBox(height: 8),

            // Confidence
            Text(
              'Confidence: ${confidence.toStringAsFixed(0)}%',
              style: const TextStyle(
                fontSize: 16,
                color: AppTheme.textSecondary,
              ),
            ),

            const SizedBox(height: 8),

            // Time taken
            Text(
              'Completed in ${_formatTime(_elapsedSeconds)}',
              style: const TextStyle(
                fontSize: 14,
                color: AppTheme.textHint,
              ),
            ),

            const SizedBox(height: 32),

            // View results button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  final id = _assessmentId ?? widget.assessmentId;
                  context.go('/assessments/$id/results');
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: decisionColor,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: Text(
                  l10n.viewResults,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
              ),
            ),

            const SizedBox(height: 12),

            TextButton(
              onPressed: () => context.go('/home'),
              child: Text(l10n.backToDashboard),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorState(AppLocalizations l10n) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: const Color(0xFFDC2626).withOpacity(0.1),
              ),
              child: const Icon(
                Icons.error_outline,
                size: 48,
                color: Color(0xFFDC2626),
              ),
            ),

            const SizedBox(height: 24),

            Text(
              l10n.analysisFailed,
              style: const TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.w700,
                color: Color(0xFFDC2626),
              ),
            ),

            const SizedBox(height: 12),

            Text(
              _errorMessage ?? 'An unexpected error occurred',
              style: const TextStyle(
                fontSize: 14,
                color: AppTheme.textSecondary,
              ),
              textAlign: TextAlign.center,
            ),

            const SizedBox(height: 32),

            ElevatedButton.icon(
              onPressed: () {
                setState(() {
                  _hasError = false;
                  _errorMessage = null;
                  _progressPercent = 0;
                  _elapsedSeconds = 0;
                  _startTime = DateTime.now();
                });
                _startElapsedTimer();
                _startAnalysis();
              },
              icon: const Icon(Icons.refresh),
              label: Text(l10n.retry),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryDark,
                padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
              ),
            ),

            const SizedBox(height: 12),

            TextButton(
              onPressed: () => context.go('/home'),
              child: Text(l10n.goBack),
            ),
          ],
        ),
      ),
    );
  }

  void _showCancelConfirmation() {
    final l10n = AppLocalizations.of(context);
    showDialog(
      context: context,
      barrierDismissible: true,
      builder: (dialogContext) => AlertDialog(
        title: Text(l10n.leaveAnalysis),
        content: const Text(
          'The analysis is running. You can:\n\n'
          '• Run in background - analysis continues, check results later in Reports\n'
          '• Stay here - wait for completion',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: Text(l10n.stayHere),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              // Navigate to home - analysis continues in background
              context.go('/home');
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryDark,
            ),
            child: Text(l10n.runInBackground),
          ),
        ],
      ),
    );
  }
}
