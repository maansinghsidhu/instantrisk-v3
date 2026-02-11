import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import 'dart:async';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/subscription_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Sanctions Screening Progress Screen
/// Shows real-time progress of sanctions screening with detailed step updates
class SanctionsScreeningProgressScreen extends StatefulWidget {
  final String assessmentId;
  final String level;

  const SanctionsScreeningProgressScreen({
    super.key,
    required this.assessmentId,
    required this.level,
  });

  @override
  State<SanctionsScreeningProgressScreen> createState() =>
      _SanctionsScreeningProgressScreenState();
}

class _SanctionsScreeningProgressScreenState
    extends State<SanctionsScreeningProgressScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;

  // Progress state
  String _currentStepId = '';
  String _currentStepName = '';
  String _currentStepDesc = 'Initializing screening...';
  int _stepIndex = 0;
  int _totalSteps = 5;
  double _progressPercent = 0;
  int _elapsedSeconds = 0;
  bool _isComplete = false;
  bool _hasError = false;
  String? _errorMessage;

  // Results
  String _overallStatus = 'pending';
  int _totalMatches = 0;
  double _highestScore = 0;
  List<Map<String, dynamic>> _stepResults = [];
  List<Map<String, dynamic>> _liveFindings = [];

  Timer? _elapsedTimer;
  DateTime? _startTime;
  String? _sessionId;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
    _startTime = DateTime.now();
    _startElapsedTimer();
    _startScreening();
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

  Color _getLevelColor() {
    switch (widget.level) {
      case 'quick':
        return const Color(0xFF2563EB); // Blue
      case 'enhanced':
        return const Color(0xFF7C3AED); // Purple
      case 'deep':
        return const Color(0xFF6366F1); // Indigo
      case 'full':
        return const Color(0xFFDC2626); // Red
      default:
        return const Color(0xFF7C3AED);
    }
  }

  String _getLevelName() {
    switch (widget.level) {
      case 'quick':
        return 'Quick Screening';
      case 'enhanced':
        return 'Enhanced Screening';
      case 'deep':
        return 'Deep Analysis';
      case 'full':
        return 'Full Investigation';
      default:
        return 'Screening';
    }
  }

  Future<void> _startScreening() async {
    try {
      setState(() {
        _currentStepDesc = 'Starting ${_getLevelName().toLowerCase()}...';
        _progressPercent = 5;
      });

      // Start async screening
      final response = await authService.post(
        '/sanctions/assessments/${widget.assessmentId}/screen-async?level=${widget.level}',
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        // Check if no entities were found in the document
        if (data['status'] == 'no_entities') {
          setState(() {
            _isComplete = true;
            _progressPercent = 100;
            _overallStatus = 'no_entities';
            _currentStepDesc = data['message'] ?? 'No entities found in assessment to screen';
          });
          _elapsedTimer?.cancel();
          return;
        }

        _sessionId = data['session_id'];
        _totalSteps = data['steps_count'] ?? 5;

        setState(() {
          _currentStepDesc = 'Connecting to screening service...';
        });

        // Connect WebSocket for progress updates
        _connectWebSocket(_sessionId!);
      } else {
        final errorData = jsonDecode(response.body);
        _handleError(errorData['detail'] ?? 'Failed to start screening');
      }
    } catch (e) {
      _handleError('Error starting screening: $e');
    }
  }

  void _connectWebSocket(String sessionId) {
    try {
      final wsUrl = authService.baseUrl
          .replaceFirst('https://', 'wss://')
          .replaceFirst('http://', 'ws://');

      _channel = WebSocketChannel.connect(
        Uri.parse('$wsUrl/sanctions/ws/$sessionId'),
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
          _handleError('Connection error: $error');
        },
        onDone: () {
          if (!_isComplete && !_hasError) {
            _handleError('Connection closed unexpectedly');
          }
        },
      );
    } catch (e) {
      _handleError('Failed to connect: $e');
    }
  }

  void _handleWebSocketMessage(Map<String, dynamic> message) {
    final type = message['type'] as String?;

    switch (type) {
      case 'progress':
        setState(() {
          _currentStepId = message['step_id'] ?? '';
          _currentStepName = message['step_name'] ?? '';
          _currentStepDesc = message['step_description'] ?? 'Processing...';
          _stepIndex = message['step_index'] ?? 0;
          _totalSteps = message['total_steps'] ?? _totalSteps;
          _progressPercent = (message['progress_percent'] ?? 0).toDouble();
          _elapsedSeconds = message['elapsed_seconds'] ?? _elapsedSeconds;
        });
        break;

      case 'result':
        setState(() {
          // Add step result
          _stepResults.add({
            'step_id': message['step_id'],
            'step_name': message['step_name'],
            'status': message['status'],
            'matches': message['matches'] ?? [],
            'entities_checked': message['entities_checked'] ?? 0,
            'closest_match': message['closest_match'],
          });

          // Update live findings
          if (message['live_findings'] != null) {
            _liveFindings = List<Map<String, dynamic>>.from(message['live_findings']);
          }
        });
        break;

      case 'complete':
        setState(() {
          _isComplete = true;
          _progressPercent = 100;
          _overallStatus = message['overall_status'] ?? 'clear';
          _totalMatches = message['total_matches'] ?? 0;
          _highestScore = (message['highest_score'] ?? 0).toDouble();

          // Update live findings one last time
          if (message['live_findings'] != null) {
            _liveFindings = List<Map<String, dynamic>>.from(message['live_findings']);
          }
        });
        _elapsedTimer?.cancel();
        break;

      case 'error':
        _handleError(message['message'] ?? 'Screening failed');
        break;

      case 'keepalive':
        // Ignore keepalive messages
        break;
    }
  }

  void _handleError(String message) {
    setState(() {
      _hasError = true;
      _errorMessage = message;
    });
    _elapsedTimer?.cancel();
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _subscription?.cancel();
    _channel?.sink.close();
    _elapsedTimer?.cancel();
    super.dispose();
  }

  String _formatTime(int seconds) {
    final minutes = seconds ~/ 60;
    final secs = seconds % 60;
    return '${minutes.toString().padLeft(2, '0')}:${secs.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final levelColor = _getLevelColor();

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: AppTheme.surface,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: AppTheme.textPrimary),
          onPressed: () => context.pop(),
        ),
        title: Text(
          _getLevelName(),
          style: const TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
          ),
        ),
        centerTitle: true,
      ),
      body: _hasError
          ? _buildErrorState()
          : _isComplete
              ? _buildCompleteState(levelColor)
              : _buildProgressState(levelColor),
    );
  }

  Widget _buildProgressState(Color levelColor) {
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
                        color: levelColor,
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
                            color: levelColor,
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

              const SizedBox(height: 24),

              // Current step indicator
              AnimatedBuilder(
                animation: _pulseController,
                builder: (context, child) {
                  return Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: levelColor.withOpacity(0.05 + (_pulseController.value * 0.05)),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: levelColor.withOpacity(0.2)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 10,
                          height: 10,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: levelColor,
                            boxShadow: [
                              BoxShadow(
                                color: levelColor.withOpacity(0.5),
                                blurRadius: 8,
                                spreadRadius: _pulseController.value * 2,
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 12),
                        Text(
                          _currentStepName.isEmpty ? 'Initializing' : _currentStepName,
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: levelColor,
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),

              const SizedBox(height: 12),

              // Detailed step description
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: levelColor.withOpacity(0.1),
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
                        color: levelColor,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      _currentStepDesc,
                      style: TextStyle(
                        fontSize: 12,
                        color: levelColor,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),

        // Checks and findings
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              // Live findings section
              if (_liveFindings.isNotEmpty) ...[
                Text(
                  AppLocalizations.of(context).liveFindings,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textHint,
                    letterSpacing: 1,
                  ),
                ),
                const SizedBox(height: 12),
                ..._buildLiveFindingsCards(levelColor),
                const SizedBox(height: 24),
              ],

              Text(
                AppLocalizations.of(context).checks,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textHint,
                  letterSpacing: 1,
                ),
              ),
              const SizedBox(height: 12),
              ..._buildChecksList(levelColor),
            ],
          ),
        ),

        // Background processing banner
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: levelColor.withOpacity(0.05),
            border: Border(top: BorderSide(color: levelColor.withOpacity(0.2))),
          ),
          child: SafeArea(
            child: Row(
              children: [
                Icon(Icons.info_outline, size: 20, color: levelColor),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'You can close this screen. We\'ll notify you when screening completes.',
                    style: TextStyle(
                      fontSize: 12,
                      color: levelColor,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  List<Widget> _buildLiveFindingsCards(Color levelColor) {
    return _liveFindings.reversed.take(8).map((finding) {
      final label = finding['label'] as String? ?? '';
      final value = finding['value'] as String? ?? '';
      final type = finding['type'] as String? ?? 'info';

      Color typeColor;
      IconData typeIcon;
      switch (type) {
        case 'success':
          typeColor = const Color(0xFF059669);
          typeIcon = Icons.check_circle;
          break;
        case 'warning':
          typeColor = const Color(0xFFF59E0B);
          typeIcon = Icons.warning;
          break;
        case 'error':
          typeColor = const Color(0xFFDC2626);
          typeIcon = Icons.error;
          break;
        default:
          typeColor = levelColor;
          typeIcon = Icons.info_outline;
      }

      return Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: typeColor.withOpacity(0.05),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: typeColor.withOpacity(0.2)),
        ),
        child: Row(
          children: [
            Icon(typeIcon, size: 18, color: typeColor),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppTheme.textSecondary,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 2),
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
            ),
          ],
        ),
      );
    }).toList();
  }

  List<Widget> _buildChecksList(Color levelColor) {
    // Build list of checks based on level
    final allSteps = _getStepsForLevel();

    return allSteps.asMap().entries.map((entry) {
      final index = entry.key;
      final step = entry.value;
      final stepName = step['name'] as String;

      // Check if this step has a result
      final result = _stepResults.firstWhere(
        (r) => r['step_name'] == stepName,
        orElse: () => {},
      );

      final isCompleted = result.isNotEmpty;
      final isCurrent = index == _stepIndex && !isCompleted;
      final isPending = index > _stepIndex && !isCompleted;

      final l10n = AppLocalizations.of(context);
      String statusText = isPending ? l10n.pending : isCurrent ? l10n.checking : l10n.done;
      Color statusColor = isPending
          ? AppTheme.textHint
          : isCurrent
              ? levelColor
              : const Color(0xFF059669);

      // Get match info if completed
      String? matchInfo;
      if (isCompleted) {
        final matches = result['matches'] as List? ?? [];
        if (matches.isNotEmpty) {
          statusText = '${matches.length} match${matches.length > 1 ? 'es' : ''}';
          statusColor = const Color(0xFFF59E0B);
        } else {
          matchInfo = '0 matches';
        }
      }

      return Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: isCurrent ? levelColor.withOpacity(0.05) : AppTheme.surface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: isCurrent ? levelColor : AppTheme.border,
            width: isCurrent ? 2 : 1,
          ),
        ),
        child: Row(
          children: [
            // Status indicator
            Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isCompleted
                    ? statusColor.withOpacity(0.2)
                    : isCurrent
                        ? levelColor.withOpacity(0.2)
                        : AppTheme.background,
                border: Border.all(
                  color: isCompleted ? statusColor : isCurrent ? levelColor : AppTheme.border,
                  width: 2,
                ),
              ),
              child: isCompleted
                  ? Icon(Icons.check, color: statusColor, size: 16)
                  : isCurrent
                      ? SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                            color: levelColor,
                            strokeWidth: 2,
                          ),
                        )
                      : null,
            ),
            const SizedBox(width: 12),

            // Step name
            Expanded(
              child: Text(
                stepName,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: isPending ? AppTheme.textSecondary : AppTheme.textPrimary,
                ),
              ),
            ),

            // Status
            Text(
              statusText,
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
                color: statusColor,
              ),
            ),
          ],
        ),
      );
    }).toList();
  }

  List<Map<String, String>> _getStepsForLevel() {
    switch (widget.level) {
      case 'quick':
        return [
          {'name': 'OFAC SDN List'},
          {'name': 'EU Consolidated'},
          {'name': 'UN Security Council'},
        ];
      case 'standard':
        return [
          {'name': 'OFAC SDN List'},
          {'name': 'EU Consolidated'},
          {'name': 'UN Security Council'},
          {'name': 'UK HMT'},
          {'name': 'Fuzzy Match'},
          {'name': 'Alias Check'},
          {'name': 'PEP Database'},
          {'name': 'Adverse Media'},
        ];
      case 'extensive':
      default:
        return [
          {'name': 'OFAC SDN List'},
          {'name': 'EU Consolidated'},
          {'name': 'UN Security Council'},
          {'name': 'UK HMT'},
          {'name': 'Global Lists'},
          {'name': 'Fuzzy Match'},
          {'name': 'Alias Check'},
          {'name': 'PEP Database'},
          {'name': 'Adverse Media'},
          {'name': 'Ownership Chains'},
          {'name': 'Related Entities'},
          {'name': 'Network Mapping'},
          {'name': 'Historical Analysis'},
          {'name': 'AI Pattern Detection'},
          {'name': 'Risk Scoring'},
        ];
    }
  }

  Widget _buildCompleteState(Color levelColor) {
    Color statusColor;
    IconData statusIcon;
    String statusText;
    String? statusSubtitle;

    final l10n = AppLocalizations.of(context);
    switch (_overallStatus) {
      case 'clear':
        statusColor = const Color(0xFF059669);
        statusIcon = Icons.check_circle;
        statusText = l10n.clear;
        break;
      case 'review':
        statusColor = const Color(0xFFF59E0B);
        statusIcon = Icons.warning;
        statusText = l10n.reviewRequired;
        break;
      case 'match':
        statusColor = const Color(0xFFDC2626);
        statusIcon = Icons.dangerous;
        statusText = l10n.matchFound;
        break;
      case 'no_entities':
        statusColor = const Color(0xFF6B7280);
        statusIcon = Icons.info_outline;
        statusText = l10n.noEntitiesFound;
        statusSubtitle = 'No names or entities could be extracted from this document for sanctions screening.';
        break;
      default:
        statusColor = levelColor;
        statusIcon = Icons.help_outline;
        statusText = l10n.complete;
    }

    return Column(
      children: [
        // Status header
        Container(
          padding: const EdgeInsets.all(32),
          color: statusColor.withOpacity(0.1),
          child: Column(
            children: [
              Container(
                width: 100,
                height: 100,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: statusColor.withOpacity(0.2),
                ),
                child: Icon(
                  statusIcon,
                  size: 56,
                  color: statusColor,
                ),
              ),
              const SizedBox(height: 20),
              Text(
                statusText,
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w700,
                  color: statusColor,
                  letterSpacing: 1,
                ),
              ),
              const SizedBox(height: 8),
              if (statusSubtitle != null)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Text(
                    statusSubtitle,
                    style: const TextStyle(
                      fontSize: 14,
                      color: AppTheme.textSecondary,
                    ),
                    textAlign: TextAlign.center,
                  ),
                )
              else
                Text(
                  'Completed in ${_formatTime(_elapsedSeconds)}',
                  style: const TextStyle(
                    fontSize: 14,
                    color: AppTheme.textSecondary,
                  ),
                ),
            ],
          ),
        ),

        // Stats - only show if we actually did screening (not for no_entities)
        if (_overallStatus != 'no_entities')
          Container(
            padding: const EdgeInsets.all(20),
            color: AppTheme.surface,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildStat('Checks', '$_totalSteps'),
                _buildStat('Matches', '$_totalMatches'),
                _buildStat('Score', '${_highestScore.toStringAsFixed(0)}%'),
              ],
            ),
          ),

        // Findings list
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              if (_overallStatus == 'no_entities') ...[
                // Show helpful message when no entities found
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Column(
                    children: [
                      Icon(
                        Icons.document_scanner_outlined,
                        size: 48,
                        color: AppTheme.textHint,
                      ),
                      const SizedBox(height: 16),
                      const Text(
                        'What does this mean?',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'The document analysis did not identify any person names, company names, or other entities that could be screened against sanctions lists.\n\nThis could happen if:\n- The document is empty or contains only numbers/codes\n- The text could not be extracted properly\n- The document type does not contain named entities',
                        style: TextStyle(
                          fontSize: 14,
                          color: AppTheme.textSecondary,
                          height: 1.5,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ] else if (_liveFindings.isNotEmpty) ...[
                Text(
                  l10n.screeningResults,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textHint,
                    letterSpacing: 1,
                  ),
                ),
                const SizedBox(height: 12),
                ..._buildLiveFindingsCards(levelColor),
              ],
            ],
          ),
        ),

        // Action button
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: AppTheme.surface,
            border: Border(top: BorderSide(color: AppTheme.border)),
          ),
          child: SafeArea(
            child: SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  // Pop back to sanctions detail screen which will refresh data
                  context.pop();
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: _overallStatus == 'no_entities' ? statusColor : levelColor,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: Text(
                  _overallStatus == 'no_entities' ? l10n.goBack : l10n.viewFullResults,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildStat(String label, String value) {
    return Column(
      children: [
        Text(
          value,
          style: const TextStyle(
            fontSize: 28,
            fontWeight: FontWeight.w700,
            color: AppTheme.textPrimary,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: const TextStyle(
            fontSize: 12,
            color: AppTheme.textSecondary,
          ),
        ),
      ],
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 64, color: Colors.red),
            const SizedBox(height: 16),
            Text(
              _errorMessage ?? 'An error occurred',
              style: const TextStyle(
                fontSize: 16,
                color: Colors.red,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: () {
                setState(() {
                  _hasError = false;
                  _errorMessage = null;
                  _progressPercent = 0;
                  _stepIndex = 0;
                  _stepResults.clear();
                  _liveFindings.clear();
                });
                _startScreening();
              },
              child: Text(AppLocalizations.of(context).retry),
            ),
          ],
        ),
      ),
    );
  }
}
