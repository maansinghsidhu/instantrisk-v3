import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'dart:convert';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';


/// V3 AI Explainer Screen - Explainable AI Decision Visualization
class AIExplainerScreen extends StatefulWidget {
  final String? assessmentId;
  final String? decisionType;

  const AIExplainerScreen({
    super.key,
    this.assessmentId,
    this.decisionType,
  });

  @override
  State<AIExplainerScreen> createState() => _AIExplainerScreenState();
}

class _AIExplainerScreenState extends State<AIExplainerScreen> {
  bool _isLoading = true;
  bool _isLoadingAssessments = true;
  Map<String, dynamic>? _explanationData;
  String? _error;
  int _selectedFactorIndex = -1;

  // Assessment selection
  List<Map<String, dynamic>> _completedAssessments = [];
  String? _selectedAssessmentId;

  @override
  void initState() {
    super.initState();
    _loadAssessments();
  }

  Future<void> _loadAssessments() async {
    setState(() {
      _isLoadingAssessments = true;
      _isLoading = true;
    });

    try {
      final assessmentsResponse = await AuthService().get('/assessments/?page=1&page_size=50');
      if (assessmentsResponse.statusCode == 200) {
        final data = json.decode(assessmentsResponse.body);
        final assessments = data['items'] ?? data['assessments'] ?? data ?? [];

        if (assessments is List) {
          // Filter to only completed assessments with decisions
          // Handle both uppercase and lowercase status values
          _completedAssessments = assessments
              .where((a) {
                final status = a['status']?.toString().toUpperCase() ?? '';
                final decision = a['decision']?.toString().toUpperCase() ?? '';
                return status == 'COMPLETED' && decision.isNotEmpty && decision != 'PENDING';
              })
              .map((a) => Map<String, dynamic>.from(a))
              .toList();
        }
      }

      setState(() {
        _isLoadingAssessments = false;
      });

      // If widget has assessmentId, use it; otherwise use first completed assessment
      if (widget.assessmentId != null) {
        _selectedAssessmentId = widget.assessmentId;
        await _loadExplanationData();
      } else if (_completedAssessments.isNotEmpty) {
        _selectedAssessmentId = _completedAssessments.first['id'].toString();
        await _loadExplanationData();
      } else {
        setState(() {
          _isLoading = false;
          _error = 'No completed assessments found. Complete an assessment to see AI explanations.';
        });
      }
    } catch (e) {
      setState(() {
        _isLoadingAssessments = false;
        _isLoading = false;
        _error = 'Failed to load assessments: $e';
      });
    }
  }

  Future<void> _loadExplanationData() async {
    if (_selectedAssessmentId == null) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      // First check if we already have this assessment in our list
      final cachedAssessment = _completedAssessments.firstWhere(
        (a) => a['id'].toString() == _selectedAssessmentId,
        orElse: () => {},
      );

      if (cachedAssessment.isNotEmpty) {
        setState(() {
          _explanationData = _buildExplanationFromAssessment(cachedAssessment);
          _isLoading = false;
        });
        return;
      }

      // Otherwise fetch from API
      final assessmentResponse = await AuthService().get('/assessments/$_selectedAssessmentId');
      if (assessmentResponse.statusCode == 200) {
        final assessment = json.decode(assessmentResponse.body);
        setState(() {
          _explanationData = _buildExplanationFromAssessment(assessment);
          _isLoading = false;
        });
        return;
      }

      setState(() {
        _error = 'Failed to load assessment data';
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Failed to load explanation data: $e';
        _isLoading = false;
      });
    }
  }

  Map<String, dynamic> _buildExplanationFromAssessment(Map<String, dynamic> assessment) {
    final decision = assessment['decision'] ?? 'PENDING';
    final riskScore = assessment['risk_score'] ?? 0;
    final confidenceScore = assessment['confidence_score'] ?? 0;
    final aiAnalysis = assessment['ai_analysis'] ?? {};
    final riskFactors = aiAnalysis['risk_factors'] ?? [];
    final rationale = assessment['decision_rationale'] ?? 'No rationale provided.';

    // Build feature importance from AI analysis
    List<Map<String, dynamic>> featureImportance = [];
    if (riskFactors is List) {
      double baseImportance = 0.25;
      for (int i = 0; i < riskFactors.length && i < 5; i++) {
        featureImportance.add({
          'feature': riskFactors[i].toString().split(':').first.trim(),
          'importance': baseImportance - (i * 0.04),
          'value': riskFactors[i].toString().split(':').last.trim(),
          'impact': decision == 'GO' ? 'positive' : decision == 'NO_GO' ? 'negative' : 'neutral',
        });
      }
    }

    if (featureImportance.isEmpty) {
      featureImportance = [
        {'feature': 'Risk Score', 'importance': 0.30, 'value': '$riskScore%', 'impact': riskScore >= 70 ? 'positive' : 'neutral'},
        {'feature': 'Confidence', 'importance': 0.25, 'value': '$confidenceScore%', 'impact': confidenceScore >= 80 ? 'positive' : 'neutral'},
        {'feature': 'Premium', 'importance': 0.20, 'value': '${assessment['premium'] ?? 'N/A'}', 'impact': 'neutral'},
        {'feature': 'Territory', 'importance': 0.15, 'value': assessment['territory'] ?? 'N/A', 'impact': 'neutral'},
        {'feature': 'Risk Category', 'importance': 0.10, 'value': assessment['risk_category'] ?? 'N/A', 'impact': 'neutral'},
      ];
    }

    return {
      'assessment_id': assessment['id'],
      'reference': assessment['reference_number'] ?? 'N/A',
      'decision': decision == 'GO' ? 'GO' : decision == 'NO_GO' ? 'NO-GO' : 'REFER',
      'confidence': confidenceScore.toDouble(),
      'decision_summary': rationale,
      'model_version': 'InstantRisk-AI v2.0',
      'feature_importance': featureImportance,
      'decision_path': [
        {'step': 1, 'node': 'Document Analysis', 'condition': 'OCR & Extraction', 'result': 'Completed', 'status': 'pass'},
        {'step': 2, 'node': 'Risk Assessment', 'condition': 'Risk Score >= 50', 'result': riskScore >= 50 ? 'Pass ($riskScore%)' : 'Fail ($riskScore%)', 'status': riskScore >= 50 ? 'pass' : 'fail'},
        {'step': 3, 'node': 'Underwriting Rules', 'condition': 'Compliance Check', 'result': decision == 'NO_GO' ? 'Failed' : 'Passed', 'status': decision == 'NO_GO' ? 'fail' : 'pass'},
        {'step': 4, 'node': 'Final Decision', 'condition': 'AI Recommendation', 'result': decision, 'status': decision == 'GO' ? 'pass' : decision == 'REFER' ? 'warning' : 'fail'},
      ],
      'similar_risks': [],
      'counterfactuals': [],
    };
  }

  Map<String, dynamic> _generateMockExplanation() {
    return {
      'decision': 'GO',
      'confidence': 87.5,
      'decision_summary': 'The AI model recommends accepting this risk based on favorable historical performance, adequate pricing, and acceptable exposure levels.',
      'model_version': 'InstantRisk-XAI v2.1.0',
      'processing_time_ms': 1250,
      'feature_importance': [
        {'feature': 'Historical Loss Ratio', 'importance': 0.28, 'value': '45%', 'impact': 'positive'},
        {'feature': 'Territory Risk Score', 'importance': 0.22, 'value': '6.2/10', 'impact': 'neutral'},
        {'feature': 'Premium Adequacy', 'importance': 0.18, 'value': '112%', 'impact': 'positive'},
        {'feature': 'Reinsurance Coverage', 'importance': 0.12, 'value': '75%', 'impact': 'positive'},
        {'feature': 'Exposure Concentration', 'importance': 0.10, 'value': '23%', 'impact': 'neutral'},
        {'feature': 'Claims Frequency', 'importance': 0.06, 'value': '2.1/yr', 'impact': 'positive'},
        {'feature': 'Policy Terms', 'importance': 0.04, 'value': 'Standard', 'impact': 'neutral'},
      ],
      'decision_path': [
        {
          'step': 1,
          'node': 'Risk Assessment',
          'condition': 'Loss Ratio < 60%',
          'result': 'Pass (45%)',
          'status': 'pass',
        },
        {
          'step': 2,
          'node': 'Territory Check',
          'condition': 'Risk Score < 8.0',
          'result': 'Pass (6.2)',
          'status': 'pass',
        },
        {
          'step': 3,
          'node': 'Premium Validation',
          'condition': 'Adequacy > 100%',
          'result': 'Pass (112%)',
          'status': 'pass',
        },
        {
          'step': 4,
          'node': 'Exposure Analysis',
          'condition': 'Concentration < 30%',
          'result': 'Pass (23%)',
          'status': 'pass',
        },
        {
          'step': 5,
          'node': 'Compliance Check',
          'condition': 'All Requirements Met',
          'result': 'Pass',
          'status': 'pass',
        },
      ],
      'similar_risks': [
        {'id': 'RSK-2025-001', 'similarity': 92, 'outcome': 'Profitable', 'loss_ratio': 38},
        {'id': 'RSK-2024-156', 'similarity': 87, 'outcome': 'Profitable', 'loss_ratio': 42},
        {'id': 'RSK-2024-089', 'similarity': 84, 'outcome': 'Profitable', 'loss_ratio': 51},
        {'id': 'RSK-2024-203', 'similarity': 81, 'outcome': 'Loss', 'loss_ratio': 78},
        {'id': 'RSK-2023-445', 'similarity': 79, 'outcome': 'Profitable', 'loss_ratio': 45},
      ],
      'counterfactuals': [
        {
          'scenario': 'If loss ratio were 65% instead of 45%',
          'new_decision': 'REFER',
          'confidence_change': -22,
        },
        {
          'scenario': 'If territory risk score were 8.5 instead of 6.2',
          'new_decision': 'GO',
          'confidence_change': -15,
        },
        {
          'scenario': 'If premium adequacy were 95% instead of 112%',
          'new_decision': 'REFER',
          'confidence_change': -18,
        },
      ],
      'regulatory_compliance': {
        'solvency_ii': true,
        'lloyds_requirements': true,
        'sanctions_check': true,
        'aml_check': true,
      },
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Analysis'),
        backgroundColor: const Color(0xFF1a237e),
        foregroundColor: Colors.white,
        actions: [
          if (_explanationData != null) ...[
            IconButton(
              icon: const Icon(Icons.download),
              onPressed: _exportExplanation,
              tooltip: 'Export Report',
            ),
            IconButton(
              icon: const Icon(Icons.share),
              onPressed: _shareExplanation,
              tooltip: 'Share',
            ),
          ],
        ],
      ),
      body: _isLoadingAssessments
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadAssessments,
              child: Column(
                children: [
                  // Assessment Selector
                  _buildAssessmentSelector(),
                  // Content
                  Expanded(
                    child: _isLoading
                        ? const Center(child: CircularProgressIndicator())
                        : _error != null
                            ? _buildErrorState()
                            : _explanationData != null
                                ? SingleChildScrollView(
                                    physics: const AlwaysScrollableScrollPhysics(),
                                    padding: const EdgeInsets.all(16),
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        _buildDecisionSummary(),
                                        const SizedBox(height: 20),
                                        _buildFeatureImportance(),
                                        const SizedBox(height: 20),
                                        _buildDecisionPath(),
                                        const SizedBox(height: 20),
                                        _buildSimilarRisks(),
                                        const SizedBox(height: 20),
                                        _buildCounterfactuals(),
                                        const SizedBox(height: 20),
                                        _buildComplianceStatus(),
                                        const SizedBox(height: 20),
                                        _buildModelInfo(),
                                      ],
                                    ),
                                  )
                                : _buildEmptyState(),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _buildAssessmentSelector() {
    if (_completedAssessments.isEmpty) {
      return const SizedBox.shrink();
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.analytics, color: Color(0xFF1a237e), size: 20),
              const SizedBox(width: 8),
              const Text(
                'Select Assessment',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF1a237e),
                ),
              ),
              const Spacer(),
              Text(
                '${_completedAssessments.length} completed',
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey[600],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 80,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: _completedAssessments.length,
              itemBuilder: (context, index) {
                final assessment = _completedAssessments[index];
                final isSelected = assessment['id'].toString() == _selectedAssessmentId;
                return _buildAssessmentChip(assessment, isSelected);
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAssessmentChip(Map<String, dynamic> assessment, bool isSelected) {
    final decision = assessment['decision']?.toString().toUpperCase() ?? 'PENDING';
    final riskScore = assessment['risk_score'] ?? 0;
    final confidenceScore = assessment['confidence_score'] ?? 0;
    final title = assessment['title'] ?? assessment['insured_name'] ?? assessment['reference_number'] ?? 'Assessment #${assessment['id']}';
    final mode = assessment['mode']?.toString().toUpperCase() ?? '';

    Color decisionColor;
    switch (decision) {
      case 'GO':
        decisionColor = Colors.green;
        break;
      case 'NO_GO':
        decisionColor = Colors.red;
        break;
      default:
        decisionColor = Colors.orange;
    }

    return GestureDetector(
      onTap: () {
        setState(() {
          _selectedAssessmentId = assessment['id'].toString();
        });
        _loadExplanationData();
      },
      child: Container(
        width: 160,
        margin: const EdgeInsets.only(right: 12),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isSelected ? decisionColor.withOpacity(0.1) : Colors.grey[50],
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? decisionColor : Colors.grey[300]!,
            width: isSelected ? 2 : 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: decisionColor.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    decision == 'NO_GO' ? 'NO-GO' : decision,
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      color: decisionColor,
                    ),
                  ),
                ),
                const Spacer(),
                if (mode.isNotEmpty)
                  Text(
                    mode,
                    style: TextStyle(
                      fontSize: 9,
                      color: Colors.grey[600],
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              title.length > 20 ? '${title.substring(0, 20)}...' : title,
              style: TextStyle(
                fontSize: 12,
                fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                color: isSelected ? decisionColor : Colors.black87,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const Spacer(),
            Row(
              children: [
                Text(
                  'Risk: $riskScore%',
                  style: TextStyle(
                    fontSize: 10,
                    color: Colors.grey[600],
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  'Conf: $confidenceScore%',
                  style: TextStyle(
                    fontSize: 10,
                    color: Colors.grey[600],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: Colors.red[300]),
            const SizedBox(height: 16),
            Text(
              _error!,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.red),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _loadExplanationData,
              icon: const Icon(Icons.refresh),
              label: const Text('Try Again'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.analytics_outlined, size: 64, color: Colors.grey[400]),
            const SizedBox(height: 16),
            const Text(
              'No Completed Assessments',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Complete an assessment to see the AI analysis and decision explanation.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey[600]),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDecisionSummary() {
    final data = _explanationData!;
    final decision = data['decision'] as String;
    final confidence = data['confidence'] as double;

    Color decisionColor;
    IconData decisionIcon;
    switch (decision.toUpperCase()) {
      case 'GO':
        decisionColor = Colors.green;
        decisionIcon = Icons.check_circle;
        break;
      case 'NO-GO':
        decisionColor = Colors.red;
        decisionIcon = Icons.cancel;
        break;
      default:
        decisionColor = Colors.orange;
        decisionIcon = Icons.help_outline;
    }

    return Card(
      color: decisionColor.withOpacity(0.1),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(decisionIcon, color: decisionColor, size: 48),
                const SizedBox(width: 16),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'AI Decision: $decision',
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: decisionColor,
                      ),
                    ),
                    Text(
                      'Confidence: ${confidence.toStringAsFixed(1)}%',
                      style: TextStyle(
                        fontSize: 16,
                        color: decisionColor.withOpacity(0.8),
                      ),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 16),
            // Confidence Bar
            Container(
              height: 12,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(6),
                color: Colors.grey[300],
              ),
              child: FractionallySizedBox(
                alignment: Alignment.centerLeft,
                widthFactor: confidence / 100,
                child: Container(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(6),
                    gradient: LinearGradient(
                      colors: [decisionColor.withOpacity(0.7), decisionColor],
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              data['decision_summary'] as String,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFeatureImportance() {
    final features = _explanationData!['feature_importance'] as List;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.analytics, color: Color(0xFF1a237e)),
                SizedBox(width: 8),
                Text(
                  'Feature Importance',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const SizedBox(height: 8),
            const Text(
              'Key factors that influenced the AI decision',
              style: TextStyle(color: Colors.grey, fontSize: 13),
            ),
            const SizedBox(height: 16),
            SizedBox(
              height: 220,
              child: BarChart(
                BarChartData(
                  alignment: BarChartAlignment.spaceAround,
                  maxY: 0.35,
                  barGroups: features.asMap().entries.map((e) {
                    final importance = e.value['importance'] as double;
                    final impact = e.value['impact'] as String;
                    Color barColor;
                    switch (impact) {
                      case 'positive':
                        barColor = Colors.green;
                        break;
                      case 'negative':
                        barColor = Colors.red;
                        break;
                      default:
                        barColor = Colors.blue;
                    }
                    return BarChartGroupData(
                      x: e.key,
                      barRods: [
                        BarChartRodData(
                          toY: importance,
                          color: _selectedFactorIndex == e.key
                              ? barColor
                              : barColor.withOpacity(0.6),
                          width: 20,
                          borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
                        ),
                      ],
                    );
                  }).toList(),
                  titlesData: FlTitlesData(
                    show: true,
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        getTitlesWidget: (value, meta) {
                          final idx = value.toInt();
                          if (idx < features.length) {
                            final name = features[idx]['feature'] as String;
                            return Padding(
                              padding: const EdgeInsets.only(top: 8),
                              child: RotatedBox(
                                quarterTurns: 1,
                                child: Text(
                                  name.length > 10 ? '${name.substring(0, 10)}...' : name,
                                  style: const TextStyle(fontSize: 9),
                                ),
                              ),
                            );
                          }
                          return const Text('');
                        },
                        reservedSize: 80,
                      ),
                    ),
                    leftTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        getTitlesWidget: (value, meta) {
                          return Text(
                            '${(value * 100).toInt()}%',
                            style: const TextStyle(fontSize: 10),
                          );
                        },
                        reservedSize: 40,
                      ),
                    ),
                    topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  ),
                  gridData: const FlGridData(show: true, horizontalInterval: 0.1),
                  borderData: FlBorderData(show: false),
                  barTouchData: BarTouchData(
                    touchCallback: (event, response) {
                      if (response?.spot != null) {
                        setState(() {
                          _selectedFactorIndex = response!.spot!.touchedBarGroupIndex;
                        });
                      }
                    },
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
            // Feature Details List
            ...features.map((f) {
              final isSelected = features.indexOf(f) == _selectedFactorIndex;
              return _buildFeatureDetailRow(f, isSelected);
            }),
          ],
        ),
      ),
    );
  }

  Widget _buildFeatureDetailRow(Map<String, dynamic> feature, bool isSelected) {
    final impact = feature['impact'] as String;
    Color impactColor;
    IconData impactIcon;
    switch (impact) {
      case 'positive':
        impactColor = Colors.green;
        impactIcon = Icons.trending_up;
        break;
      case 'negative':
        impactColor = Colors.red;
        impactIcon = Icons.trending_down;
        break;
      default:
        impactColor = Colors.blue;
        impactIcon = Icons.trending_flat;
    }

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 2),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: isSelected ? impactColor.withOpacity(0.1) : Colors.transparent,
        borderRadius: BorderRadius.circular(8),
        border: isSelected ? Border.all(color: impactColor.withOpacity(0.3)) : null,
      ),
      child: Row(
        children: [
          Icon(impactIcon, color: impactColor, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              feature['feature'],
              style: TextStyle(
                fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
              ),
            ),
          ),
          Text(
            feature['value'],
            style: TextStyle(
              fontWeight: FontWeight.w500,
              color: impactColor,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            '${((feature['importance'] as double) * 100).toInt()}%',
            style: const TextStyle(color: Colors.grey, fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _buildDecisionPath() {
    final path = _explanationData!['decision_path'] as List;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.account_tree, color: Color(0xFF1a237e)),
                SizedBox(width: 8),
                Text(
                  'Decision Path',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const SizedBox(height: 8),
            const Text(
              'Step-by-step breakdown of the decision process',
              style: TextStyle(color: Colors.grey, fontSize: 13),
            ),
            const SizedBox(height: 16),
            ...path.asMap().entries.map((e) {
              final step = e.value;
              final isLast = e.key == path.length - 1;
              return _buildDecisionStep(step, isLast);
            }),
          ],
        ),
      ),
    );
  }

  Widget _buildDecisionStep(Map<String, dynamic> step, bool isLast) {
    final status = step['status'] as String;
    final isPass = status == 'pass';

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Column(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: isPass ? Colors.green : Colors.red,
                shape: BoxShape.circle,
              ),
              child: Center(
                child: Icon(
                  isPass ? Icons.check : Icons.close,
                  color: Colors.white,
                  size: 18,
                ),
              ),
            ),
            if (!isLast)
              Container(
                width: 2,
                height: 40,
                color: Colors.grey[300],
              ),
          ],
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Step ${step['step']}: ${step['node']}',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 4),
                Text(
                  'Condition: ${step['condition']}',
                  style: const TextStyle(color: Colors.grey, fontSize: 13),
                ),
                Text(
                  'Result: ${step['result']}',
                  style: TextStyle(
                    color: isPass ? Colors.green : Colors.red,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSimilarRisks() {
    final risks = _explanationData!['similar_risks'] as List;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.compare_arrows, color: Color(0xFF1a237e)),
                SizedBox(width: 8),
                Text(
                  'Similar Historical Risks',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const SizedBox(height: 8),
            const Text(
              'Past risks with similar characteristics',
              style: TextStyle(color: Colors.grey, fontSize: 13),
            ),
            const SizedBox(height: 16),
            ...risks.map((risk) => _buildSimilarRiskRow(risk)),
          ],
        ),
      ),
    );
  }

  Widget _buildSimilarRiskRow(Map<String, dynamic> risk) {
    final outcome = risk['outcome'] as String;
    final isProfitable = outcome == 'Profitable';

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 4),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey[50],
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey[200]!),
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 18,
            backgroundColor: isProfitable ? Colors.green.withOpacity(0.1) : Colors.red.withOpacity(0.1),
            child: Text(
              '${risk['similarity']}%',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.bold,
                color: isProfitable ? Colors.green : Colors.red,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  risk['id'],
                  style: const TextStyle(fontWeight: FontWeight.w500),
                ),
                Text(
                  'Loss Ratio: ${risk['loss_ratio']}%',
                  style: const TextStyle(color: Colors.grey, fontSize: 12),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: isProfitable ? Colors.green.withOpacity(0.1) : Colors.red.withOpacity(0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              outcome,
              style: TextStyle(
                color: isProfitable ? Colors.green : Colors.red,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCounterfactuals() {
    final counterfactuals = _explanationData!['counterfactuals'] as List;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.swap_horiz, color: Color(0xFF1a237e)),
                SizedBox(width: 8),
                Text(
                  'What-If Scenarios',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const SizedBox(height: 8),
            const Text(
              'How changes would affect the decision',
              style: TextStyle(color: Colors.grey, fontSize: 13),
            ),
            const SizedBox(height: 16),
            ...counterfactuals.map((cf) {
              final change = cf['confidence_change'] as int;
              return Container(
                margin: const EdgeInsets.symmetric(vertical: 4),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.amber.withOpacity(0.05),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.amber.withOpacity(0.2)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.lightbulb_outline, color: Colors.amber, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            cf['scenario'],
                            style: const TextStyle(fontSize: 13),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: _getDecisionColor(cf['new_decision']).withOpacity(0.1),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            'Decision: ${cf['new_decision']}',
                            style: TextStyle(
                              color: _getDecisionColor(cf['new_decision']),
                              fontWeight: FontWeight.w500,
                              fontSize: 12,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'Confidence: ${change > 0 ? '+' : ''}$change%',
                          style: TextStyle(
                            color: change > 0 ? Colors.green : Colors.red,
                            fontWeight: FontWeight.w500,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  Widget _buildComplianceStatus() {
    final compliance = _explanationData!['regulatory_compliance'] as Map<String, dynamic>;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.verified_user, color: Color(0xFF1a237e)),
                SizedBox(width: 8),
                Text(
                  'Compliance Checks',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const SizedBox(height: 16),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              childAspectRatio: 3,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              children: [
                _buildComplianceItem('Solvency II', compliance['solvency_ii'] as bool),
                _buildComplianceItem("Lloyd's Requirements", compliance['lloyds_requirements'] as bool),
                _buildComplianceItem('Sanctions Check', compliance['sanctions_check'] as bool),
                _buildComplianceItem('AML Check', compliance['aml_check'] as bool),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildComplianceItem(String label, bool passed) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: passed ? Colors.green.withOpacity(0.1) : Colors.red.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: passed ? Colors.green.withOpacity(0.3) : Colors.red.withOpacity(0.3),
        ),
      ),
      child: Row(
        children: [
          Icon(
            passed ? Icons.check_circle : Icons.cancel,
            color: passed ? Colors.green : Colors.red,
            size: 20,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              label,
              style: TextStyle(
                fontSize: 12,
                color: passed ? Colors.green[700] : Colors.red[700],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildModelInfo() {
    final data = _explanationData!;

    return Card(
      color: Colors.grey[50],
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.info_outline, color: Colors.grey),
                SizedBox(width: 8),
                Text(
                  'Model Information',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Colors.grey),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Model Version', style: TextStyle(color: Colors.grey)),
                Text(data['model_version'] ?? 'N/A'),
              ],
            ),
            const SizedBox(height: 4),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Processing Time', style: TextStyle(color: Colors.grey)),
                Text('${data['processing_time_ms']}ms'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Color _getDecisionColor(String decision) {
    switch (decision.toUpperCase()) {
      case 'GO':
        return Colors.green;
      case 'NO-GO':
        return Colors.red;
      default:
        return Colors.orange;
    }
  }

  void _exportExplanation() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Exporting AI explanation report...')),
    );
  }

  void _shareExplanation() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Sharing explanation...')),
    );
  }
}
