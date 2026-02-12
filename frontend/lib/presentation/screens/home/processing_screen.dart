import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import 'dart:async';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';

/// Processing Screen - Shows 5-Agent AI processing with detailed progress
class ProcessingScreen extends StatefulWidget {
  final String documentId;

  const ProcessingScreen({
    super.key,
    required this.documentId,
  });

  @override
  State<ProcessingScreen> createState() => _ProcessingScreenState();
}

class _ProcessingScreenState extends State<ProcessingScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  int _currentAgent = 0;
  String? _errorMessage;
  Map<String, dynamic>? _analysisResult;
  String _currentStatus = 'Initializing...';
  List<String> _agentLogs = [];

  // 5-Agent Multi-Agent System
  final List<AgentStep> _agents = [
    AgentStep(
      name: 'Document Classifier',
      title: 'Classifying Document',
      subtitle: 'Identifying document type and validating insurance relevance',
      icon: Icons.category_outlined,
      color: AppTheme.phaseExport, // Indigo
      tasks: [
        'Analyzing document structure',
        'Identifying document type (Slip, Policy, Certificate)',
        'Validating as insurance document',
        'Extracting document metadata',
      ],
    ),
    AgentStep(
      name: 'Data Extractor',
      title: 'Extracting Data',
      subtitle: 'Pulling all insurance fields from document',
      icon: Icons.storage_outlined,
      color: AppTheme.phaseStructure, // Violet
      tasks: [
        'Extracting insured information',
        'Identifying coverage details',
        'Parsing monetary values',
        'Extracting dates and terms',
        'Finding policy numbers and references',
      ],
    ),
    AgentStep(
      name: 'Risk Analyst',
      title: 'Analyzing Risks',
      subtitle: 'Identifying risk factors and exposures',
      icon: Icons.analytics_outlined,
      color: AppTheme.phaseRefine, // Pink
      tasks: [
        'Identifying primary risk factors',
        'Analyzing exposure areas',
        'Assessing territorial risks',
        'Evaluating industry-specific hazards',
        'Rating overall risk profile',
      ],
    ),
    AgentStep(
      name: 'Senior Underwriter',
      title: 'Underwriting Decision',
      subtitle: 'Making GO/NO-GO/REFER recommendation',
      icon: Icons.gavel_outlined,
      color: AppTheme.analysisCyan, // Teal
      tasks: [
        'Reviewing risk assessment',
        'Calculating suggested premium',
        'Determining appropriate deductibles',
        'Setting terms and conditions',
        'Making underwriting decision',
      ],
    ),
    AgentStep(
      name: 'Quality Assurance',
      title: 'Final Validation',
      subtitle: 'Ensuring accuracy and completeness',
      icon: Icons.verified_outlined,
      color: AppTheme.success, // Green
      tasks: [
        'Validating extracted data',
        'Cross-checking calculations',
        'Verifying decision logic',
        'Preparing final report',
        'Quality score assessment',
      ],
    ),
  ];

  int _currentTaskIndex = 0;
  Timer? _taskTimer;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat();

    _checkAuthAndProcess();
  }

  void _checkAuthAndProcess() {
    if (!authService.isLoggedIn) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          context.go('/login');
        }
      });
      return;
    }
    _processDocuments();
  }

  void _startTaskAnimation() {
    _taskTimer?.cancel();
    _taskTimer = Timer.periodic(const Duration(milliseconds: 800), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }

      final currentAgent = _agents[_currentAgent];
      if (_currentTaskIndex < currentAgent.tasks.length - 1) {
        setState(() {
          _currentTaskIndex++;
          _agentLogs.add('${currentAgent.name}: ${currentAgent.tasks[_currentTaskIndex]}');
          if (_agentLogs.length > 6) {
            _agentLogs.removeAt(0);
          }
        });
      }
    });
  }

  Future<void> _processDocuments() async {
    final token = widget.documentId;

    try {
      // Agent 1: Document Classifier
      _updateAgent(0, 'Classifying document type...');
      _startTaskAnimation();
      await Future.delayed(const Duration(milliseconds: 1200));

      // Agent 2: Data Extractor - Start the actual API call
      _updateAgent(1, 'Extracting insurance data...');

      // Use longer timeout for OCR processing (up to 5 minutes)
      final response = await authService.postLong('/upload-sessions/$token/process');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _analysisResult = data['analysis'];
        final assessmentId = data['assessment_id'];

        // Agent 3: Risk Analyst
        _updateAgent(2, 'Analyzing risk factors...');
        await Future.delayed(const Duration(milliseconds: 1000));

        // Agent 4: Senior Underwriter
        _updateAgent(3, 'Making underwriting decision...');
        await Future.delayed(const Duration(milliseconds: 1000));

        // Agent 5: Quality Assurance
        _updateAgent(4, 'Validating and finalizing...');
        await Future.delayed(const Duration(milliseconds: 800));

        // Complete
        _taskTimer?.cancel();
        setState(() {
          _currentAgent = 5;
          _currentStatus = 'Analysis Complete!';
          _agentLogs.add('All agents completed successfully');
        });

        await Future.delayed(const Duration(milliseconds: 500));

        // Navigate to results with the actual assessment ID
        if (mounted) {
          context.go('/reports/results/$assessmentId', extra: _analysisResult);
        }
      } else if (response.statusCode == 401) {
        if (mounted) {
          context.go('/login');
        }
      } else {
        _taskTimer?.cancel();
        setState(() {
          _errorMessage = 'Analysis failed: ${response.statusCode}';
        });
      }
    } catch (e) {
      _taskTimer?.cancel();
      setState(() {
        _errorMessage = 'Error: $e';
      });
    }
  }

  void _updateAgent(int index, String status) {
    if (!mounted) return;
    setState(() {
      _currentAgent = index;
      _currentStatus = status;
      _currentTaskIndex = 0;
      _agentLogs.add('${_agents[index].name} started');
      if (_agentLogs.length > 6) {
        _agentLogs.removeAt(0);
      }
    });
    _startTaskAnimation();
  }

  @override
  void dispose() {
    _animationController.dispose();
    _taskTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const SizedBox(height: 20),

              // Header
              Row(
                children: [
                  IconButton(
                    onPressed: () => context.go('/home'),
                    icon: Icon(Icons.close, color: AppTheme.textSecondary),
                  ),
                  Expanded(
                    child: Text(
                      'Multi-Agent Analysis',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.textPrimary,
                        fontFamily: 'Inter',
                      ),
                    ),
                  ),
                  const SizedBox(width: 48),
                ],
              ),

              const SizedBox(height: 20),

              // Current Agent Icon with Animation
              _buildCurrentAgentIndicator(),

              const SizedBox(height: 16),

              // Current Status
              Text(
                _currentStatus,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: _errorMessage != null ? AppTheme.danger : AppTheme.textPrimary,
                  fontFamily: 'Inter',
                ),
              ),

              if (_errorMessage != null) ...[
                const SizedBox(height: 8),
                Text(
                  _errorMessage!,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 14,
                    color: AppTheme.danger,
                    fontFamily: 'Inter',
                  ),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: () => context.go('/home'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryDark,
                  ),
                  child: const Text('Go Back'),
                ),
              ],

              const SizedBox(height: 24),

              // Agent Pipeline
              Expanded(
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '5-Agent Pipeline',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textSecondary,
                          fontFamily: 'Inter',
                        ),
                      ),
                      const SizedBox(height: 12),

                      // Agent Steps
                      ...List.generate(
                        _agents.length,
                        (index) => _buildAgentItem(_agents[index], index),
                      ),

                      const Spacer(),

                      // Live Log
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: AppTheme.darkBg,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Container(
                                  width: 8,
                                  height: 8,
                                  decoration: BoxDecoration(
                                    color: _errorMessage != null ? AppTheme.danger : AppTheme.success,
                                    shape: BoxShape.circle,
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Text(
                                  'Live Activity',
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    color: AppTheme.textSecondary,
                                    fontFamily: 'monospace',
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            SizedBox(
                              height: 80,
                              child: ListView.builder(
                                itemCount: _agentLogs.length,
                                reverse: true,
                                itemBuilder: (context, index) {
                                  final log = _agentLogs[_agentLogs.length - 1 - index];
                                  return Padding(
                                    padding: const EdgeInsets.only(bottom: 4),
                                    child: Text(
                                      '> $log',
                                      style: TextStyle(
                                        fontSize: 11,
                                        color: AppTheme.textSecondary,
                                        fontFamily: 'monospace',
                                      ),
                                    ),
                                  );
                                },
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 16),

              // Overall Progress
              Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Overall Progress',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                      Text(
                        '${((_currentAgent / _agents.length) * 100).toInt()}%',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.primaryDark,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: LinearProgressIndicator(
                      value: _currentAgent / _agents.length,
                      backgroundColor: AppTheme.border,
                      valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primaryDark),
                      minHeight: 10,
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 20),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCurrentAgentIndicator() {
    if (_currentAgent >= _agents.length) {
      // Completed
      return Container(
        width: 100,
        height: 100,
        decoration: BoxDecoration(
          color: AppTheme.success,
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: AppTheme.success.withOpacity(0.3),
              blurRadius: 20,
              spreadRadius: 5,
            ),
          ],
        ),
        child: Icon(
          Icons.check,
          size: 48,
          color: Colors.white,
        ),
      );
    }

    final agent = _agents[_currentAgent];
    return Stack(
      alignment: Alignment.center,
      children: [
        // Outer rotating ring
        RotationTransition(
          turns: _animationController,
          child: Container(
            width: 110,
            height: 110,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: SweepGradient(
                colors: [
                  agent.color.withOpacity(0.1),
                  agent.color,
                  agent.color.withOpacity(0.1),
                ],
              ),
            ),
          ),
        ),
        // Inner circle with icon
        Container(
          width: 80,
          height: 80,
          decoration: BoxDecoration(
            color: AppTheme.surface,
            shape: BoxShape.circle,
            border: Border.all(color: agent.color, width: 2),
            boxShadow: [
              BoxShadow(
                color: agent.color.withOpacity(0.2),
                blurRadius: 15,
                spreadRadius: 3,
              ),
            ],
          ),
          child: Icon(
            agent.icon,
            size: 36,
            color: agent.color,
          ),
        ),
      ],
    );
  }

  Widget _buildAgentItem(AgentStep agent, int index) {
    final isCompleted = index < _currentAgent;
    final isActive = index == _currentAgent;

    return Padding(
      padding: EdgeInsets.only(bottom: index < _agents.length - 1 ? 10 : 0),
      child: Row(
        children: [
          // Agent indicator
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: isCompleted
                  ? agent.color
                  : isActive
                      ? agent.color.withOpacity(0.2)
                      : AppTheme.border,
              shape: BoxShape.circle,
              border: isActive ? Border.all(color: agent.color, width: 2) : null,
            ),
            child: Center(
              child: isCompleted
                  ? const Icon(Icons.check, color: Colors.white, size: 16)
                  : isActive
                      ? SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                            color: agent.color,
                            strokeWidth: 2,
                          ),
                        )
                      : Text(
                          '${index + 1}',
                          style: TextStyle(
                            color: AppTheme.textHint,
                            fontWeight: FontWeight.w600,
                            fontSize: 12,
                          ),
                        ),
            ),
          ),
          const SizedBox(width: 12),

          // Agent content
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  agent.name,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: isCompleted || isActive
                        ? agent.color
                        : AppTheme.textHint,
                    fontFamily: 'Inter',
                  ),
                ),
                if (isActive && _currentTaskIndex < agent.tasks.length)
                  Text(
                    agent.tasks[_currentTaskIndex],
                    style: TextStyle(
                      fontSize: 11,
                      color: AppTheme.textSecondary,
                      fontFamily: 'Inter',
                    ),
                  ),
              ],
            ),
          ),

          // Status icon
          if (isCompleted)
            Icon(Icons.check_circle, color: agent.color, size: 18)
          else if (isActive)
            SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(
                color: agent.color,
                strokeWidth: 2,
              ),
            ),
        ],
      ),
    );
  }
}

class AgentStep {
  final String name;
  final String title;
  final String subtitle;
  final IconData icon;
  final Color color;
  final List<String> tasks;

  AgentStep({
    required this.name,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.color,
    required this.tasks,
  });
}
