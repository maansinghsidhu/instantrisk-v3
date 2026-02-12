import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'dart:convert';
import 'dart:async';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/subscription_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Results Screen - Displays GO/NO-GO decision with real AI analysis
/// Also handles live processing progress when navigated from upload
class ResultsScreen extends StatefulWidget {
  final String assessmentId;
  final Map<String, dynamic>? analysisData;
  // Processing mode - when true, shows live progress
  final bool isProcessing;
  final String? sessionId;
  final String? sessionToken;
  final int documentCount;

  const ResultsScreen({
    super.key,
    required this.assessmentId,
    this.analysisData,
    this.isProcessing = false,
    this.sessionId,
    this.sessionToken,
    this.documentCount = 1,
  });

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen>
    with SingleTickerProviderStateMixin {
  Map<String, dynamic>? _analysis;
  Map<String, dynamic>? _assessment;
  bool _isLoading = true;
  String? _error;

  // Pricing data
  Map<String, dynamic>? _pricingResult;
  bool _isCalculatingPricing = false;
  String? _pricingError;

  // AI Analysis state
  bool _isRunningAnalysis = false;
  bool _showDetails = false;

  // Upgrade analysis state
  bool _isUpgrading = false;

  // Subscription service for tier-based UI
  final SubscriptionService _subscriptionService = SubscriptionService();

  // Processing progress state (for live progress view)
  late AnimationController _pulseController;
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  bool _isProcessing = false;
  String _currentAgent = '';
  String _currentDescription = 'Initializing...';
  int _agentIndex = 0;
  int _totalAgents = 5;
  double _progressPercent = 0;
  int _elapsedSeconds = 0;
  int _estimatedRemaining = 0;
  bool _processingComplete = false;
  bool _hasProcessingError = false;
  String? _processingErrorMessage;
  Timer? _elapsedTimer;
  DateTime? _startTime;
  List<Map<String, dynamic>> _liveFindings = [];
  int _currentDocument = 0;
  int _totalDocuments = 0;
  String _documentName = '';
  Timer? _pollTimer;
  String? get _sessionToken => widget.sessionToken ?? (widget.sessionId != null ? widget.sessionId!.substring(0, widget.sessionId!.lastIndexOf("-")) : null);
  String? _actualAssessmentId;

  // Tier helpers
  bool get _isPremium => _subscriptionService.isPremium;
  bool get _isBasicOrHigher => _subscriptionService.isBasic || _subscriptionService.isPremium;
  bool get _isTrial => _subscriptionService.isTrial;
  bool get _canSeeDecision => _subscriptionService.hasFeature('go_no_go_decision');

  // Dynamic label for casualty vs property
  String get limitLabel {
    final category = _assessment?['risk_category']?.toString().toLowerCase() ?? '';
    final isCasualty = category == 'casualty' ||
                       category == 'financial_lines' ||
                       category == 'cyber';
    return isCasualty ? 'Limit' : 'Sum Insured';
  }

  // Underwriting percentage from AI analysis
  String get underwritingPercent {
    final recommended = _analysis?['agent_results']?['underwriter']?['recommended_share'];
    if (recommended != null) return '${recommended}%';
    final confPercent = confidencePercent;
    if (confPercent > 0) return '${(confPercent * 0.3).toInt()}%'; // Fallback estimate
    return 'Insufficient Data';
  }

  bool get hasUnderwritingData => underwritingPercent != 'Insufficient Data';

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);

    if (widget.isProcessing && widget.sessionId != null) {
      // Processing mode - show live progress
      _isProcessing = true;
      _isLoading = false;
      _startTime = DateTime.now();
      _totalDocuments = widget.documentCount;
      _currentDocument = 1;
      _startElapsedTimer();
      _connectWebSocket(widget.sessionId!);
    } else if (widget.analysisData != null) {
      _analysis = widget.analysisData;
      _isLoading = false;
    } else {
      _checkAuthAndFetch();
    }
  }

  void _startElapsedTimer() {
    _elapsedTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (_startTime != null && !_processingComplete && !_hasProcessingError) {
        setState(() {
          _elapsedSeconds = DateTime.now().difference(_startTime!).inSeconds;
        });
      }
    });
  }

  int _wsRetryCount = 0;
  static const int _maxWsRetries = 3;

  void _connectWebSocket(String sessionId, {int retryCount = 0}) {
    _wsRetryCount = retryCount;

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
            // Reset retry count on successful message
            _wsRetryCount = 0;
          } catch (e) {
            // Ignore parse errors
            debugPrint('WebSocket parse error: $e');
          }
        },
        onError: (error) {
          debugPrint('WebSocket error: $error');
          // Try reconnecting with exponential backoff
          if (_wsRetryCount < _maxWsRetries && !_processingComplete && !_hasProcessingError) {
            final delay = Duration(seconds: (1 << _wsRetryCount)); // 1, 2, 4 seconds
            debugPrint('Reconnecting WebSocket in ${delay.inSeconds}s (attempt ${_wsRetryCount + 1}/$_maxWsRetries)');
            Future.delayed(delay, () {
              if (mounted && !_processingComplete && !_hasProcessingError) {
                _connectWebSocket(sessionId, retryCount: _wsRetryCount + 1);
              }
            });
          } else {
            // Fallback to polling after max retries
            _startPolling();
          }
        },
        onDone: () {
          // WebSocket closed
          if (!_processingComplete && !_hasProcessingError) {
            // Try reconnecting once, then fall back to polling
            if (_wsRetryCount < _maxWsRetries) {
              Future.delayed(const Duration(seconds: 2), () {
                if (mounted && !_processingComplete && !_hasProcessingError) {
                  _connectWebSocket(sessionId, retryCount: _wsRetryCount + 1);
                }
              });
            } else {
              _startPolling();
            }
          }
        },
      );
    } catch (e) {
      debugPrint('WebSocket connection error: $e');
      // Fall back to polling if WebSocket fails
      _startPolling();
    }
  }

  void _handleWebSocketMessage(Map<String, dynamic> message) {
    final type = message['type'] as String?;

    switch (type) {
      case 'progress':
        setState(() {
          _currentAgent = message['current_agent'] ?? '';
          _agentIndex = message['agent_index'] ?? 0;
          _totalAgents = message['total_agents'] ?? _totalAgents;
          _currentDescription = message['description'] ?? 'Processing...';
          final progressVal = message['progress_percent'];
          _progressPercent = (progressVal is num) ? progressVal.toDouble() : 0.0;
          _estimatedRemaining = message['estimated_remaining'] ?? 0;
          _currentDocument = message['current_document'] ?? 0;
          _totalDocuments = message['total_documents'] ?? widget.documentCount;
          _documentName = message['document_name'] ?? '';

          // Handle live findings from backend
          if (message['live_findings'] != null) {
            _liveFindings = List<Map<String, dynamic>>.from(message['live_findings']);
          }
        });
        break;

      case 'complete':
        // Update assessment ID from message
        if (message['assessment_id'] != null) {
          _actualAssessmentId = message['assessment_id'].toString();
        }
        setState(() {
          _processingComplete = true;
          _progressPercent = 100;
          _isProcessing = false;
        });
        _elapsedTimer?.cancel();
        _pollTimer?.cancel();
        // Fetch the actual results
        _fetchData();
        break;

      case 'error':
        _handleProcessingError(message['message'] ?? 'Unknown error');
        break;
    }
  }

  void _startPolling() {
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      await _pollProgress();
    });
  }

  /// Poll assessment endpoint for status updates (used when navigating from history)
  void _startPollingAssessment() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) async {
      await _pollAssessmentStatus();
    });
  }

  /// Check assessment status and fetch full data when complete
  Future<void> _pollAssessmentStatus() async {
    try {
      final assessmentId = _effectiveAssessmentId;
      final response = await authService.get('/assessments/$assessmentId');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final status = data['status']?.toString().toLowerCase() ?? '';

        if (status == 'completed' || status == 'complete') {
          // Analysis complete - show results
          _pollTimer?.cancel();
          _elapsedTimer?.cancel();
          setState(() {
            _processingComplete = true;
            _progressPercent = 100;
            _isProcessing = false;
            _assessment = data;
            _analysis = data['ai_analysis'] ?? {};
          });
        } else if (status == 'failed' || status == 'error') {
          _pollTimer?.cancel();
          _handleProcessingError(data['error'] ?? 'Analysis failed');
        } else {
          // Still processing - update progress
          setState(() {
            _progressPercent = (_progressPercent + 5).clamp(0, 90);
            _currentDescription = 'Analysis in progress...';
          });
        }
      }
    } catch (e) {
      // Ignore polling errors
    }
  }

  Future<void> _pollProgress() async {
    try {
      final response = await authService.get(
        '/upload-sessions/${_sessionToken ?? widget.assessmentId}/status',
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        if (data['status'] == 'completed') {
          _pollTimer?.cancel();
          if (data['assessment_id'] != null) {
            _actualAssessmentId = data['assessment_id'].toString();
          }
          setState(() {
            _processingComplete = true;
            _progressPercent = 100;
            _isProcessing = false;
          });
          _elapsedTimer?.cancel();
          _fetchData();
        } else if (data['status'] == 'failed') {
          _pollTimer?.cancel();
          _handleProcessingError(data['error'] ?? 'Analysis failed');
        } else {
          // Update progress based on status
          setState(() {
            _currentAgent = data['current_agent'] ?? _currentAgent;
            _currentDescription = data['description'] ?? _currentDescription;
            if (data['progress'] != null && data['progress'] is num) {
              _progressPercent = (data['progress'] as num).toDouble();
            }
          });
        }
      }
    } catch (e) {
      // Ignore polling errors
    }
  }

  void _handleProcessingError(String message) {
    setState(() {
      _hasProcessingError = true;
      _processingErrorMessage = message;
      _isProcessing = false;
    });
    _elapsedTimer?.cancel();
    _pollTimer?.cancel();
  }

  String _formatTime(int seconds) {
    final minutes = seconds ~/ 60;
    final secs = seconds % 60;
    return '${minutes.toString().padLeft(2, '0')}:${secs.toString().padLeft(2, '0')}';
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

  Future<void> _checkAuthAndFetch() async {
    if (!authService.isLoggedIn) {
      if (mounted) {
        context.go('/login');
      }
      return;
    }
    _fetchData();
  }

  // Get the effective assessment ID (may be updated by WebSocket)
  String get _effectiveAssessmentId => _actualAssessmentId ?? widget.assessmentId;

  Future<void> _fetchData() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      // Use effective ID (may be updated by WebSocket during processing)
      final assessmentId = _effectiveAssessmentId;

      // First, try to load from local cache for instant display
      await _loadFromCache(assessmentId);

      // Try fetching from assessments API first (by ID)
      final assessmentResponse = await authService.get('/assessments/$assessmentId');

      if (assessmentResponse.statusCode == 200) {
        final data = jsonDecode(assessmentResponse.body);

        // Check if assessment is still processing
        // Backend uses: draft, pending_review, in_progress, completed, cancelled, failed
        final status = data['status']?.toString().toLowerCase() ?? '';
        final isStillProcessing = status == 'draft' ||
                                   status == 'pending_review' ||
                                   status == 'in_progress' ||
                                   status == 'processing' ||
                                   status == 'pending' ||
                                   status == 'uploading';
        if (isStillProcessing) {
          // Show processing state and start polling
          setState(() {
            _isProcessing = true;
            _isLoading = false;
            _currentDescription = 'Analysis in progress...';
            _progressPercent = 50; // Show partial progress
          });
          _startTime ??= DateTime.now();
          _startElapsedTimer();
          _startPollingAssessment();
          return;
        }

        setState(() {
          _assessment = data;
          _analysis = data['ai_analysis'] ?? {};
          _isLoading = false;
        });

        // Cache the data locally for offline/instant access
        await _saveToCache(assessmentId, data);
        return;
      }

      if (assessmentResponse.statusCode == 401) {
        if (mounted) {
          context.go('/login');
        }
        return;
      }

      // Fallback: try upload session analysis
      final sessionResponse = await authService.get('/upload-sessions/${_sessionToken ?? assessmentId}/analysis');

      if (sessionResponse.statusCode == 200) {
        final data = jsonDecode(sessionResponse.body);
        setState(() {
          _analysis = data['analysis'];
          _isLoading = false;
        });
        // Cache this too
        await _saveToCache(assessmentId, {'ai_analysis': data['analysis']});
      } else if (sessionResponse.statusCode == 401) {
        if (mounted) {
          context.go('/login');
        }
      } else {
        // If API failed but we have cached data, use it
        if (_assessment != null || _analysis != null) {
          setState(() => _isLoading = false);
        } else {
          setState(() {
            _error = 'Assessment not found';
            _isLoading = false;
          });
        }
      }
    } catch (e) {
      // If network failed but we have cached data, use it
      if (_assessment != null || _analysis != null) {
        setState(() => _isLoading = false);
      } else {
        setState(() {
          _error = 'Failed to load: $e';
          _isLoading = false;
        });
      }
    }
  }

  /// Load assessment data from local cache
  Future<void> _loadFromCache(String assessmentId) async {
    try {
      final box = await Hive.openBox('assessment_cache');
      final cachedData = box.get('assessment_$assessmentId');
      if (cachedData != null) {
        final data = Map<String, dynamic>.from(cachedData);
        setState(() {
          _assessment = data;
          _analysis = data['ai_analysis'] ?? _analysis ?? {};
        });
      }
    } catch (e) {
      debugPrint('Cache load error: $e');
    }
  }

  /// Save assessment data to local cache
  Future<void> _saveToCache(String assessmentId, Map<String, dynamic> data) async {
    try {
      final box = await Hive.openBox('assessment_cache');
      await box.put('assessment_$assessmentId', data);
    } catch (e) {
      debugPrint('Cache save error: $e');
    }
  }

  // Get data from assessment or analysis
  String get decision {
    // First try assessment decision from database
    final assessmentDecision = _assessment?['decision']?.toString().toUpperCase();
    if (assessmentDecision != null && assessmentDecision.isNotEmpty) {
      return assessmentDecision;
    }
    // Then try decision from AI analysis (underwriter agent)
    final analysisDecision = _analysis?['decision']?.toString().toUpperCase();
    if (analysisDecision != null && analysisDecision.isNotEmpty) {
      return analysisDecision;
    }
    // Fallback based on confidence
    return confidence > 0.5 ? 'GO' : 'NO_GO';
  }
  bool get isApproved => decision == 'GO';
  bool get isReferred => false;
  // Confidence from underwriter agent or assessment confidence_score
  double get confidence {
    // Helper to safely convert to double
    double? toSafeDouble(dynamic value) {
      if (value == null) return null;
      if (value is num) return value.toDouble();
      if (value is String) return double.tryParse(value);
      return null;
    }
    // First try underwriter agent confidence (0-1 scale)
    final underwriterConf = toSafeDouble(_analysis?['agent_results']?['underwriter']?['confidence']);
    if (underwriterConf != null) {
      return underwriterConf > 1 ? underwriterConf / 100 : underwriterConf;  // Normalize to 0-1
    }
    // Then try assessment confidence_score
    final assessmentConf = toSafeDouble(_assessment?['confidence_score']);
    if (assessmentConf != null) {
      return assessmentConf > 1 ? assessmentConf / 100 : assessmentConf;  // Normalize to 0-1
    }
    return 0.5;  // Default
  }
  int get confidencePercent => (confidence * 100).toInt();
  int get riskScore => _assessment?['risk_score'] ?? 50;
  double get premiumEstimate {
    final value = _assessment?['premium'] ?? _analysis?['premium'];
    if (value == null) return 0.0;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value) ?? 0.0;
    return 0.0;
  }
  String get companyName => _assessment?['insured_name'] ?? _analysis?['company_name'] ?? 'Document Analysis';
  String get riskType => _assessment?['risk_category'] ?? _analysis?['risk_type'] ?? _analysis?['document_type'] ?? 'Pending Review';
  String get coverageDetails => _assessment?['description'] ?? _analysis?['coverage_details'] ?? '';
  String get territory => _assessment?['territory'] ?? _analysis?['territory'] ?? '';
  String get referenceNumber => _assessment?['reference_number'] ?? '';
  // riskFactors - check multiple sources with comprehensive fallbacks
  List<dynamic> get riskFactors {
    // First: directly from assessment ai_recommendations (backend stores here)
    final assessmentRecs = _assessment?['ai_recommendations'];
    if (assessmentRecs != null && assessmentRecs is List && assessmentRecs.isNotEmpty) {
      return assessmentRecs;
    }

    // Second: try ai_analysis object for risk_factors
    final aiAnalysis = _assessment?['ai_analysis'];
    if (aiAnalysis != null && aiAnalysis is Map) {
      // Try risk_factors directly
      final riskFactorsFromAnalysis = aiAnalysis['risk_factors'];
      if (riskFactorsFromAnalysis != null && riskFactorsFromAnalysis is List && riskFactorsFromAnalysis.isNotEmpty) {
        return riskFactorsFromAnalysis;
      }

      // Try agent_results -> risk_analyst -> risk_factors
      final agentResults = aiAnalysis['agent_results'];
      if (agentResults != null && agentResults is Map) {
        final riskAnalyst = agentResults['risk_analyst'];
        if (riskAnalyst != null && riskAnalyst is Map) {
          final factors = riskAnalyst['risk_factors'];
          if (factors != null && factors is List && factors.isNotEmpty) {
            return factors;
          }
        }
      }

      // Try recommendations from ai_analysis
      final recommendations = aiAnalysis['recommendations'];
      if (recommendations != null && recommendations is List && recommendations.isNotEmpty) {
        return recommendations;
      }
    }

    // Third: try _analysis (from direct API response or route params)
    final analysisRiskFactors = _analysis?['risk_factors'];
    if (analysisRiskFactors != null && analysisRiskFactors is List && analysisRiskFactors.isNotEmpty) {
      return analysisRiskFactors;
    }

    // Default empty
    return [];
  }
  double get deductible {
    final value = _assessment?['deductible'] ?? _analysis?['deductible'];
    if (value == null) return 0.0;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value) ?? 0.0;
    return 0.0;
  }
  double get sumInsured {
    final value = _assessment?['sum_insured'] ?? _analysis?['sum_insured'];
    if (value == null) return 0.0;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value) ?? 0.0;
    return 0.0;
  }

  // Useful metrics for document analysis
  int get documentsAnalyzed {
    final docs = _assessment?['documents_count'] ?? _analysis?['documents_count'];
    if (docs != null) return docs as int;
    // Count document markers in OCR text
    final ocr = ocrExtractedText;
    if (ocr.isEmpty) return 0;
    return RegExp(r'--- Document \d+:').allMatches(ocr).length;
  }

  int get keyFindingsCount => riskFactors.length;

  String get decisionRationale => _assessment?['decision_rationale'] ??
      _analysis?['decision_rationale'] ??
      _analysis?['agent_results']?['underwriter']?['decision_rationale'] ?? '';

  // OCR Extracted Text
  String get ocrExtractedText => _assessment?['ocr_extracted_text'] ??
      _analysis?['ocr_extracted_text'] ??
      _analysis?['ocr_text_preview'] ?? '';

  // Analysis mode (quick/go_no_go/deep)
  String get analysisMode => _assessment?['analysis_mode'] ??
      _analysis?['analysis_mode'] ?? 'quick';

  // Agent Results - the detailed analysis from each AI agent
  Map<String, dynamic> get agentResults {
    final aiAnalysis = _assessment?['ai_analysis'] ?? _analysis;
    if (aiAnalysis == null) return {};
    return Map<String, dynamic>.from(aiAnalysis['agent_results'] ?? {});
  }

  // Number of agents used
  int get agentsUsed {
    final aiAnalysis = _assessment?['ai_analysis'] ?? _analysis;
    return aiAnalysis?['agents_used'] ?? agentResults.length;
  }

  bool get canUpgradeAnalysis => analysisMode != 'deep';

  String get nextMode {
    if (analysisMode == 'quick') return 'go_no_go';
    if (analysisMode == 'go_no_go') return 'deep';
    return '';
  }

  String get nextModeLabel {
    if (analysisMode == 'quick') return 'Standard Analysis';
    if (analysisMode == 'go_no_go') return 'Deep Analysis';
    return '';
  }

  // Pricing Factors - extracted data for underwriting
  Map<String, dynamic> get pricingFactors {
    final factors = <String, dynamic>{};
    final extractor = agentResults['extractor'] ?? {};

    // Insured Profile
    final insuredProfile = <String, dynamic>{};
    final insuredName = extractor['insured']?['name'] ?? extractor['company_name'] ?? companyName;
    if (insuredName.isNotEmpty && insuredName != 'Document Analysis') insuredProfile['name'] = insuredName;
    final industry = extractor['insured']?['industry'] ?? extractor['industry'] ?? _assessment?['industry'];
    if (industry != null && industry.toString().isNotEmpty) insuredProfile['industry'] = industry;
    final established = extractor['insured']?['established'] ?? extractor['established_date'];
    if (established != null) insuredProfile['established'] = established;
    final address = extractor['insured']?['address'] ?? extractor['address'];
    if (address != null && address.toString().isNotEmpty) insuredProfile['address'] = address;
    if (insuredProfile.isNotEmpty) factors['insured_profile'] = insuredProfile;

    // Financial Metrics
    final financialMetrics = <String, dynamic>{};
    final revenue = extractor['financial']?['revenue'] ?? extractor['revenue'] ?? _assessment?['revenue'];
    if (revenue != null) financialMetrics['revenue'] = revenue;
    final tiv = sumInsured > 0 ? sumInsured : (extractor['total_insured_value'] ?? extractor['tiv']);
    if (tiv != null && tiv > 0) financialMetrics['total_insured_value'] = tiv;
    final assets = extractor['financial']?['total_assets'] ?? extractor['assets'];
    if (assets != null) financialMetrics['total_assets'] = assets;
    final employees = extractor['employees'] ?? extractor['employee_count'];
    if (employees != null) financialMetrics['employees'] = employees;
    if (financialMetrics.isNotEmpty) factors['financial_metrics'] = financialMetrics;

    // Coverage Details
    final coverageDetails = <String, dynamic>{};
    final policyType = extractor['policy']?['type'] ?? extractor['policy_type'] ?? riskType;
    if (policyType.isNotEmpty && policyType != 'Pending Review') coverageDetails['policy_type'] = policyType;
    final limit = extractor['policy']?['limit'] ?? extractor['limit_of_liability'] ?? sumInsured;
    if (limit != null && limit > 0) coverageDetails['limit'] = limit;
    final ded = extractor['policy']?['deductible'] ?? deductible;
    if (ded > 0) coverageDetails['deductible'] = ded;
    final policyPeriod = extractor['policy']?['period'] ?? extractor['policy_period'];
    if (policyPeriod != null) coverageDetails['policy_period'] = policyPeriod;
    final territoryVal = extractor['policy']?['territory'] ?? territory;
    if (territoryVal.isNotEmpty) coverageDetails['territory'] = territoryVal;
    if (coverageDetails.isNotEmpty) factors['coverage_details'] = coverageDetails;

    // Claims History
    final claimsHistory = <String, dynamic>{};
    final claims = extractor['claims'] ?? extractor['claims_history'];
    if (claims != null && claims is List && claims.isNotEmpty) {
      claimsHistory['claims'] = claims;
    } else if (claims != null && claims is Map) {
      claimsHistory.addAll(Map<String, dynamic>.from(claims));
    }
    final lossRatio = extractor['loss_ratio'];
    if (lossRatio != null) claimsHistory['loss_ratio'] = lossRatio;
    if (claimsHistory.isNotEmpty) factors['claims_history'] = claimsHistory;

    // Geographic Exposure
    final geoExposure = <String, dynamic>{};
    final locations = extractor['locations'] ?? extractor['operating_locations'];
    if (locations != null && locations is List && locations.isNotEmpty) geoExposure['locations'] = locations;
    final territories = extractor['territories'] ?? extractor['operating_territories'];
    if (territories != null && territories is List && territories.isNotEmpty) geoExposure['territories'] = territories;
    final catExposure = extractor['catastrophe_exposure'] ?? extractor['nat_cat_exposure'];
    if (catExposure != null) geoExposure['catastrophe_exposure'] = catExposure;
    if (geoExposure.isNotEmpty) factors['geographic_exposure'] = geoExposure;

    // Risk Indicators (from risk analyst)
    final riskAnalyst = agentResults['risk_analyst'] ?? {};
    final riskIndicators = <String, dynamic>{};
    final riskLevel = riskAnalyst['overall_risk_level'] ?? riskAnalyst['risk_level'];
    if (riskLevel != null) riskIndicators['risk_level'] = riskLevel;
    final riskFactorsList = riskAnalyst['risk_factors'] ?? riskFactors;
    if (riskFactorsList.isNotEmpty) riskIndicators['key_risks'] = riskFactorsList.take(5).toList();
    final hazards = riskAnalyst['hazards'] ?? extractor['hazards'];
    if (hazards != null && hazards is List && hazards.isNotEmpty) riskIndicators['hazards'] = hazards;
    if (riskIndicators.isNotEmpty) factors['risk_indicators'] = riskIndicators;

    // Key Personnel (for sanctions/compliance context)
    final keyPersonnel = extractor['key_personnel'];
    if (keyPersonnel != null && keyPersonnel is Map) {
      final personnel = <String, dynamic>{};
      if (keyPersonnel['directors'] is List && (keyPersonnel['directors'] as List).isNotEmpty) {
        personnel['directors'] = keyPersonnel['directors'];
      }
      if (keyPersonnel['officers'] is List && (keyPersonnel['officers'] as List).isNotEmpty) {
        personnel['officers'] = keyPersonnel['officers'];
      }
      if (keyPersonnel['shareholders'] is List && (keyPersonnel['shareholders'] as List).isNotEmpty) {
        personnel['shareholders'] = keyPersonnel['shareholders'];
      }
      if (keyPersonnel['ultimate_beneficial_owners'] is List && (keyPersonnel['ultimate_beneficial_owners'] as List).isNotEmpty) {
        personnel['ubos'] = keyPersonnel['ultimate_beneficial_owners'];
      }
      if (personnel.isNotEmpty) factors['key_personnel'] = personnel;
    }

    return factors;
  }

  Future<void> _calculatePricing() async {
    setState(() {
      _isCalculatingPricing = true;
      _pricingError = null;
    });

    try {
      // Determine class of business and other parameters from assessment
      final classOfBusiness = _assessment?['risk_category'] ??
                               _analysis?['class_of_business'] ??
                               'property';
      final limitOfLiability = sumInsured > 0 ? sumInsured : 1000000;
      final territoryValue = territory.isNotEmpty ? territory : 'EU';

      final response = await authService.post('/pricing/technical', body: {
        'assessment_id': int.parse(widget.assessmentId),
        'class_of_business': classOfBusiness,
        'limit_of_liability': limitOfLiability,
        'currency': 'GBP',
        'deductible': deductible,
        'territory': territoryValue,
      });

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = jsonDecode(response.body);
        if (data['technical_premium'] != null) {
          setState(() {
            _pricingResult = data;
            _isCalculatingPricing = false;
          });
        } else {
          setState(() {
            _pricingError = 'Failed to calculate pricing';
            _isCalculatingPricing = false;
          });
        }
      } else {
        setState(() {
          _pricingError = 'Failed to calculate pricing: ${response.statusCode}';
          _isCalculatingPricing = false;
        });
      }
    } catch (e) {
      setState(() {
        _pricingError = 'Pricing calculation error: $e';
        _isCalculatingPricing = false;
      });
    }
  }

  Future<void> _triggerAIAnalysis() async {
    setState(() {
      _isRunningAnalysis = true;
    });

    try {
      final response = await authService.post('/assessments/${widget.assessmentId}/analyze');

      if (response.statusCode == 200 || response.statusCode == 202) {
        // Wait a bit for analysis to complete, then refresh
        await Future.delayed(const Duration(seconds: 3));
        await _fetchData();
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Analysis failed: ${response.statusCode}'),
              backgroundColor: AppTheme.danger,
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: $e'),
            backgroundColor: AppTheme.danger,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isRunningAnalysis = false;
        });
      }
    }
  }

  Future<void> _upgradeAnalysis() async {
    if (!canUpgradeAnalysis) return;

    setState(() {
      _isUpgrading = true;
    });

    try {
      final response = await authService.post(
        '/assessments/${widget.assessmentId}/upgrade-analysis?target_mode=$nextMode',
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true && data['session_id'] != null) {
          // Navigate to progress screen
          if (mounted) {
            context.go('/analysis/${data['assessment_id']}?session_id=${data['session_id']}&mode=$nextMode');
          }
        } else {
          throw Exception(data['detail'] ?? 'Upgrade failed');
        }
      } else if (response.statusCode == 401) {
        if (mounted) context.go('/login');
      } else {
        final error = jsonDecode(response.body);
        throw Exception(error['detail'] ?? 'Failed to upgrade analysis');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Upgrade failed: $e'),
            backgroundColor: AppTheme.danger,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isUpgrading = false;
        });
      }
    }
  }

  Widget _buildUpgradeCard() {
    if (!canUpgradeAnalysis) return const SizedBox.shrink();

    final modeColor = nextMode == 'go_no_go'
        ? const Color(0xFF2563EB)
        : const Color(0xFF7C3AED);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20.0),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: modeColor.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: modeColor.withValues(alpha: 0.3)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.upgrade_outlined, color: modeColor),
                const SizedBox(width: 8),
                Text(
                  'Want more detailed analysis?',
                  style: TextStyle(fontWeight: FontWeight.bold, color: modeColor),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              analysisMode == 'quick'
                  ? 'Upgrade to see extracted data, risk factors, and better confidence scoring.'
                  : 'Upgrade to Deep Analysis for comprehensive risk assessment and QA validation.',
              style: TextStyle(fontSize: 13, color: Colors.grey[700]),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _isUpgrading ? null : _upgradeAnalysis,
                icon: _isUpgrading
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.auto_awesome),
                label: Text(_isUpgrading ? 'Upgrading...' : 'Upgrade to $nextModeLabel'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: modeColor,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _shareResults() async {
    try {
      final response = await authService.post(
        '/share/assessments/${widget.assessmentId}',
        body: {'hours_valid': 24},
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final shareUrl = 'https://d2f065h47nuk0c.cloudfront.net/#/share/${data['token']}';
        if (mounted) {
          showDialog(
            context: context,
            builder: (ctx) => AlertDialog(
              title: const Text('Share Assessment'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Anyone with this link can view the results:',
                    style: TextStyle(fontSize: 14, color: AppTheme.textSecondary)),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.background,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: SelectableText(shareUrl,
                      style: const TextStyle(fontSize: 13)),
                  ),
                  const SizedBox(height: 8),
                  Text('Expires in 24 hours',
                    style: TextStyle(fontSize: 12, color: Colors.grey[500])),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('Close'),
                ),
                ElevatedButton.icon(
                  onPressed: () {
                    Share.share(shareUrl);
                    Navigator.pop(ctx);
                  },
                  icon: const Icon(Icons.share, size: 18),
                  label: const Text('Share'),
                ),
              ],
            ),
          );
        }
      } else {
        throw Exception('Failed to create share link');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not create share link: $e'),
            backgroundColor: AppTheme.danger),
        );
      }
    }
  }

  // Rename dialog (Premium only)
  Future<void> _showRenameDialog() async {
    final controller = TextEditingController(text: companyName);

    final result = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Rename Analysis'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(
            labelText: 'Account Name',
            hintText: 'Enter account or company name',
          ),
          autofocus: true,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, controller.text),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryDark,
              foregroundColor: Colors.white,
            ),
            child: const Text('Save'),
          ),
        ],
      ),
    );

    if (result != null && result.isNotEmpty && result != companyName) {
      await _updateAssessmentTitle(result);
    }
  }

  Future<void> _updateAssessmentTitle(String newTitle) async {
    try {
      final response = await authService.put(
        '/assessments/${widget.assessmentId}',
        body: {'title': newTitle},
      );
      if (response.statusCode == 200) {
        await _fetchData();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Analysis renamed successfully'),
              backgroundColor: AppTheme.success,
            ),
          );
        }
      } else {
        throw Exception('Failed to rename');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to rename: $e'),
            backgroundColor: AppTheme.danger,
          ),
        );
      }
    }
  }

  // Build underwriting summary card for Basic+ users
  Widget _buildUnderwritingSummary() {
    final suggestedPremium = premiumEstimate;
    final suggestedLimit = sumInsured;
    final hasPremiumData = suggestedPremium > 0;
    final hasLimitData = suggestedLimit > 0;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20.0),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: _buildSummaryCard(
                  title: 'Underwriting %',
                  value: underwritingPercent,
                  icon: Icons.pie_chart_outline,
                  color: AppTheme.primaryDark,
                  hasData: hasUnderwritingData,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildSummaryCard(
                  title: 'Suggested Premium',
                  value: hasPremiumData ? 'GBP ${_formatCurrency(suggestedPremium)}' : 'Insufficient Data',
                  icon: Icons.attach_money_outlined,
                  color: AppTheme.success,
                  hasData: hasPremiumData,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildSummaryCard(
            title: limitLabel,
            value: hasLimitData ? 'GBP ${_formatCurrency(suggestedLimit)}' : 'Insufficient Data',
            icon: Icons.shield_outlined,
            color: const Color(0xFF7C3AED),
            hasData: hasLimitData,
            fullWidth: true,
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryCard({
    required String title,
    required String value,
    required IconData icon,
    required Color color,
    required bool hasData,
    bool fullWidth = false,
  }) {
    return Container(
      width: fullWidth ? double.infinity : null,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: hasData ? color.withValues(alpha: 0.1) : AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: hasData ? color.withValues(alpha: 0.3) : AppTheme.border,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: hasData ? color : AppTheme.textHint, size: 18),
              const SizedBox(width: 8),
              Text(
                title,
                style: TextStyle(
                  fontSize: 12,
                  color: hasData ? color : AppTheme.textSecondary,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(
              fontSize: hasData ? 20 : 14,
              fontWeight: hasData ? FontWeight.w700 : FontWeight.w500,
              color: hasData ? color : AppTheme.textHint,
              fontStyle: hasData ? FontStyle.normal : FontStyle.italic,
              fontFamily: 'Inter',
            ),
          ),
        ],
      ),
    );
  }

  // Build upgrade prompt for lower tiers
  Widget _buildTrialUpgradeCard() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20.0),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              AppTheme.primaryDark.withValues(alpha: 0.1),
              AppTheme.primaryDark.withValues(alpha: 0.05),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppTheme.primaryDark.withValues(alpha: 0.3)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryDark.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(
                    Icons.workspace_premium,
                    color: AppTheme.primaryDark,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Unlock Full Analysis',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      SizedBox(height: 2),
                      Text(
                        'Trial Plan',
                        style: TextStyle(
                          fontSize: 13,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            const Text(
              'Upgrade to Basic to see:',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            _buildUpgradeFeatureItem(Icons.analytics_outlined, 'Full AI Risk Analysis'),
            _buildUpgradeFeatureItem(Icons.percent, 'Underwriting Percentage'),
            _buildUpgradeFeatureItem(Icons.attach_money, 'Premium Pricing'),
            _buildUpgradeFeatureItem(Icons.description_outlined, 'Coverage Details'),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => context.go('/subscription'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryDark,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
                child: const Text(
                  'Upgrade to Basic',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildUpgradeFeatureItem(IconData icon, String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          Icon(icon, size: 18, color: AppTheme.primaryDark),
          const SizedBox(width: 10),
          Text(
            text,
            style: const TextStyle(
              fontSize: 14,
              color: AppTheme.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildUpgradePrompt() {
    final message = _isTrial
        ? 'Upgrade to Basic for full risk analysis, underwriting details & pricing'
        : 'Upgrade to Premium for chat, AI documents & deep analysis';
    final targetTier = _isTrial ? 'Basic' : 'Premium';

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20.0),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.primaryDark.withValues(alpha: 0.05),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.primaryDark.withValues(alpha: 0.2)),
        ),
        child: Row(
          children: [
            Icon(Icons.upgrade_outlined, color: AppTheme.primaryDark),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                message,
                style: const TextStyle(
                  fontSize: 14,
                  color: AppTheme.textSecondary,
                ),
              ),
            ),
            TextButton(
              onPressed: () => context.go('/subscription'),
              child: Text(
                'Upgrade',
                style: TextStyle(
                  color: AppTheme.primaryDark,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Build an expandable card for each AI agent's report
  Widget _buildAgentReportCard(String agentName, Map<String, dynamic> data) {
    // Format agent name for display
    final displayName = _formatAgentName(agentName);
    final agentIcon = _getAgentIcon(agentName);
    final agentColor = _getAgentColor(agentName);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: agentColor.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: agentColor.withValues(alpha: 0.2)),
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          leading: Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: agentColor.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Icon(agentIcon, color: agentColor, size: 18),
          ),
          title: Text(
            displayName,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: agentColor,
              fontFamily: 'Inter',
            ),
          ),
          subtitle: Text(
            _getAgentSummary(agentName, data),
            style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          children: [
            // Render agent-specific data
            ...data.entries.where((e) => e.value != null && e.value.toString().isNotEmpty).map((entry) {
              final key = _formatFieldName(entry.key);
              final value = entry.value;

              // Skip internal fields
              if (entry.key.startsWith('_') || entry.key == 'raw_response') {
                return const SizedBox.shrink();
              }

              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      key,
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textSecondary,
                        letterSpacing: 0.5,
                      ),
                    ),
                    const SizedBox(height: 4),
                    _buildFieldValue(value),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  String _formatAgentName(String name) {
    final names = {
      'classifier': 'Document Classifier',
      'extractor': 'Data Extractor',
      'risk_analyst': 'Risk Analyst',
      'financial_analyst': 'Financial Analyst',
      'compliance': 'Compliance Officer',
      'exposure': 'Exposure Analyst',
      'underwriter': 'Underwriter',
      'verification': 'Verification Agent',
      'qa': 'Quality Assurance',
    };
    return names[name.toLowerCase()] ?? name.split('_').map((w) =>
      w.isNotEmpty ? '${w[0].toUpperCase()}${w.substring(1)}' : '').join(' ');
  }

  IconData _getAgentIcon(String name) {
    final icons = {
      'classifier': Icons.category_outlined,
      'extractor': Icons.data_object_outlined,
      'risk_analyst': Icons.trending_up_outlined,
      'financial_analyst': Icons.attach_money_outlined,
      'compliance': Icons.verified_outlined,
      'exposure': Icons.warning_amber_outlined,
      'underwriter': Icons.gavel_outlined,
      'verification': Icons.fact_check_outlined,
      'qa': Icons.check_circle_outline,
    };
    return icons[name.toLowerCase()] ?? Icons.smart_toy_outlined;
  }

  Color _getAgentColor(String name) {
    final colors = {
      'classifier': const Color(0xFF2563EB),
      'extractor': const Color(0xFF059669),
      'risk_analyst': const Color(0xFFDC2626),
      'financial_analyst': const Color(0xFF7C3AED),
      'compliance': const Color(0xFF0891B2),
      'exposure': const Color(0xFFF59E0B),
      'underwriter': const Color(0xFF4F46E5),
      'verification': const Color(0xFF10B981),
      'qa': const Color(0xFF6366F1),
    };
    return colors[name.toLowerCase()] ?? AppTheme.primaryDark;
  }

  String _getAgentSummary(String name, Map<String, dynamic> data) {
    switch (name.toLowerCase()) {
      case 'classifier':
        return 'Type: ${data['document_type'] ?? 'Unknown'}';
      case 'extractor':
        final insured = data['insured']?['name'] ?? data['company_name'] ?? '';
        return insured.isNotEmpty ? 'Insured: $insured' : 'Data extracted';
      case 'risk_analyst':
        final level = data['overall_risk_level'] ?? data['risk_level'] ?? '';
        return level.isNotEmpty ? 'Risk: $level' : 'Risk analyzed';
      case 'underwriter':
        return 'Decision: ${data['decision'] ?? 'Pending'}';
      case 'qa':
        return 'Status: ${data['overall_status'] ?? 'Reviewed'}';
      default:
        return 'Analysis complete';
    }
  }

  String _formatFieldName(String name) {
    return name.replaceAll('_', ' ').split(' ').map((w) =>
      w.isNotEmpty ? '${w[0].toUpperCase()}${w.substring(1)}' : '').join(' ');
  }

  Widget _buildFieldValue(dynamic value) {
    if (value is Map) {
      return Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: AppTheme.background,
          borderRadius: BorderRadius.circular(6),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: value.entries.map((e) => Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${_formatFieldName(e.key.toString())}: ',
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary, fontWeight: FontWeight.w500)),
                Expanded(child: Text('${e.value}',
                  style: const TextStyle(fontSize: 12, color: AppTheme.textPrimary))),
              ],
            ),
          )).toList(),
        ),
      );
    } else if (value is List) {
      return Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: AppTheme.background,
          borderRadius: BorderRadius.circular(6),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: value.map((item) => Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('• ', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                Expanded(child: Text('$item', style: const TextStyle(fontSize: 12, color: AppTheme.textPrimary))),
              ],
            ),
          )).toList(),
        ),
      );
    } else {
      return Text(
        value.toString(),
        style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary, height: 1.4),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        backgroundColor: AppTheme.background,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios, color: AppTheme.textPrimary),
            onPressed: () => context.go('/reports'),
          ),
        ),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (_error != null) {
      return Scaffold(
        backgroundColor: AppTheme.background,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios, color: AppTheme.textPrimary),
            onPressed: () => context.go('/reports'),
          ),
        ),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.error_outline, size: 64, color: AppTheme.danger),
              const SizedBox(height: 16),
              Text(_error!, style: TextStyle(color: AppTheme.textSecondary)),
              const SizedBox(height: 16),
              ElevatedButton(onPressed: _fetchData, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }

    // Show processing error state
    if (_hasProcessingError) {
      return _buildProcessingErrorState();
    }

    // Show live processing progress
    if (_isProcessing) {
      return _buildProcessingState();
    }

    // Wait for data to be ready before showing decision to prevent flash
    final hasData = _assessment != null || _analysis != null;
    if (!hasData) {
      return Scaffold(
        backgroundColor: AppTheme.background,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios, color: AppTheme.textPrimary),
            onPressed: () => context.go('/reports'),
          ),
        ),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    final decisionColor = isApproved ? AppTheme.success : AppTheme.danger;
    final decisionText = isApproved ? 'GO' : 'NO-GO';
    final decisionIcon = isApproved ? Icons.check : Icons.close;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppTheme.textPrimary),
          onPressed: () => context.go('/reports'),
        ),
        title: Text(
          referenceNumber.isNotEmpty ? referenceNumber : 'Assessment Results',
          style: const TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
            fontFamily: 'Inter',
          ),
        ),
        centerTitle: true,
        actions: [
          // Rename button (all tiers)
          IconButton(
            icon: const Icon(Icons.edit_outlined, color: AppTheme.textPrimary),
            onPressed: _showRenameDialog,
            tooltip: 'Rename Analysis',
          ),
          IconButton(
            icon: const Icon(Icons.share_outlined, color: AppTheme.textPrimary),
            onPressed: _shareResults,
          ),
        ],
      ),
      body: SingleChildScrollView(
        child: Column(
          children: [
            // GO/NO-GO Decision Circle (or locked for trial users)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 32),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    _canSeeDecision
                        ? decisionColor.withValues(alpha: 0.1)
                        : Colors.grey.withValues(alpha: 0.1),
                    AppTheme.background,
                  ],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
              ),
              child: Column(
                children: [
                  // Large Decision Circle (or locked state)
                  if (_canSeeDecision)
                    Container(
                      width: 160,
                      height: 160,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: decisionColor,
                        boxShadow: [
                          BoxShadow(
                            color: decisionColor.withValues(alpha: 0.4),
                            blurRadius: 30,
                            spreadRadius: 5,
                          ),
                        ],
                      ),
                      child: Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              decisionIcon,
                              color: Colors.white,
                              size: 48,
                            ),
                            const SizedBox(height: 4),
                            Text(
                              decisionText,
                              style: const TextStyle(
                                fontSize: 32,
                                fontWeight: FontWeight.w800,
                                color: Colors.white,
                                fontFamily: 'Inter',
                                letterSpacing: 2,
                              ),
                            ),
                          ],
                        ),
                      ),
                    )
                  else
                    // Locked decision for trial users
                    Container(
                      width: 160,
                      height: 160,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: Colors.grey.shade400,
                        boxShadow: [
                          BoxShadow(
                            color: Colors.grey.withValues(alpha: 0.3),
                            blurRadius: 30,
                            spreadRadius: 5,
                          ),
                        ],
                      ),
                      child: Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Icon(
                              Icons.lock_outline,
                              color: Colors.white,
                              size: 48,
                            ),
                            const SizedBox(height: 4),
                            const Text(
                              '???',
                              style: TextStyle(
                                fontSize: 32,
                                fontWeight: FontWeight.w800,
                                color: Colors.white,
                                fontFamily: 'Inter',
                                letterSpacing: 2,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  const SizedBox(height: 24),

                  // Company & Risk Type
                  Text(
                    companyName,
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                      fontFamily: 'Inter',
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    riskType,
                    style: const TextStyle(
                      fontSize: 16,
                      color: AppTheme.textSecondary,
                      fontFamily: 'Inter',
                    ),
                  ),
                  if (territory.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      territory,
                      style: const TextStyle(
                        fontSize: 14,
                        color: AppTheme.textHint,
                        fontFamily: 'Inter',
                      ),
                    ),
                  ],
                ],
              ),
            ),

            // Trial upgrade prompt - show immediately after decision
            if (_isTrial) ...[
              _buildTrialUpgradeCard(),
              const SizedBox(height: 24),
            ],

            // Underwriting Summary (Basic+ only) - Key metrics for underwriters
            if (_isBasicOrHigher) ...[
              _buildUnderwritingSummary(),
              const SizedBox(height: 24),
            ],

            // Key Metrics Cards - Confidence and Documents (Premium only for detailed view)
            if (_isPremium)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: Row(
                  children: [
                    Expanded(
                      child: _buildMetricCard(
                        title: 'Confidence',
                        value: '$confidencePercent%',
                        subtitle: _getConfidenceLevel(confidencePercent),
                        icon: Icons.verified_outlined,
                        color: _getConfidenceColor(confidencePercent),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _buildMetricCard(
                        title: 'Documents',
                        value: documentsAnalyzed > 0 ? '$documentsAnalyzed' : '-',
                        subtitle: 'Analyzed',
                        icon: Icons.description_outlined,
                        color: AppTheme.primaryDark,
                      ),
                    ),
                  ],
                ),
              ),
            if (_isPremium) const SizedBox(height: 24),

            // Upgrade Analysis Card (Premium only - they can upgrade to deeper modes)
            if (_isPremium) _buildUpgradeCard(),
            if (_isPremium && canUpgradeAnalysis) const SizedBox(height: 24),

            // Coverage Details (Basic+ only)
            if (_isBasicOrHigher && coverageDetails.isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: AppTheme.primaryDark.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: const Icon(
                              Icons.description_outlined,
                              color: AppTheme.primaryDark,
                              size: 20,
                            ),
                          ),
                          const SizedBox(width: 12),
                          const Text(
                            'Coverage Details',
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.textPrimary,
                              fontFamily: 'Inter',
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Text(
                        coverageDetails,
                        style: const TextStyle(
                          fontSize: 14,
                          color: AppTheme.textSecondary,
                          height: 1.5,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            if (_isBasicOrHigher && coverageDetails.isNotEmpty) const SizedBox(height: 24),

            // "View Full Analysis" toggle button
            if (_isBasicOrHigher)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: () => setState(() => _showDetails = !_showDetails),
                    icon: Icon(_showDetails ? Icons.expand_less : Icons.expand_more, size: 20),
                    label: Text(_showDetails ? 'Hide Detailed Analysis' : 'View Full Analysis'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFF8B00FF),
                      side: BorderSide(color: const Color(0xFF8B00FF).withValues(alpha: 0.3)),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                ),
              ),
            if (_isBasicOrHigher) const SizedBox(height: 24),

            // === DETAIL SECTIONS (hidden by default, shown on toggle) ===

            // Risk Factors (from AI analysis) - Basic+ only
            if (_isBasicOrHigher && _showDetails) ...[
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: AppTheme.warning.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: const Icon(
                              Icons.warning_amber_outlined,
                              color: AppTheme.warning,
                              size: 20,
                            ),
                          ),
                          const SizedBox(width: 12),
                          const Expanded(
                            child: Text(
                              'AI Risk Analysis',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.w600,
                                color: AppTheme.textPrimary,
                                fontFamily: 'Inter',
                              ),
                            ),
                          ),
                          if (riskFactors.isEmpty && !_isRunningAnalysis)
                            ElevatedButton.icon(
                              onPressed: _triggerAIAnalysis,
                              icon: const Icon(Icons.auto_awesome, size: 16),
                              label: const Text('Analyze'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: AppTheme.primaryDark,
                                foregroundColor: Colors.white,
                                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(8),
                                ),
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      if (_isRunningAnalysis)
                        const Center(
                          child: Padding(
                            padding: EdgeInsets.all(20),
                            child: Column(
                              children: [
                                CircularProgressIndicator(),
                                SizedBox(height: 12),
                                Text(
                                  'Running AI analysis...',
                                  style: TextStyle(color: AppTheme.textSecondary),
                                ),
                              ],
                            ),
                          ),
                        )
                      else if (riskFactors.isEmpty)
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: AppTheme.background,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Column(
                            children: [
                              Icon(
                                Icons.analytics_outlined,
                                size: 40,
                                color: AppTheme.textHint,
                              ),
                              const SizedBox(height: 12),
                              Text(
                                AppLocalizations.of(context).noAiAnalysisYet,
                                textAlign: TextAlign.center,
                                style: const TextStyle(
                                  fontSize: 13,
                                  color: AppTheme.textSecondary,
                                ),
                              ),
                            ],
                          ),
                        )
                      else
                        ...riskFactors.map((factor) => Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                margin: const EdgeInsets.only(top: 6),
                                width: 6,
                                height: 6,
                                decoration: const BoxDecoration(
                                  color: AppTheme.primaryDark,
                                  shape: BoxShape.circle,
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Text(
                                  factor.toString(),
                                  style: const TextStyle(
                                    fontSize: 14,
                                    color: AppTheme.textSecondary,
                                    height: 1.4,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        )),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
            ],

            // Pricing Factors Section - Key data for underwriting decisions (Premium only)
            if (_isPremium && pricingFactors.isNotEmpty && _showDetails)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.primaryDark.withValues(alpha: 0.2)),
                  ),
                  child: Theme(
                    data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                    child: ExpansionTile(
                      initiallyExpanded: false,
                      tilePadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                      childrenPadding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                      leading: Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AppTheme.primaryDark.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(
                          Icons.analytics_outlined,
                          color: AppTheme.primaryDark,
                          size: 20,
                        ),
                      ),
                      title: const Text(
                        'Pricing Factors',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                          fontFamily: 'Inter',
                        ),
                      ),
                      subtitle: Text(
                        '${pricingFactors.length} categories extracted',
                        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                      ),
                      children: [
                        Text(
                          'Key data extracted from documents for pricing decisions',
                          style: TextStyle(
                            fontSize: 13,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                        const SizedBox(height: 16),

                        // Display each category of pricing factors
                        ...pricingFactors.entries.map((category) {
                          final categoryName = _formatFactorName(category.key);
                          final categoryData = category.value as Map<String, dynamic>;
                          final categoryIcon = _getPricingCategoryIcon(category.key);
                          final categoryColor = _getPricingCategoryColor(category.key);

                          return Container(
                            margin: const EdgeInsets.only(bottom: 12),
                            decoration: BoxDecoration(
                              color: categoryColor.withValues(alpha: 0.05),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: categoryColor.withValues(alpha: 0.2)),
                            ),
                            child: Theme(
                              data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                              child: ExpansionTile(
                                initiallyExpanded: false,
                                tilePadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
                                childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
                                leading: Container(
                                  padding: const EdgeInsets.all(6),
                                  decoration: BoxDecoration(
                                    color: categoryColor.withValues(alpha: 0.15),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Icon(categoryIcon, color: categoryColor, size: 16),
                                ),
                                title: Text(
                                  categoryName,
                                  style: TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w600,
                                    color: categoryColor,
                                    fontFamily: 'Inter',
                                  ),
                                ),
                                subtitle: Text(
                                  '${categoryData.length} fields extracted',
                                  style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                                ),
                                children: [
                                  ...categoryData.entries.map((field) {
                                    final fieldName = _formatFactorName(field.key);
                                    final fieldValue = field.value;

                                    return Padding(
                                      padding: const EdgeInsets.only(bottom: 8),
                                      child: Row(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          SizedBox(
                                            width: 120,
                                            child: Text(
                                              fieldName,
                                              style: const TextStyle(
                                                fontSize: 12,
                                                color: AppTheme.textSecondary,
                                                fontWeight: FontWeight.w500,
                                              ),
                                            ),
                                          ),
                                          Expanded(
                                            child: _buildPricingFactorValue(fieldValue),
                                          ),
                                        ],
                                      ),
                                    );
                                  }),
                                ],
                              ),
                            ),
                          );
                        }),

                        // Info note
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: AppTheme.background,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Row(
                            children: [
                              Icon(Icons.info_outline, size: 16, color: AppTheme.textHint),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  'Data automatically extracted from uploaded documents by AI analysis',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: AppTheme.textSecondary,
                                    height: 1.4,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            if (_isPremium && pricingFactors.isNotEmpty && _showDetails) const SizedBox(height: 24),

            // Decision Rationale (Extensive GO/NO-GO Summary) - Basic+ only
            // Trial users see only the Go/No-Go decision, not the detailed rationale
            if (_isBasicOrHigher && decisionRationale.isNotEmpty && _showDetails)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: decisionColor.withValues(alpha: 0.3)),
                  ),
                  child: Theme(
                    data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                    child: ExpansionTile(
                      initiallyExpanded: false,
                      tilePadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                      childrenPadding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                      leading: Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: decisionColor.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Icon(
                          Icons.gavel_outlined,
                          color: decisionColor,
                          size: 20,
                        ),
                      ),
                      title: const Text(
                        'Underwriting Decision',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                          fontFamily: 'Inter',
                        ),
                      ),
                      subtitle: Text(
                        'AI rationale for $decisionText decision',
                        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                      ),
                      children: [
                        Text(
                          decisionRationale,
                          style: const TextStyle(
                            fontSize: 14,
                            color: AppTheme.textSecondary,
                            height: 1.6,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            if (_isBasicOrHigher && decisionRationale.isNotEmpty) const SizedBox(height: 24),

            // Agent Reports Section - Expandable details for each AI agent (Premium only)
            if (_isPremium && agentResults.isNotEmpty && _showDetails)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Theme(
                    data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                    child: ExpansionTile(
                      initiallyExpanded: false,
                      tilePadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                      childrenPadding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                      leading: Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: const Color(0xFF7C3AED).withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(
                          Icons.psychology_outlined,
                          color: Color(0xFF7C3AED),
                          size: 20,
                        ),
                      ),
                      title: const Text(
                        'AI Agent Reports',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                          fontFamily: 'Inter',
                        ),
                      ),
                      subtitle: Text(
                        '$agentsUsed agents analyzed this submission',
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                      children: [
                        // Render each agent's report
                        ...agentResults.entries.map((entry) {
                          final agentName = entry.key;
                          final agentData = entry.value as Map<String, dynamic>?;
                          if (agentData == null) return const SizedBox.shrink();

                          return _buildAgentReportCard(agentName, agentData);
                        }),
                      ],
                    ),
                  ),
                ),
              ),
            if (_isPremium && agentResults.isNotEmpty) const SizedBox(height: 24),

            // OCR Extracted Text Section (Premium only)
            if (_isPremium && ocrExtractedText.isNotEmpty && _showDetails)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20.0),
                child: Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Theme(
                    data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                    child: ExpansionTile(
                      initiallyExpanded: false,
                      tilePadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                      childrenPadding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                      leading: Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AppTheme.primaryDark.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(
                          Icons.document_scanner_outlined,
                          color: AppTheme.primaryDark,
                          size: 20,
                        ),
                      ),
                      title: const Text(
                        'OCR Extracted Text',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                          fontFamily: 'Inter',
                        ),
                      ),
                      subtitle: Text(
                        '${ocrExtractedText.length} characters extracted',
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                      children: [
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: AppTheme.background,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: AppTheme.border.withValues(alpha: 0.5)),
                          ),
                          constraints: const BoxConstraints(maxHeight: 300),
                          child: SingleChildScrollView(
                            child: SelectableText(
                              ocrExtractedText,
                              style: const TextStyle(
                                fontSize: 13,
                                color: AppTheme.textSecondary,
                                height: 1.5,
                                fontFamily: 'monospace',
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            if (_isPremium && ocrExtractedText.isNotEmpty && _showDetails) const SizedBox(height: 24),

            // Upgrade prompt for lower tiers
            if (!_isPremium) ...[
              _buildUpgradePrompt(),
              const SizedBox(height: 24),
            ],

            // Action Buttons
            Padding(
              padding: const EdgeInsets.all(20.0),
              child: Column(
                children: [
                  // AI Generate Documents Button (Premium only, enabled for GO and NO_GO)
                  if (_isPremium) ...[
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: () => context.go('/documents/ai-advisor/${widget.assessmentId}'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.primaryDark,
                          foregroundColor: Colors.white,
                          disabledBackgroundColor: AppTheme.border,
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                        child: const Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.auto_awesome, size: 20),
                            SizedBox(width: 8),
                            Text(
                              'AI Generate Documents',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                  ],

                  // Secondary Actions
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          icon: const Icon(Icons.share_outlined, size: 18),
                          label: const Text('Share'),
                          onPressed: _shareResults,
                          style: OutlinedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(vertical: 14),
                            side: const BorderSide(color: AppTheme.border),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: OutlinedButton.icon(
                          icon: const Icon(Icons.refresh, size: 18),
                          label: const Text('Refresh'),
                          onPressed: _fetchData,
                          style: OutlinedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(vertical: 14),
                            side: const BorderSide(color: AppTheme.border),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 40),
          ],
        ),
      ),
    );
  }

  /// Build processing state UI - shows live progress
  Widget _buildProcessingState() {
    const modeColor = Color(0xFF7C3AED); // Deep analysis purple

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: AppTheme.surface,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.close, color: AppTheme.textPrimary),
          onPressed: _showCancelConfirmation,
        ),
        title: const Text(
          'Deep Analysis',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: modeColor,
            fontFamily: 'Inter',
          ),
        ),
        centerTitle: true,
      ),
      body: Column(
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
                            style: const TextStyle(
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

                // Document progress indicator
                if (_totalDocuments > 1 || widget.documentCount > 1)
                  Container(
                    width: double.infinity,
                    margin: const EdgeInsets.only(bottom: 16),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: modeColor.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: modeColor.withValues(alpha: 0.3)),
                    ),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: modeColor.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: const Icon(
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
                                style: const TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w700,
                                  color: modeColor,
                                  letterSpacing: 0.5,
                                ),
                              ),
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
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(color: modeColor.withValues(alpha: 0.3)),
                          ),
                          child: Text(
                            '${(_totalDocuments > 0 ? _totalDocuments : widget.documentCount) - (_currentDocument > 0 ? _currentDocument : 1)} left',
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: modeColor,
                            ),
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
                        color: modeColor.withValues(alpha: 0.05 + (_pulseController.value * 0.05)),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: modeColor.withValues(alpha: 0.2)),
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
                                  color: modeColor.withValues(alpha: 0.5),
                                  blurRadius: 8,
                                  spreadRadius: _pulseController.value * 2,
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 12),
                          Text(
                            _currentAgent.isEmpty ? 'Initializing' : _currentAgent,
                            style: const TextStyle(
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

                Text(
                  _currentDescription,
                  style: const TextStyle(
                    fontSize: 14,
                    color: AppTheme.textSecondary,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),

          // Live findings panel
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                // Live findings
                if (_liveFindings.isNotEmpty)
                  _buildLiveFindingsPanel(modeColor),

                const SizedBox(height: 16),

                // Analysis summary
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
                          const Icon(Icons.analytics_outlined, size: 18, color: modeColor),
                          const SizedBox(width: 8),
                          const Text(
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
                      _buildProgressSummaryRow('Mode', 'Deep Analysis'),
                      _buildProgressSummaryRow('Documents', '${_totalDocuments > 0 ? _totalDocuments : widget.documentCount}'),
                      _buildProgressSummaryRow('Agents', '$_totalAgents'),
                      _buildProgressSummaryRow('Progress', '${_progressPercent.toInt()}%'),
                    ],
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
                  const Icon(Icons.timer_outlined, size: 16, color: AppTheme.textSecondary),
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
      ),
    );
  }

  Widget _buildProgressSummaryRow(String label, String value) {
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

  Widget _buildLiveFindingsPanel(Color modeColor) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: modeColor.withValues(alpha: 0.3)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: modeColor.withValues(alpha: 0.05),
              borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
            ),
            child: Row(
              children: [
                Icon(Icons.stream, size: 20, color: modeColor),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Live Findings',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: modeColor,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: modeColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    '${_liveFindings.length}',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: modeColor,
                    ),
                  ),
                ),
              ],
            ),
          ),
          Container(
            constraints: const BoxConstraints(maxHeight: 200),
            child: ListView.builder(
              shrinkWrap: true,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              itemCount: _liveFindings.length > 10 ? 10 : _liveFindings.length,
              itemBuilder: (context, index) {
                final finding = _liveFindings.reversed.toList()[index];
                return _buildLiveFindingItem(finding, modeColor);
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLiveFindingItem(Map<String, dynamic> finding, Color modeColor) {
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
        typeColor = modeColor;
        typeIcon = Icons.info_outline;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: typeColor.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: typeColor.withValues(alpha: 0.15)),
      ),
      child: Row(
        children: [
          Icon(typeIcon, size: 16, color: typeColor),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(
                    fontSize: 10,
                    color: AppTheme.textSecondary,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                Text(
                  value,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// Build processing error state with helpful error messages
  Widget _buildProcessingErrorState() {
    // Parse error message to show helpful tips
    final errorMsg = _processingErrorMessage ?? 'An unexpected error occurred';
    final isTimeout = errorMsg.toLowerCase().contains('timeout');
    final isConnection = errorMsg.toLowerCase().contains('connection') ||
                         errorMsg.toLowerCase().contains('network');
    final isServer = errorMsg.toLowerCase().contains('server') ||
                     errorMsg.toLowerCase().contains('500');

    String helpText;
    String suggestionText;
    IconData suggestionIcon;

    if (isTimeout) {
      helpText = 'The analysis took too long to complete.';
      suggestionText = 'Try with fewer documents or use Quick Analysis mode.';
      suggestionIcon = Icons.timer_off;
    } else if (isConnection) {
      helpText = 'Connection was lost during analysis.';
      suggestionText = 'Check your internet connection and try again.';
      suggestionIcon = Icons.wifi_off;
    } else if (isServer) {
      helpText = 'Our servers are experiencing issues.';
      suggestionText = 'Please wait a moment and try again.';
      suggestionIcon = Icons.cloud_off;
    } else {
      helpText = 'Something went wrong during analysis.';
      suggestionText = 'Try again or use a different analysis mode.';
      suggestionIcon = Icons.help_outline;
    }

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppTheme.textPrimary),
          onPressed: () => context.go('/home'),
        ),
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: const Color(0xFFDC2626).withValues(alpha: 0.1),
                ),
                child: const Icon(
                  Icons.error_outline,
                  size: 48,
                  color: Color(0xFFDC2626),
                ),
              ),
              const SizedBox(height: 24),
              const Text(
                'Analysis Failed',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFFDC2626),
                ),
              ),
              const SizedBox(height: 12),
              Text(
                helpText,
                style: const TextStyle(
                  fontSize: 16,
                  color: AppTheme.textPrimary,
                  fontWeight: FontWeight.w500,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),

              // Suggestion card
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.warning.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.warning.withValues(alpha: 0.3)),
                ),
                child: Row(
                  children: [
                    Icon(suggestionIcon, color: AppTheme.warning, size: 24),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        suggestionText,
                        style: const TextStyle(
                          fontSize: 14,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              // Technical details (collapsed by default)
              if (errorMsg.isNotEmpty && errorMsg != 'An unexpected error occurred') ...[
                const SizedBox(height: 16),
                ExpansionTile(
                  title: const Text(
                    'Technical Details',
                    style: TextStyle(fontSize: 14, color: AppTheme.textSecondary),
                  ),
                  children: [
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: Text(
                        errorMsg,
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppTheme.textHint,
                          fontFamily: 'Courier',
                        ),
                      ),
                    ),
                  ],
                ),
              ],

              const SizedBox(height: 32),

              // Retry button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: () {
                    setState(() {
                      _hasProcessingError = false;
                      _processingErrorMessage = null;
                      _isProcessing = true;
                      _progressPercent = 0;
                      _elapsedSeconds = 0;
                      _startTime = DateTime.now();
                    });
                    _startElapsedTimer();
                    if (widget.sessionId != null) {
                      _connectWebSocket(widget.sessionId!);
                    }
                  },
                  icon: const Icon(Icons.refresh, color: Colors.white),
                  label: const Text('Try Again', style: TextStyle(color: Colors.white)),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryDark,
                    padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 12),

              // Upload new documents button
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () => context.go('/home/intake'),
                  icon: const Icon(Icons.upload_file),
                  label: const Text('Upload New Documents'),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 12),

              TextButton(
                onPressed: () => context.go('/home'),
                child: const Text('Go to Dashboard'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showCancelConfirmation() {
    showDialog(
      context: context,
      barrierDismissible: true,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Leave Analysis?'),
        content: const Text(
          'The analysis is running. You can:\n\n'
          '\u2022 Run in background - analysis continues, check results later in Reports\n'
          '\u2022 Stay here - wait for completion',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Stay Here'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              context.go('/home');
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryDark,
            ),
            child: const Text('Run in Background'),
          ),
        ],
      ),
    );
  }

  Widget _buildMetricCard({
    required String title,
    required String value,
    required String subtitle,
    required IconData icon,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: color, size: 18),
              ),
              Text(
                subtitle,
                style: const TextStyle(
                  fontSize: 12,
                  color: AppTheme.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            value,
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w700,
              color: color,
              fontFamily: 'Inter',
            ),
          ),
          const SizedBox(height: 4),
          Text(
            title,
            style: const TextStyle(
              fontSize: 14,
              color: AppTheme.textSecondary,
              fontFamily: 'Inter',
            ),
          ),
        ],
      ),
    );
  }

  String _getRiskLevel(int score) {
    if (score >= 70) return 'High Risk';
    if (score >= 40) return 'Medium Risk';
    return 'Low Risk';
  }

  String _getConfidenceLevel(int score) {
    if (score >= 80) return 'High Confidence';
    if (score >= 60) return 'Good';
    if (score >= 40) return 'Moderate';
    return 'Low';
  }

  Color _getConfidenceColor(int score) {
    if (score >= 80) return AppTheme.success;
    if (score >= 60) return AppTheme.primaryDark;
    if (score >= 40) return AppTheme.warning;
    return AppTheme.danger;
  }

  Color _getRiskScoreColor(int score) {
    if (score >= 70) return AppTheme.success;
    if (score >= 50) return AppTheme.warning;
    return AppTheme.danger;
  }

  String _formatCurrency(double value) {
    if (value >= 1000000) {
      return '${(value / 1000000).toStringAsFixed(1)}M';
    } else if (value >= 1000) {
      return '${(value / 1000).toStringAsFixed(1)}k';
    }
    return value.toStringAsFixed(0);
  }

  Widget _buildPricingMetric(String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 11,
                    color: color,
                  ),
                ),
                Text(
                  value,
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: color,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatFactorName(String key) {
    return key
        .replaceAll('_', ' ')
        .split(' ')
        .map((word) => word.isNotEmpty ? '${word[0].toUpperCase()}${word.substring(1)}' : '')
        .join(' ');
  }

  IconData _getPricingCategoryIcon(String category) {
    final icons = {
      'insured_profile': Icons.business_outlined,
      'financial_metrics': Icons.attach_money_outlined,
      'coverage_details': Icons.shield_outlined,
      'claims_history': Icons.history_outlined,
      'geographic_exposure': Icons.public_outlined,
      'risk_indicators': Icons.warning_amber_outlined,
      'key_personnel': Icons.people_outline,
    };
    return icons[category] ?? Icons.folder_outlined;
  }

  Color _getPricingCategoryColor(String category) {
    final colors = {
      'insured_profile': const Color(0xFF2563EB),
      'financial_metrics': const Color(0xFF059669),
      'coverage_details': const Color(0xFF7C3AED),
      'claims_history': const Color(0xFFDC2626),
      'geographic_exposure': const Color(0xFF0891B2),
      'risk_indicators': const Color(0xFFF59E0B),
      'key_personnel': const Color(0xFF4F46E5),
    };
    return colors[category] ?? AppTheme.primaryDark;
  }

  Widget _buildPricingFactorValue(dynamic value) {
    if (value is Map) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: (value as Map<String, dynamic>).entries.map((e) => Padding(
          padding: const EdgeInsets.only(bottom: 2),
          child: Text(
            '${_formatFactorName(e.key.toString())}: ${e.value}',
            style: const TextStyle(fontSize: 12, color: AppTheme.textPrimary),
          ),
        )).toList(),
      );
    } else if (value is List) {
      if (value.isEmpty) return const SizedBox.shrink();
      // Check if list contains maps (e.g., directors, officers)
      if (value.first is Map) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: value.take(5).map((item) {
            final itemMap = item as Map<String, dynamic>;
            final name = itemMap['name'] ?? itemMap['company_name'] ?? '';
            final role = itemMap['role'] ?? itemMap['percentage'] ?? '';
            return Padding(
              padding: const EdgeInsets.only(bottom: 2),
              child: Text(
                role != null && role.toString().isNotEmpty ? '$name ($role)' : name.toString(),
                style: const TextStyle(fontSize: 12, color: AppTheme.textPrimary),
              ),
            );
          }).toList(),
        );
      }
      // Simple list
      return Text(
        value.take(5).join(', '),
        style: const TextStyle(fontSize: 12, color: AppTheme.textPrimary),
      );
    } else if (value is num) {
      // Format numbers nicely
      if (value >= 1000000) {
        return Text(
          '${(value / 1000000).toStringAsFixed(1)}M',
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textPrimary),
        );
      } else if (value >= 1000) {
        return Text(
          '${(value / 1000).toStringAsFixed(1)}k',
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textPrimary),
        );
      }
      return Text(
        value.toString(),
        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textPrimary),
      );
    }
    return Text(
      value.toString(),
      style: const TextStyle(fontSize: 12, color: AppTheme.textPrimary),
    );
  }
}
