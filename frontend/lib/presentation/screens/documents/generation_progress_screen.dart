import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:async';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';

/// Generation Progress + Preview Screen
/// Shows 19-agent pipeline progress across 6 phases with live preview.
class GenerationProgressScreen extends StatefulWidget {
  final String assessmentId;
  final List<Map<String, dynamic>> selectedDocuments;
  final Map<String, List<Map<String, dynamic>>>? clausesByDoc;

  const GenerationProgressScreen({
    super.key,
    required this.assessmentId,
    required this.selectedDocuments,
    this.clausesByDoc,
  });

  @override
  State<GenerationProgressScreen> createState() => _GenerationProgressScreenState();
}

class _GenerationProgressScreenState extends State<GenerationProgressScreen> {
  // 19 agents organized by 6 phases
  final List<_PipelinePhase> _phases = [
    _PipelinePhase('RESEARCH', AppTheme.phaseResearch, [
      _PipelineAgent('RiskResearcher', 'Searching knowledge base for relevant clauses', Icons.search),
      _PipelineAgent('ClauseExtractor', 'Extracting key provisions from found clauses', Icons.content_paste_search),
      _PipelineAgent('GapAnalyzer', 'Identifying coverage gaps and missing clauses', Icons.find_replace),
    ]),
    _PipelinePhase('STRUCTURE', AppTheme.phaseStructure, [
      _PipelineAgent('ClauseManager', 'Mapping clause IDs to standard wordings', Icons.library_books),
      _PipelineAgent('StructurePlanner', 'Planning document sections using CUAD patterns', Icons.account_tree),
      _PipelineAgent('LloydFormatter', 'Applying London market formatting standards', Icons.format_align_left),
    ]),
    _PipelinePhase('COMPOSE', AppTheme.phaseCompose, [
      _PipelineAgent('SectionDrafter', 'Drafting each section with selected clauses', Icons.edit_document),
      _PipelineAgent('ConsistencyChecker', 'Verifying values match across all sections', Icons.fact_check),
      _PipelineAgent('ToneUnifier', 'Ensuring consistent legal language throughout', Icons.record_voice_over),
    ]),
    _PipelinePhase('VALIDATE', AppTheme.phaseValidate, [
      _PipelineAgent('RiskChallenger', 'Challenging coverage adequacy', Icons.gavel),
      _PipelineAgent('ClauseVerifier', 'Verifying all clause IDs are valid standards', Icons.verified_user),
      _PipelineAgent('ComplianceReviewer', 'Lloyd\'s compliance and regulatory check', Icons.policy),
    ]),
    _PipelinePhase('REFINE', AppTheme.phaseRefine, [
      _PipelineAgent('HouseStyleAgent', 'Matching your uploaded document style', Icons.style),
      _PipelineAgent('LanguageVarier', 'Varying legal phrasing to avoid repetition', Icons.text_rotation_none),
      _PipelineAgent('ProofReader', 'Grammar, numbering, and cross-references', Icons.spellcheck),
      _PipelineAgent('ClauseCompiler', 'Inserting full ACORD standard wordings', Icons.integration_instructions),
    ]),
    _PipelinePhase('EXPORT', AppTheme.phaseExport, [
      _PipelineAgent('ScheduleBuilder', 'Building schedules, appendices, and tables', Icons.table_chart),
      _PipelineAgent('PDFExporter', 'Generating PDF with Lloyd\'s formatting', Icons.picture_as_pdf),
      _PipelineAgent('QualityGate', 'Final quality checklist before delivery', Icons.check_circle_outline),
    ]),
  ];

  int _currentAgentIndex = 0;
  int _totalAgents = 0;
  bool _isComplete = false;
  bool _hasError = false;
  String? _errorMessage;
  List<Map<String, dynamic>> _generatedDocs = [];
  int _userClauseCount = 0;
  int _acordClauseCount = 0;
  int _aiClauseCount = 0;
  Timer? _progressTimer;

  List<_PipelineAgent> get _allAgents =>
      _phases.expand((p) => p.agents).toList();

  @override
  void initState() {
    super.initState();
    _totalAgents = _allAgents.length;
    _startGeneration();
  }

  @override
  void dispose() {
    _progressTimer?.cancel();
    super.dispose();
  }

  String? _jobId;

  Future<void> _startGeneration() async {
    setState(() {
      _allAgents[0].status = _AgentStatus.running;
    });
    _callGenerationAPI();
  }

  Future<void> _callGenerationAPI() async {
    try {
      // Step 1: POST to start generation — returns immediately with job_id
      final response = await authService.post(
        '/document-generation/generate',
        body: {
          'assessment_id': widget.assessmentId,
          'documents': widget.selectedDocuments.map((d) => d['type']).toList(),
          'clauses': widget.clausesByDoc,
        },
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _jobId = data['job_id'];
        if (_jobId == null) {
          _handleError('No job_id returned from server');
          return;
        }
        // Step 2: Start polling for real progress
        _pollJobStatus();
      } else {
        _handleError('Generation failed: ${response.statusCode}');
      }
    } catch (e) {
      _handleError('Document generation failed: $e. Please try again.');
    }
  }

  Future<void> _pollJobStatus() async {
    _progressTimer = Timer.periodic(const Duration(seconds: 2), (timer) async {
      if (_isComplete || _hasError) {
        timer.cancel();
        return;
      }
      try {
        final response = await authService.get('/generation-jobs/$_jobId/status');
        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);
          final status = data['status'] as String?;
          final currentAgent = data['current_agent'] as String?;
          final steps = data['steps'] as List?;

          if (steps != null) {
            _updateAgentProgress(steps);
          } else if (currentAgent != null) {
            _updateAgentByName(currentAgent);
          }

          if (status == 'completed') {
            timer.cancel();
            await _fetchCompletedJob();
          } else if (status == 'failed') {
            timer.cancel();
            _handleError(data['error_message'] ?? 'Generation failed on server');
          }
        }
      } catch (e) {
        // Don't stop polling on transient errors
      }
    });
  }

  void _updateAgentProgress(List steps) {
    final allAgents = _allAgents;
    for (final step in steps) {
      final agentName = step['agent'] as String?;
      final stepStatus = step['status'] as String?;
      if (agentName == null) continue;

      final idx = allAgents.indexWhere((a) => a.name == agentName);
      if (idx == -1) continue;

      setState(() {
        if (stepStatus == 'completed') {
          allAgents[idx].status = _AgentStatus.complete;
        } else if (stepStatus == 'running') {
          allAgents[idx].status = _AgentStatus.running;
          _currentAgentIndex = idx;
        }
        // pending stays pending
      });
    }
  }

  void _updateAgentByName(String currentAgent) {
    final allAgents = _allAgents;
    final idx = allAgents.indexWhere((a) => a.name == currentAgent);
    if (idx == -1) return;

    setState(() {
      // Mark all before current as complete
      for (int i = 0; i < idx; i++) {
        allAgents[i].status = _AgentStatus.complete;
      }
      allAgents[idx].status = _AgentStatus.running;
      _currentAgentIndex = idx;
    });
  }

  Future<void> _fetchCompletedJob() async {
    try {
      final response = await authService.get('/generation-jobs/$_jobId');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final outputs = data['agent_outputs'] as Map<String, dynamic>?;

        setState(() {
          for (final agent in _allAgents) {
            agent.status = _AgentStatus.complete;
          }
          _isComplete = true;

          if (outputs != null) {
            _generatedDocs = (outputs['documents'] as List?)
                ?.map((d) => Map<String, dynamic>.from(d))
                .toList() ?? [];

            // Build source counts from documents
            int userCount = 0, acordCount = 0, aiCount = 0;
            for (final doc in _generatedDocs) {
              final attr = doc['source_attribution'] as Map<String, dynamic>?;
              if (attr != null) {
                userCount += (attr['user'] as num?)?.toInt() ?? 0;
                acordCount += (attr['acord'] as num?)?.toInt() ?? 0;
                aiCount += (attr['ai_generated'] as num?)?.toInt() ?? 0;
              }
            }
            _userClauseCount = userCount;
            _acordClauseCount = acordCount;
            _aiClauseCount = aiCount;
          }
        });
      } else {
        _handleError('Failed to fetch generated documents');
      }
    } catch (e) {
      _handleError('Failed to fetch results: $e');
    }
  }

  void _handleError(String message) {
    _progressTimer?.cancel();
    setState(() {
      _hasError = true;
      _errorMessage = message;
      final allAgents = _allAgents;
      if (_currentAgentIndex < allAgents.length) {
        allAgents[_currentAgentIndex].status = _AgentStatus.error;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_ios, color: AppTheme.text1(context)),
          onPressed: () => context.pop(),
        ),
        title: Text(
          _isComplete ? 'Documents Ready' : 'Generating Documents',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.text1(context),
          ),
        ),
        centerTitle: true,
        actions: [
          if (!_isComplete && !_hasError)
            Padding(
              padding: const EdgeInsets.only(right: 16),
              child: Center(
                child: Text(
                  '${_currentAgentIndex + 1}/$_totalAgents',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.text2(context),
                  ),
                ),
              ),
            ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Overall progress bar
            if (!_isComplete) _buildOverallProgress(),
            if (!_isComplete) const SizedBox(height: 16),

            // Phase-grouped pipeline
            _buildPhasedPipeline(),
            const SizedBox(height: 24),

            if (_isComplete) ...[
              _buildCompletionBanner(),
              const SizedBox(height: 20),
              ..._generatedDocs.map(_buildDocCard),
              const SizedBox(height: 16),
              _buildSourceAttribution(),
            ],

            if (_hasError) _buildErrorCard(),
          ],
        ),
      ),
    );
  }

  Widget _buildOverallProgress() {
    final progress = _totalAgents > 0 ? _currentAgentIndex / _totalAgents : 0.0;
    final currentAgent = _currentAgentIndex < _allAgents.length
        ? _allAgents[_currentAgentIndex]
        : null;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2.5,
                  value: progress,
                  color: AppTheme.primaryDark,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  currentAgent?.name ?? 'Processing...',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.text1(context),
                  ),
                ),
              ),
              Text(
                '${(progress * 100).toInt()}%',
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
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: progress,
              backgroundColor: AppTheme.borderOf(context),
              color: AppTheme.primaryDark,
              minHeight: 6,
            ),
          ),
          if (currentAgent != null) ...[
            const SizedBox(height: 6),
            Text(
              currentAgent.description,
              style: TextStyle(fontSize: 12, color: AppTheme.text2(context)),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildPhasedPipeline() {
    return Column(
      children: _phases.map((phase) {
        final isPhaseActive = phase.agents.any(
            (a) => a.status == _AgentStatus.running || a.status == _AgentStatus.complete);
        final isPhaseComplete = phase.agents.every((a) => a.status == _AgentStatus.complete);

        return Container(
          margin: const EdgeInsets.only(bottom: 12),
          decoration: BoxDecoration(
            color: AppTheme.surfaceOf(context),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isPhaseComplete
                  ? AppTheme.phaseCompose.withValues(alpha: 0.3)
                  : isPhaseActive
                      ? phase.color.withValues(alpha: 0.3)
                      : AppTheme.borderOf(context),
            ),
          ),
          child: Theme(
            data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
            child: ExpansionTile(
              initiallyExpanded: isPhaseActive && !isPhaseComplete,
              tilePadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
              childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
              leading: Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: (isPhaseComplete
                          ? AppTheme.phaseCompose
                          : isPhaseActive
                              ? phase.color
                              : AppTheme.textH(context))
                      .withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  isPhaseComplete ? Icons.check : Icons.circle,
                  size: 16,
                  color: isPhaseComplete
                      ? AppTheme.phaseCompose
                      : isPhaseActive
                          ? phase.color
                          : AppTheme.textH(context),
                ),
              ),
              title: Text(
                phase.name,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.2,
                  color: isPhaseActive ? AppTheme.text1(context) : AppTheme.textH(context),
                ),
              ),
              trailing: Text(
                '${phase.agents.where((a) => a.status == _AgentStatus.complete).length}/${phase.agents.length}',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: isPhaseComplete
                      ? AppTheme.phaseCompose
                      : AppTheme.text2(context),
                ),
              ),
              children: phase.agents.map((agent) => _buildAgentRow(agent, phase.color)).toList(),
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildAgentRow(_PipelineAgent agent, Color phaseColor) {
    Color iconColor;
    Widget statusWidget;

    switch (agent.status) {
      case _AgentStatus.pending:
        iconColor = AppTheme.textH(context);
        statusWidget = Icon(Icons.circle_outlined, size: 16, color: AppTheme.textH(context));
        break;
      case _AgentStatus.running:
        iconColor = phaseColor;
        statusWidget = SizedBox(
          width: 16,
          height: 16,
          child: CircularProgressIndicator(strokeWidth: 2, color: phaseColor),
        );
        break;
      case _AgentStatus.complete:
        iconColor = AppTheme.phaseCompose;
        statusWidget = Icon(Icons.check_circle, size: 16, color: AppTheme.phaseCompose);
        break;
      case _AgentStatus.error:
        iconColor = AppTheme.errorRed;
        statusWidget = Icon(Icons.error, size: 16, color: AppTheme.errorRed);
        break;
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          statusWidget,
          const SizedBox(width: 10),
          Icon(agent.icon, size: 14, color: iconColor),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  agent.name,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: agent.status == _AgentStatus.pending
                        ? AppTheme.textH(context)
                        : AppTheme.text1(context),
                  ),
                ),
                Text(
                  agent.description,
                  style: TextStyle(
                    fontSize: 10,
                    color: agent.status == _AgentStatus.running
                        ? phaseColor
                        : AppTheme.textH(context),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCompletionBanner() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.phaseCompose.withValues(alpha: 0.1),
            AppTheme.phaseCompose.withValues(alpha: 0.05),
          ],
        ),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.phaseCompose.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Icon(Icons.check_circle, color: AppTheme.phaseCompose, size: 24),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Generation Complete',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.text1(context),
                  ),
                ),
                Text(
                  '${_generatedDocs.length} document${_generatedDocs.length != 1 ? 's' : ''} generated by InstantRisk Engine',
                  style: TextStyle(fontSize: 13, color: AppTheme.text2(context)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDocCard(Map<String, dynamic> doc) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppTheme.primaryDark.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.description, color: AppTheme.primaryDark, size: 22),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  doc['title'] ?? doc['name'] ?? 'Document',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.text1(context),
                  ),
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppTheme.warningAmber.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        'DRAFT',
                        style: TextStyle(
                          fontSize: 9,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.warningAmber,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '${doc['total_sections'] ?? (doc['sections'] is List ? (doc['sections'] as List).length : doc['sections'] ?? 0)} sections',
                      style: TextStyle(fontSize: 11, color: AppTheme.textH(context)),
                    ),
                  ],
                ),
              ],
            ),
          ),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              IconButton(
                icon: const Icon(Icons.edit_document, size: 20, color: AppTheme.primaryDark),
                onPressed: () {
                  final docId = doc['id']?.toString() ?? '';
                  if (docId.isNotEmpty) {
                    context.go('/documents/edit/$docId', extra: {
                      'assessmentId': widget.assessmentId,
                    });
                  }
                },
                tooltip: 'Edit',
              ),
              IconButton(
                icon: Icon(Icons.visibility, size: 20, color: AppTheme.text2(context)),
                onPressed: () {
                  final docId = doc['id']?.toString() ?? '';
                  if (docId.isNotEmpty) {
                    context.go('/documents/preview/$docId', extra: {
                      'assessmentId': widget.assessmentId,
                    });
                  }
                },
                tooltip: 'View',
              ),
              IconButton(
                icon: Icon(Icons.download, size: 20, color: AppTheme.text2(context)),
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('PDF download coming soon')),
                  );
                },
                tooltip: 'Download PDF',
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSourceAttribution() {
    final total = _userClauseCount + _acordClauseCount + _aiClauseCount;
    if (total == 0) return const SizedBox.shrink();

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.info_outline, size: 14, color: AppTheme.textH(context)),
          const SizedBox(width: 6),
          Text(
            '$_userClauseCount from your uploads, $_acordClauseCount from ACORD, $_aiClauseCount engine-generated',
            style: TextStyle(fontSize: 11, color: AppTheme.textH(context)),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.errorRed.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.errorRed.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Icon(Icons.error_outline, color: AppTheme.errorRed),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  _errorMessage ?? 'Generation failed',
                  style: TextStyle(color: AppTheme.text1(context), fontSize: 14),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: () {
                setState(() {
                  _hasError = false;
                  _currentAgentIndex = 0;
                  for (final agent in _allAgents) {
                    agent.status = _AgentStatus.pending;
                  }
                });
                _startGeneration();
              },
              child: const Text('Retry'),
            ),
          ),
        ],
      ),
    );
  }
}

enum _AgentStatus { pending, running, complete, error }

class _PipelineAgent {
  final String name;
  final String description;
  final IconData icon;
  _AgentStatus status;

  _PipelineAgent(this.name, this.description, this.icon, {this.status = _AgentStatus.pending});
}

class _PipelinePhase {
  final String name;
  final Color color;
  final List<_PipelineAgent> agents;

  _PipelinePhase(this.name, this.color, this.agents);
}
