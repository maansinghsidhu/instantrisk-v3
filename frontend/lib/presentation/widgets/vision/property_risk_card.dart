import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/vision_service.dart';

/// PropertyRiskCard - Shows computer vision analysis results for a property assessment.
/// Displays detected risk features (roof condition, flood zone, construction type, etc.)
/// and OCR confidence score for processed documents.
class PropertyRiskCard extends StatefulWidget {
  final String assessmentId;

  const PropertyRiskCard({
    super.key,
    required this.assessmentId,
  });

  @override
  State<PropertyRiskCard> createState() => _PropertyRiskCardState();
}

class _PropertyRiskCardState extends State<PropertyRiskCard> {
  Map<String, dynamic>? _visionData;
  List<Map<String, dynamic>> _propertyRisks = [];
  List<Map<String, dynamic>> _ocrResults = [];
  bool _isLoading = true;
  bool _isExpanded = true;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final visionFuture = visionService.getVisionAnalysis(widget.assessmentId);
    final risksFuture = visionService.getPropertyRisks(widget.assessmentId);
    final ocrFuture = visionService.getOcrResults(widget.assessmentId);

    final results = await Future.wait([visionFuture, risksFuture, ocrFuture]);

    if (mounted) {
      setState(() {
        _visionData = results[0] as Map<String, dynamic>?;
        _propertyRisks = results[1] as List<Map<String, dynamic>>;
        _ocrResults = results[2] as List<Map<String, dynamic>>;
        _isLoading = false;
      });
    }
  }

  double get _avgOcrConfidence {
    if (_ocrResults.isEmpty) return 0;
    final total = _ocrResults.fold<double>(
      0,
      (sum, r) => sum + ((r['confidence'] as num?)?.toDouble() ?? 0),
    );
    return total / _ocrResults.length;
  }

  Color _confidenceColor(double confidence) {
    if (confidence >= 0.9) return AppTheme.success;
    if (confidence >= 0.7) return AppTheme.warning;
    return AppTheme.danger;
  }

  Color _riskLevelColor(String level) {
    switch (level.toLowerCase()) {
      case 'high':
        return AppTheme.danger;
      case 'medium':
        return AppTheme.warning;
      case 'low':
        return AppTheme.success;
      default:
        return AppTheme.info;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          InkWell(
            onTap: () => setState(() => _isExpanded = !_isExpanded),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: AppTheme.analysisCyan.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.remove_red_eye_outlined,
                      size: 18,
                      color: AppTheme.analysisCyan,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Computer Vision Analysis',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.text1(context),
                          ),
                        ),
                        if (!_isLoading && _ocrResults.isNotEmpty)
                          Text(
                            'OCR Confidence: ${(_avgOcrConfidence * 100).toStringAsFixed(0)}%',
                            style: TextStyle(
                              fontSize: 11,
                              color: _confidenceColor(_avgOcrConfidence),
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                      ],
                    ),
                  ),
                  Icon(
                    _isExpanded ? Icons.expand_less : Icons.expand_more,
                    size: 20,
                    color: AppTheme.text2(context),
                  ),
                ],
              ),
            ),
          ),

          if (_isExpanded) ...[
            Divider(height: 1, color: AppTheme.borderOf(context)),

            if (_isLoading)
              const Padding(
                padding: EdgeInsets.all(24),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_visionData == null && _propertyRisks.isEmpty && _ocrResults.isEmpty)
              Padding(
                padding: const EdgeInsets.all(24),
                child: Center(
                  child: Column(
                    children: [
                      Icon(
                        Icons.image_search_outlined,
                        size: 36,
                        color: AppTheme.textH(context),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'No vision data available',
                        style: TextStyle(
                          fontSize: 13,
                          color: AppTheme.text2(context),
                        ),
                      ),
                      const SizedBox(height: 8),
                      OutlinedButton.icon(
                        onPressed: () async {
                          await visionService.triggerAnalysis(widget.assessmentId);
                          _loadData();
                        },
                        icon: const Icon(Icons.play_arrow, size: 16),
                        label: const Text('Run Vision Analysis'),
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 8),
                        ),
                      ),
                    ],
                  ),
                ),
              )
            else
              Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // OCR Confidence section
                    if (_ocrResults.isNotEmpty) ...[
                      _SectionTitle(title: 'Document OCR Quality', context: context),
                      const SizedBox(height: 8),
                      ...(_ocrResults.map((ocr) => _OcrResultRow(
                            ocr: ocr,
                            confidenceColor: _confidenceColor(
                              (ocr['confidence'] as num?)?.toDouble() ?? 0,
                            ),
                          ))),
                      const SizedBox(height: 16),
                    ],

                    // Property risks section
                    if (_propertyRisks.isNotEmpty) ...[
                      _SectionTitle(
                          title: 'Detected Property Features', context: context),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: _propertyRisks.map((risk) {
                          final label = risk['feature']?.toString() ??
                              risk['name']?.toString() ??
                              'Feature';
                          final level = risk['risk_level']?.toString() ??
                              risk['level']?.toString() ??
                              'low';
                          final confidence = ((risk['confidence'] as num?)
                                      ?.toDouble() ??
                                  0.8) *
                              100;
                          return _FeatureChip(
                            label: label,
                            level: level,
                            confidence: confidence,
                            color: _riskLevelColor(level),
                          );
                        }).toList(),
                      ),
                    ],

                    // Summary from vision data
                    if (_visionData != null) ...[
                      if (_propertyRisks.isNotEmpty || _ocrResults.isNotEmpty)
                        const SizedBox(height: 16),
                      if (_visionData!['summary'] != null) ...[
                        _SectionTitle(title: 'Vision Summary', context: context),
                        const SizedBox(height: 8),
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: AppTheme.analysisCyan.withOpacity(0.05),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: AppTheme.analysisCyan.withOpacity(0.15),
                            ),
                          ),
                          child: Text(
                            _visionData!['summary'].toString(),
                            style: TextStyle(
                              fontSize: 13,
                              color: AppTheme.text1(context),
                              height: 1.4,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ],
                ),
              ),
          ],
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  final BuildContext context;

  const _SectionTitle({required this.title, required this.context});

  @override
  Widget build(BuildContext ctx) {
    return Text(
      title,
      style: TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w700,
        color: AppTheme.text2(context),
        letterSpacing: 0.8,
      ),
    );
  }
}

class _OcrResultRow extends StatelessWidget {
  final Map<String, dynamic> ocr;
  final Color confidenceColor;

  const _OcrResultRow({required this.ocr, required this.confidenceColor});

  @override
  Widget build(BuildContext context) {
    final filename = ocr['filename']?.toString() ?? ocr['document']?.toString() ?? 'Document';
    final confidence = ((ocr['confidence'] as num?)?.toDouble() ?? 0) * 100;

    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          const Icon(Icons.description_outlined, size: 14, color: Colors.grey),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              filename,
              style: TextStyle(
                fontSize: 12,
                color: AppTheme.text1(context),
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 8),
          // Confidence bar
          SizedBox(
            width: 60,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: LinearProgressIndicator(
                value: confidence / 100,
                backgroundColor: AppTheme.borderOf(context),
                color: confidenceColor,
                minHeight: 6,
              ),
            ),
          ),
          const SizedBox(width: 6),
          Text(
            '${confidence.toStringAsFixed(0)}%',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: confidenceColor,
            ),
          ),
        ],
      ),
    );
  }
}

class _FeatureChip extends StatelessWidget {
  final String label;
  final String level;
  final double confidence;
  final Color color;

  const _FeatureChip({
    required this.label,
    required this.level,
    required this.confidence,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
          Text(
            '${confidence.toStringAsFixed(0)}% conf.',
            style: TextStyle(
              fontSize: 9,
              color: color.withOpacity(0.7),
            ),
          ),
        ],
      ),
    );
  }
}
