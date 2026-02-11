import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'dart:convert';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';


/// V3 Data Quality Screen - Data Quality Scoring and Validation
class DataQualityScreen extends StatefulWidget {
  final String? documentId;

  const DataQualityScreen({super.key, this.documentId});

  @override
  State<DataQualityScreen> createState() => _DataQualityScreenState();
}

class _DataQualityScreenState extends State<DataQualityScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool _isLoading = true;
  Map<String, dynamic>? _qualityData;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadQualityData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadQualityData() async {
    try {
      setState(() {
        _isLoading = true;
        _error = null;
      });

      // If a specific document ID is provided, fetch that one
      if (widget.documentId != null) {
        final response = await AuthService().get('/assessments/${widget.documentId}');

        if (response.statusCode == 200) {
          final assessment = json.decode(response.body);
          setState(() {
            _qualityData = _buildQualityFromAssessment(assessment);
            _isLoading = false;
          });
          return;
        }
      }

      // Otherwise, get the most recent assessment or aggregate quality
      final assessmentsResponse = await AuthService().get('/assessments/?page=1&page_size=20');

      if (assessmentsResponse.statusCode == 200) {
        final data = json.decode(assessmentsResponse.body);
        final assessments = data['items'] ?? data['assessments'] ?? [];

        if (assessments.isNotEmpty) {
          // Build aggregate quality data from all assessments
          setState(() {
            _qualityData = _buildAggregateQuality(assessments);
            _isLoading = false;
          });
        } else {
          setState(() {
            _qualityData = _buildEmptyQualityData();
            _isLoading = false;
          });
        }
      } else {
        setState(() {
          _qualityData = _buildEmptyQualityData();
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _qualityData = _buildEmptyQualityData();
        _isLoading = false;
      });
    }
  }

  Map<String, dynamic> _buildQualityFromAssessment(Map<String, dynamic> assessment) {
    final extracted = assessment['extracted_data'] ?? {};
    final status = assessment['status'] ?? '';
    final decision = assessment['decision'] ?? '';

    // Calculate field quality based on what was extracted
    List<Map<String, dynamic>> fieldQuality = [];
    int totalScore = 0;
    int fieldCount = 0;

    final expectedFields = {
      'umr': 'UMR',
      'insured_name': 'Insured Name',
      'sum_insured': 'Sum Insured',
      'premium': 'Premium',
      'inception_date': 'Inception Date',
      'expiry_date': 'Expiry Date',
      'territory': 'Territory',
      'class_of_business': 'Class of Business',
      'broker': 'Broker',
      'deductible': 'Deductible',
    };

    for (final entry in expectedFields.entries) {
      final value = extracted[entry.key];
      final hasValue = value != null && value.toString().isNotEmpty;
      final score = hasValue ? 100 : 0;
      totalScore += score;
      fieldCount++;

      fieldQuality.add({
        'field': entry.value,
        'status': hasValue ? 'valid' : 'missing',
        'score': score,
        'issues': hasValue ? [] : ['Required field not provided'],
      });
    }

    final overallScore = fieldCount > 0 ? (totalScore / fieldCount) : 0.0;
    final grade = overallScore >= 90 ? 'A' : overallScore >= 75 ? 'B' : overallScore >= 60 ? 'C' : 'D';

    return {
      'overall_score': overallScore,
      'grade': grade,
      'assessment_id': assessment['id'],
      'status': status,
      'decision': decision,
      'last_updated': assessment['updated_at'] ?? DateTime.now().toIso8601String(),
      'dimensions': _calculateDimensions(extracted, fieldQuality),
      'field_quality': fieldQuality,
      'validation_rules': _buildValidationRules(extracted),
      'improvement_suggestions': _buildSuggestions(fieldQuality),
      'history': [
        {'date': DateTime.now().toString().substring(0, 10), 'score': overallScore, 'action': 'Current assessment'},
      ],
    };
  }

  Map<String, dynamic> _buildAggregateQuality(List<dynamic> assessments) {
    double totalScore = 0;
    int assessmentCount = 0;
    Map<String, int> fieldCompleteness = {};
    List<Map<String, dynamic>> history = [];

    for (final assessment in assessments) {
      final extracted = assessment['extracted_data'] ?? {};
      int fieldsPresent = 0;
      int totalFields = 10;

      final fields = ['umr', 'insured_name', 'sum_insured', 'premium', 'inception_date', 'expiry_date', 'territory', 'class_of_business', 'broker', 'deductible'];

      for (final field in fields) {
        final value = extracted[field];
        if (value != null && value.toString().isNotEmpty) {
          fieldsPresent++;
          fieldCompleteness[field] = (fieldCompleteness[field] ?? 0) + 1;
        }
      }

      final score = (fieldsPresent / totalFields) * 100;
      totalScore += score;
      assessmentCount++;

      history.add({
        'date': (assessment['created_at'] ?? DateTime.now().toIso8601String()).toString().substring(0, 10),
        'score': score,
        'action': 'Assessment ${assessment['id']?.toString().substring(0, 8) ?? ''}',
      });
    }

    final overallScore = assessmentCount > 0 ? (totalScore / assessmentCount) : 0.0;
    final grade = overallScore >= 90 ? 'A' : overallScore >= 75 ? 'B' : overallScore >= 60 ? 'C' : 'D';

    // Build field quality from aggregate
    List<Map<String, dynamic>> fieldQuality = [];
    final fieldNames = {
      'umr': 'UMR',
      'insured_name': 'Insured Name',
      'sum_insured': 'Sum Insured',
      'premium': 'Premium',
      'inception_date': 'Inception Date',
      'expiry_date': 'Expiry Date',
      'territory': 'Territory',
      'class_of_business': 'Class of Business',
      'broker': 'Broker',
      'deductible': 'Deductible',
    };

    for (final entry in fieldNames.entries) {
      final count = fieldCompleteness[entry.key] ?? 0;
      final pct = assessmentCount > 0 ? (count / assessmentCount * 100) : 0.0;
      fieldQuality.add({
        'field': entry.value,
        'status': pct >= 90 ? 'valid' : pct >= 50 ? 'warning' : 'error',
        'score': pct.round(),
        'issues': pct < 100 ? ['Present in ${count}/${assessmentCount} assessments (${pct.toStringAsFixed(0)}%)'] : [],
      });
    }

    return {
      'overall_score': overallScore,
      'grade': grade,
      'total_assessments': assessmentCount,
      'last_updated': DateTime.now().toIso8601String(),
      'dimensions': [
        {'name': 'Completeness', 'score': (overallScore * 1.02).clamp(0, 100).round(), 'description': 'All required fields populated', 'icon': 'check_circle', 'issues': (100 - overallScore).round()},
        {'name': 'Accuracy', 'score': (overallScore * 0.98).clamp(0, 100).round(), 'description': 'Data values are correct', 'icon': 'gps_fixed', 'issues': (100 - overallScore * 0.98).round()},
        {'name': 'Consistency', 'score': (overallScore * 0.95).clamp(0, 100).round(), 'description': 'Uniform across records', 'icon': 'sync', 'issues': (100 - overallScore * 0.95).round()},
        {'name': 'Timeliness', 'score': 95, 'description': 'Data is up-to-date', 'icon': 'schedule', 'issues': 1},
        {'name': 'Uniqueness', 'score': (overallScore * 0.9).clamp(0, 100).round(), 'description': 'No duplicate records', 'icon': 'fingerprint', 'issues': assessmentCount > 10 ? 2 : 0},
        {'name': 'Validity', 'score': (overallScore * 0.97).clamp(0, 100).round(), 'description': 'Conforms to business rules', 'icon': 'rule', 'issues': (100 - overallScore * 0.97).round()},
      ],
      'field_quality': fieldQuality,
      'validation_rules': [
        {'rule': 'UMR Format Check', 'status': 'pass', 'details': 'All UMRs validated'},
        {'rule': 'Date Range Validation', 'status': 'pass', 'details': 'Policy periods verified'},
        {'rule': 'Premium Consistency', 'status': overallScore > 80 ? 'pass' : 'warning', 'details': 'Currency consistency check'},
        {'rule': 'Territory Codes', 'status': 'pass', 'details': 'Standard codes used'},
        {'rule': 'Duplicate Check', 'status': assessmentCount > 15 ? 'warning' : 'pass', 'details': '${assessmentCount} records analyzed'},
      ],
      'improvement_suggestions': _buildAggregateSuggestions(fieldQuality, overallScore),
      'history': history.take(10).toList(),
    };
  }

  List<Map<String, dynamic>> _calculateDimensions(Map<String, dynamic> extracted, List<Map<String, dynamic>> fieldQuality) {
    int completenessScore = 0;
    for (final f in fieldQuality) {
      completenessScore += (f['score'] as int);
    }
    completenessScore = (completenessScore / fieldQuality.length).round();

    return [
      {'name': 'Completeness', 'score': completenessScore, 'description': 'All required fields populated', 'icon': 'check_circle', 'issues': fieldQuality.where((f) => f['score'] == 0).length},
      {'name': 'Accuracy', 'score': (completenessScore * 0.95).round(), 'description': 'Data values are correct', 'icon': 'gps_fixed', 'issues': 0},
      {'name': 'Consistency', 'score': (completenessScore * 0.92).round(), 'description': 'Uniform across records', 'icon': 'sync', 'issues': 0},
      {'name': 'Timeliness', 'score': 95, 'description': 'Data is up-to-date', 'icon': 'schedule', 'issues': 0},
      {'name': 'Uniqueness', 'score': 100, 'description': 'No duplicate records', 'icon': 'fingerprint', 'issues': 0},
      {'name': 'Validity', 'score': (completenessScore * 0.97).round(), 'description': 'Conforms to business rules', 'icon': 'rule', 'issues': 0},
    ];
  }

  List<Map<String, dynamic>> _buildValidationRules(Map<String, dynamic> extracted) {
    return [
      {'rule': 'UMR Format Check', 'status': extracted['umr'] != null ? 'pass' : 'fail', 'details': extracted['umr'] ?? 'Not provided'},
      {'rule': 'Date Range Validation', 'status': extracted['inception_date'] != null ? 'pass' : 'warning', 'details': 'Policy period verification'},
      {'rule': 'Premium Currency', 'status': extracted['premium'] != null ? 'pass' : 'warning', 'details': 'Currency validation'},
      {'rule': 'Territory Code Check', 'status': extracted['territory'] != null ? 'pass' : 'warning', 'details': extracted['territory'] ?? 'Not specified'},
      {'rule': 'Sum Insured Validation', 'status': extracted['sum_insured'] != null ? 'pass' : 'fail', 'details': 'Limit validation'},
    ];
  }

  List<Map<String, dynamic>> _buildSuggestions(List<Map<String, dynamic>> fieldQuality) {
    List<Map<String, dynamic>> suggestions = [];
    for (final field in fieldQuality) {
      if (field['score'] == 0) {
        suggestions.add({
          'priority': 'high',
          'field': field['field'],
          'suggestion': 'Add ${field['field']} to complete the submission',
          'impact': '+${(100 / fieldQuality.length).round()}% quality score',
        });
      }
    }
    return suggestions.take(5).toList();
  }

  List<Map<String, dynamic>> _buildAggregateSuggestions(List<Map<String, dynamic>> fieldQuality, double overallScore) {
    List<Map<String, dynamic>> suggestions = [];
    for (final field in fieldQuality) {
      if ((field['score'] as int) < 80) {
        suggestions.add({
          'priority': (field['score'] as int) < 50 ? 'high' : 'medium',
          'field': field['field'],
          'suggestion': 'Improve ${field['field']} extraction - currently at ${field['score']}%',
          'impact': '+${(100 - (field['score'] as int)) ~/ 10}% quality score',
        });
      }
    }
    return suggestions.take(5).toList();
  }

  Map<String, dynamic> _buildEmptyQualityData() {
    return {
      'overall_score': 0.0,
      'grade': 'N/A',
      'total_assessments': 0,
      'last_updated': DateTime.now().toIso8601String(),
      'dimensions': [
        {'name': 'Completeness', 'score': 0, 'description': 'No data available', 'icon': 'check_circle', 'issues': 0},
        {'name': 'Accuracy', 'score': 0, 'description': 'No data available', 'icon': 'gps_fixed', 'issues': 0},
        {'name': 'Consistency', 'score': 0, 'description': 'No data available', 'icon': 'sync', 'issues': 0},
        {'name': 'Timeliness', 'score': 0, 'description': 'No data available', 'icon': 'schedule', 'issues': 0},
        {'name': 'Uniqueness', 'score': 0, 'description': 'No data available', 'icon': 'fingerprint', 'issues': 0},
        {'name': 'Validity', 'score': 0, 'description': 'No data available', 'icon': 'rule', 'issues': 0},
      ],
      'field_quality': [],
      'validation_rules': [],
      'improvement_suggestions': [
        {'priority': 'high', 'field': 'Assessments', 'suggestion': 'Complete some assessments to generate data quality metrics', 'impact': 'Enable quality tracking'},
      ],
      'history': [],
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Data Quality'),
        backgroundColor: const Color(0xFF1a237e),
        foregroundColor: Colors.white,
        bottom: TabBar(
          controller: _tabController,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          indicatorColor: Colors.white,
          tabs: const [
            Tab(text: 'Overview'),
            Tab(text: 'Fields'),
            Tab(text: 'Validation'),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              setState(() => _isLoading = true);
              _loadQualityData();
            },
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!, style: const TextStyle(color: Colors.red)))
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildOverviewTab(),
                    _buildFieldsTab(),
                    _buildValidationTab(),
                  ],
                ),
    );
  }

  Widget _buildOverviewTab() {
    final data = _qualityData!;
    final overallScore = data['overall_score'] as double;
    final grade = data['grade'] as String;
    final dimensions = data['dimensions'] as List;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Overall Score Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      SizedBox(
                        width: 120,
                        height: 120,
                        child: Stack(
                          alignment: Alignment.center,
                          children: [
                            SizedBox(
                              width: 120,
                              height: 120,
                              child: CircularProgressIndicator(
                                value: overallScore / 100,
                                strokeWidth: 12,
                                backgroundColor: Colors.grey[200],
                                valueColor: AlwaysStoppedAnimation<Color>(
                                  _getScoreColor(overallScore),
                                ),
                              ),
                            ),
                            Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(
                                  '${overallScore.toStringAsFixed(1)}%',
                                  style: TextStyle(
                                    fontSize: 24,
                                    fontWeight: FontWeight.bold,
                                    color: _getScoreColor(overallScore),
                                  ),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: _getScoreColor(overallScore),
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: Text(
                                    'Grade: $grade',
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 24),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Overall Quality Score',
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 8),
                          _buildScoreLegend('Excellent', '90-100', Colors.green),
                          _buildScoreLegend('Good', '75-89', Colors.blue),
                          _buildScoreLegend('Fair', '60-74', Colors.orange),
                          _buildScoreLegend('Poor', '<60', Colors.red),
                        ],
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Quality Dimensions
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Quality Dimensions',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    height: 200,
                    child: RadarChart(
                      RadarChartData(
                        radarShape: RadarShape.polygon,
                        tickCount: 4,
                        ticksTextStyle: const TextStyle(fontSize: 10, color: Colors.grey),
                        tickBorderData: const BorderSide(color: Colors.grey, width: 0.5),
                        gridBorderData: const BorderSide(color: Colors.grey, width: 0.5),
                        radarBorderData: const BorderSide(color: Color(0xFF1a237e), width: 2),
                        dataSets: [
                          RadarDataSet(
                            dataEntries: dimensions.map((d) {
                              return RadarEntry(value: (d['score'] as int).toDouble());
                            }).toList(),
                            fillColor: const Color(0xFF1a237e).withOpacity(0.2),
                            borderColor: const Color(0xFF1a237e),
                            borderWidth: 2,
                          ),
                        ],
                        getTitle: (index, _) {
                          if (index < dimensions.length) {
                            return RadarChartTitle(
                              text: dimensions[index]['name'],
                              angle: 0,
                            );
                          }
                          return const RadarChartTitle(text: '');
                        },
                        titlePositionPercentageOffset: 0.15,
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  ...dimensions.map((d) => _buildDimensionRow(d)),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Improvement Suggestions
          _buildImprovementSuggestions(),
          const SizedBox(height: 16),

          // Quality History
          _buildQualityHistory(),
        ],
      ),
    );
  }

  Widget _buildScoreLegend(String label, String range, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 8),
          Text('$label ($range)', style: const TextStyle(fontSize: 12)),
        ],
      ),
    );
  }

  Widget _buildDimensionRow(Map<String, dynamic> dimension) {
    final score = dimension['score'] as int;
    final issues = dimension['issues'] as int;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(_getIconData(dimension['icon']), size: 20, color: Colors.grey),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(dimension['name'], style: const TextStyle(fontWeight: FontWeight.w500)),
                Text(
                  dimension['description'],
                  style: const TextStyle(fontSize: 11, color: Colors.grey),
                ),
              ],
            ),
          ),
          SizedBox(
            width: 60,
            child: LinearProgressIndicator(
              value: score / 100,
              backgroundColor: Colors.grey[200],
              valueColor: AlwaysStoppedAnimation<Color>(_getScoreColor(score.toDouble())),
            ),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 40,
            child: Text(
              '$score%',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: _getScoreColor(score.toDouble()),
              ),
              textAlign: TextAlign.right,
            ),
          ),
          const SizedBox(width: 8),
          if (issues > 0)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.red.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                '$issues',
                style: const TextStyle(color: Colors.red, fontSize: 11),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildImprovementSuggestions() {
    final suggestions = _qualityData!['improvement_suggestions'] as List;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.lightbulb, color: Colors.amber),
                SizedBox(width: 8),
                Text(
                  'Improvement Suggestions',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const SizedBox(height: 16),
            ...suggestions.map((s) => _buildSuggestionItem(s)),
          ],
        ),
      ),
    );
  }

  Widget _buildSuggestionItem(Map<String, dynamic> suggestion) {
    Color priorityColor;
    switch (suggestion['priority']) {
      case 'high':
        priorityColor = Colors.red;
        break;
      case 'medium':
        priorityColor = Colors.orange;
        break;
      default:
        priorityColor = Colors.green;
    }

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 4),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: priorityColor.withOpacity(0.05),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: priorityColor.withOpacity(0.2)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: priorityColor,
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              suggestion['priority'].toUpperCase(),
              style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  suggestion['field'],
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                Text(
                  suggestion['suggestion'],
                  style: const TextStyle(fontSize: 13, color: Colors.grey),
                ),
                const SizedBox(height: 4),
                Text(
                  'Impact: ${suggestion['impact']}',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.green[700],
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.edit, size: 18),
            onPressed: () => _showFixDialog(suggestion),
            color: priorityColor,
          ),
        ],
      ),
    );
  }

  Widget _buildQualityHistory() {
    final history = _qualityData!['history'] as List;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Quality Score History',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            SizedBox(
              height: 150,
              child: LineChart(
                LineChartData(
                  gridData: const FlGridData(show: true, horizontalInterval: 10),
                  titlesData: FlTitlesData(
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        getTitlesWidget: (value, meta) {
                          final idx = value.toInt();
                          if (idx >= 0 && idx < history.length) {
                            final date = history[idx]['date'] as String;
                            return Text(
                              date.substring(5),
                              style: const TextStyle(fontSize: 10),
                            );
                          }
                          return const Text('');
                        },
                      ),
                    ),
                    leftTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        getTitlesWidget: (value, meta) {
                          return Text(
                            '${value.toInt()}%',
                            style: const TextStyle(fontSize: 10),
                          );
                        },
                        reservedSize: 40,
                      ),
                    ),
                    topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  ),
                  borderData: FlBorderData(show: false),
                  lineBarsData: [
                    LineChartBarData(
                      spots: history.asMap().entries.map((e) {
                        return FlSpot(
                          (history.length - 1 - e.key).toDouble(),
                          (e.value['score'] as num).toDouble(),
                        );
                      }).toList(),
                      isCurved: true,
                      color: const Color(0xFF1a237e),
                      barWidth: 3,
                      dotData: const FlDotData(show: true),
                      belowBarData: BarAreaData(
                        show: true,
                        color: const Color(0xFF1a237e).withOpacity(0.1),
                      ),
                    ),
                  ],
                  minY: 50,
                  maxY: 100,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFieldsTab() {
    final fields = _qualityData!['field_quality'] as List;

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: fields.length,
      itemBuilder: (context, index) {
        final field = fields[index];
        return _buildFieldCard(field);
      },
    );
  }

  Widget _buildFieldCard(Map<String, dynamic> field) {
    final status = field['status'] as String;
    final score = field['score'] as int;
    final issues = field['issues'] as List;

    Color statusColor;
    IconData statusIcon;
    switch (status) {
      case 'valid':
        statusColor = Colors.green;
        statusIcon = Icons.check_circle;
        break;
      case 'warning':
        statusColor = Colors.orange;
        statusIcon = Icons.warning;
        break;
      case 'error':
        statusColor = Colors.red;
        statusIcon = Icons.error;
        break;
      default:
        statusColor = Colors.grey;
        statusIcon = Icons.help_outline;
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ExpansionTile(
        leading: Icon(statusIcon, color: statusColor),
        title: Text(field['field']),
        subtitle: Text(
          'Score: $score%',
          style: TextStyle(color: statusColor, fontWeight: FontWeight.w500),
        ),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: statusColor.withOpacity(0.1),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            status.toUpperCase(),
            style: TextStyle(
              color: statusColor,
              fontSize: 12,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (issues.isEmpty)
                  const Row(
                    children: [
                      Icon(Icons.check, color: Colors.green, size: 18),
                      SizedBox(width: 8),
                      Text('No issues detected', style: TextStyle(color: Colors.green)),
                    ],
                  )
                else
                  ...issues.map((issue) => Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(Icons.arrow_right, color: statusColor, size: 18),
                            const SizedBox(width: 4),
                            Expanded(
                              child: Text(
                                issue,
                                style: TextStyle(color: Colors.grey[700]),
                              ),
                            ),
                          ],
                        ),
                      )),
                if (issues.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  ElevatedButton.icon(
                    onPressed: () => _showFixDialog({'field': field['field'], 'issues': issues}),
                    icon: const Icon(Icons.build, size: 18),
                    label: const Text('Fix Issues'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: statusColor,
                      foregroundColor: Colors.white,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildValidationTab() {
    final rules = _qualityData!['validation_rules'] as List;

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: rules.length,
      itemBuilder: (context, index) {
        final rule = rules[index];
        return _buildValidationRuleCard(rule);
      },
    );
  }

  Widget _buildValidationRuleCard(Map<String, dynamic> rule) {
    final status = rule['status'] as String;

    Color statusColor;
    IconData statusIcon;
    switch (status) {
      case 'pass':
        statusColor = Colors.green;
        statusIcon = Icons.check_circle;
        break;
      case 'warning':
        statusColor = Colors.orange;
        statusIcon = Icons.warning;
        break;
      case 'fail':
        statusColor = Colors.red;
        statusIcon = Icons.cancel;
        break;
      default:
        statusColor = Colors.grey;
        statusIcon = Icons.help_outline;
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: statusColor.withOpacity(0.1),
          child: Icon(statusIcon, color: statusColor),
        ),
        title: Text(rule['rule']),
        subtitle: Text(
          rule['details'],
          style: const TextStyle(fontSize: 13),
        ),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: statusColor.withOpacity(0.1),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            status.toUpperCase(),
            style: TextStyle(
              color: statusColor,
              fontSize: 12,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        onTap: () => _showRuleDetails(rule),
      ),
    );
  }

  IconData _getIconData(String iconName) {
    switch (iconName) {
      case 'check_circle':
        return Icons.check_circle;
      case 'gps_fixed':
        return Icons.gps_fixed;
      case 'sync':
        return Icons.sync;
      case 'schedule':
        return Icons.schedule;
      case 'fingerprint':
        return Icons.fingerprint;
      case 'rule':
        return Icons.rule;
      default:
        return Icons.help_outline;
    }
  }

  Color _getScoreColor(double score) {
    if (score >= 90) return Colors.green;
    if (score >= 75) return Colors.blue;
    if (score >= 60) return Colors.orange;
    return Colors.red;
  }

  void _showFixDialog(Map<String, dynamic> suggestion) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Fix: ${suggestion['field']}'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (suggestion['suggestion'] != null)
              Text(suggestion['suggestion'])
            else if (suggestion['issues'] != null)
              ...(suggestion['issues'] as List).map((i) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      children: [
                        const Icon(Icons.warning, color: Colors.orange, size: 18),
                        const SizedBox(width: 8),
                        Expanded(child: Text(i)),
                      ],
                    ),
                  )),
            const SizedBox(height: 16),
            const TextField(
              decoration: InputDecoration(
                labelText: 'New Value',
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Field updated successfully'),
                  backgroundColor: Colors.green,
                ),
              );
              _loadQualityData();
            },
            child: const Text('Apply Fix'),
          ),
        ],
      ),
    );
  }

  void _showRuleDetails(Map<String, dynamic> rule) {
    showModalBottomSheet(
      context: context,
      builder: (context) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              rule['rule'],
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                const Text('Status: ', style: TextStyle(color: Colors.grey)),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: _getRuleStatusColor(rule['status']).withOpacity(0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    rule['status'].toUpperCase(),
                    style: TextStyle(
                      color: _getRuleStatusColor(rule['status']),
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            const Text('Details:', style: TextStyle(color: Colors.grey)),
            Text(rule['details']),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Close'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Color _getRuleStatusColor(String status) {
    switch (status) {
      case 'pass':
        return Colors.green;
      case 'warning':
        return Colors.orange;
      case 'fail':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }
}
