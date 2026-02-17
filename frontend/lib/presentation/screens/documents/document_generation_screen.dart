import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import 'dart:async';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/language_service.dart';
import '../../../core/services/subscription_service.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../widgets/clause_selector_widget.dart';
import '../../widgets/feature_gate_widget.dart';
// God Mode: Vision OCR confidence
import '../../widgets/vision/property_risk_card.dart';

/// Document Generation Screen - AI-Powered Document Generation from Assessments
class DocumentGenerationScreen extends ConsumerStatefulWidget {
  final String assessmentId;

  const DocumentGenerationScreen({
    super.key,
    required this.assessmentId,
  });

  @override
  ConsumerState<DocumentGenerationScreen> createState() => _DocumentGenerationScreenState();
}

class _DocumentGenerationScreenState extends ConsumerState<DocumentGenerationScreen> {
  bool _isLoadingSuggestions = true;
  bool _isGenerating = false;
  List<Map<String, dynamic>> _suggestions = [];
  List<Map<String, dynamic>> _lmaClauses = [];
  Set<String> _selectedDocs = {};
  Set<String> _selectedClauses = {};
  String? _currentAgent;
  String? _currentDescription;
  int _progressPercentage = 0;
  String? _generationJobId;
  List<Map<String, dynamic>> _generatedDocs = [];
  Timer? _pollTimer;
  List<Map<String, dynamic>> _progressSteps = [];
  int _pollErrorCount = 0;
  static const int _maxPollErrors = 15; // Max retries before giving up (30 seconds)

  // New state for loading status and language selection
  String _loadingStatus = 'Initializing...';
  String _selectedLanguage = 'en';

  // Available languages for document generation
  final List<Map<String, String>> _availableLanguages = [
    {'code': 'en', 'name': 'English'},
    {'code': 'de', 'name': 'German (Deutsch)'},
    {'code': 'fr', 'name': 'French (Français)'},
    {'code': 'es', 'name': 'Spanish (Español)'},
    {'code': 'it', 'name': 'Italian (Italiano)'},
    {'code': 'pt', 'name': 'Portuguese (Português)'},
    {'code': 'nl', 'name': 'Dutch (Nederlands)'},
    {'code': 'ar', 'name': 'Arabic (العربية)'},
    {'code': 'zh', 'name': 'Chinese (中文)'},
    {'code': 'ja', 'name': 'Japanese (日本語)'},
    {'code': 'ko', 'name': 'Korean (한국어)'},
    {'code': 'hi', 'name': 'Hindi (हिन्दी)'},
  ];

  @override
  void initState() {
    super.initState();
    _loadSuggestions();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadSuggestions() async {
    try {
      setState(() {
        _isLoadingSuggestions = true;
        _loadingStatus = 'Analyzing assessment data...';
      });

      // Simulate progressive loading status
      await Future.delayed(const Duration(milliseconds: 300));
      if (mounted) {
        setState(() => _loadingStatus = 'Fetching document templates...');
      }

      final response = await authService.post(
        '/assessments/${widget.assessmentId}/suggest-documents',
        body: {},
      );

      if (mounted) {
        setState(() => _loadingStatus = 'Loading recommended clauses...');
      }

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _suggestions = List<Map<String, dynamic>>.from(data['suggested_documents'] ?? []);
        _lmaClauses = List<Map<String, dynamic>>.from(data['lma_clauses'] ?? []);

        // Auto-select mandatory documents
        for (final doc in _suggestions) {
          if (doc['mandatory'] == true) {
            final docType = doc['document_type']?.toString();
            if (docType != null && docType.isNotEmpty) {
              _selectedDocs.add(docType);
            }
          }
        }

        // Auto-select pre-selected LMA clauses (mandatory + selected)
        for (final clause in _lmaClauses) {
          if (clause['selected'] == true || clause['mandatory'] == true) {
            final clauseId = clause['id']?.toString();
            if (clauseId != null && clauseId.isNotEmpty) {
              _selectedClauses.add(clauseId);
            }
          }
        }

        // Sort clauses: selected/mandatory first, then by category
        _lmaClauses.sort((a, b) {
          // Pre-selected/mandatory clauses first
          final aSelected = a['selected'] == true || a['mandatory'] == true;
          final bSelected = b['selected'] == true || b['mandatory'] == true;
          if (aSelected && !bSelected) return -1;
          if (!aSelected && bSelected) return 1;
          // Then mandatory before optional
          final aMandatory = a['mandatory'] == true;
          final bMandatory = b['mandatory'] == true;
          if (aMandatory && !bMandatory) return -1;
          if (!aMandatory && bMandatory) return 1;
          // Then by category
          return (a['category'] as String? ?? '').compareTo(b['category'] as String? ?? '');
        });

        // Set language from current app language
        _selectedLanguage = ref.read(languageProvider).languageCode;
      }

      setState(() => _isLoadingSuggestions = false);
    } catch (e) {
      setState(() => _isLoadingSuggestions = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load suggestions: $e')),
        );
      }
    }
  }

  void _showGenerationConfirmation() {
    if (_selectedDocs.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select at least one document to generate')),
      );
      return;
    }

    // Get selected document names
    final selectedDocNames = _suggestions
        .where((doc) => _selectedDocs.contains(doc['document_type']?.toString()))
        .map((doc) => doc['template_name'] as String? ?? (doc['document_type'] as String).replaceAll('_', ' '))
        .toList();

    // Get language name
    final langName = _availableLanguages
        .firstWhere((l) => l['code'] == _selectedLanguage, orElse: () => {'name': 'English'})['name']!;

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppTheme.primaryDark.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.summarize, color: AppTheme.primaryDark, size: 24),
            ),
            const SizedBox(width: 12),
            const Text('Generation Summary'),
          ],
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Documents
              Text(
                'Documents (${selectedDocNames.length})',
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
              ),
              const SizedBox(height: 8),
              ...selectedDocNames.map((name) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  children: [
                    const Icon(Icons.description, size: 16, color: AppTheme.primaryDark),
                    const SizedBox(width: 8),
                    Expanded(child: Text(name, style: const TextStyle(fontSize: 13))),
                  ],
                ),
              )),
              const Divider(height: 24),

              // Clauses
              Row(
                children: [
                  Text(
                    'Selected Clauses: ${_selectedClauses.length}',
                    style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.green.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      '${_selectedClauses.length}',
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: Colors.green,
                      ),
                    ),
                  ),
                ],
              ),
              const Divider(height: 24),

              // Language
              Row(
                children: [
                  const Icon(Icons.language, size: 16),
                  const SizedBox(width: 8),
                  Text('Language: $langName', style: const TextStyle(fontSize: 13)),
                ],
              ),
              const SizedBox(height: 16),

              // Pipeline info
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.info.withOpacity(0.05),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppTheme.info.withOpacity(0.2)),
                ),
                child: Row(
                  children: [
                    Icon(Icons.auto_awesome, size: 16, color: AppTheme.info),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'InstantRisk Engine will generate, validate, and refine your documents.',
                        style: TextStyle(fontSize: 12, color: AppTheme.info),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Back to Review'),
          ),
          ElevatedButton.icon(
            onPressed: () {
              Navigator.pop(context);
              _startGeneration();
            },
            icon: const Icon(Icons.rocket_launch, size: 18),
            label: const Text('Generate Documents'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryDark,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _startGeneration() async {
    if (_selectedDocs.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select at least one document to generate')),
      );
      return;
    }

    try {
      setState(() {
        _isGenerating = true;
        _progressPercentage = 0;
        _pollErrorCount = 0; // Reset error count
        _currentAgent = 'Starting...';
        _currentDescription = 'Initializing document generation pipeline';
      });

      // Use the selected document language (user can choose different from app language)
      final response = await authService.post(
        '/assessments/${widget.assessmentId}/generate-documents',
        body: {
          'document_types': _selectedDocs.toList(),
          'language': _selectedLanguage,
          'clause_ids': _selectedClauses.toList(),
        },
      );

      if (!mounted) return;

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _generationJobId = data['id']?.toString();
        if (_generationJobId != null) {
          _startPolling();
        } else {
          throw Exception('Invalid response: missing job ID');
        }
      } else {
        throw Exception('Failed to start generation: ${response.statusCode}');
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isGenerating = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Generation failed: $e')),
        );
      }
    }
  }

  void _startPolling() {
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      await _checkProgress();
    });
  }

  Future<void> _checkProgress() async {
    if (_generationJobId == null || !mounted) return;

    try {
      final response = await authService.get('/generation-jobs/$_generationJobId/status');

      if (!mounted) return;

      if (response.statusCode == 200) {
        // Reset error count on success
        _pollErrorCount = 0;

        final data = jsonDecode(response.body);
        setState(() {
          _currentAgent = data['current_agent'] as String?;
          _currentDescription = data['current_agent_description'] as String?;
          _progressPercentage = data['progress_percentage'] as int? ?? 0;
          // Capture progress steps for live display
          if (data['steps'] != null) {
            _progressSteps = List<Map<String, dynamic>>.from(data['steps']);
          }
        });

        if (data['status'] == 'completed' || data['status'] == 'failed') {
          _pollTimer?.cancel();
          if (data['status'] == 'completed') {
            await _loadGeneratedDocuments();
          } else {
            // Show error message
            if (mounted && data['error_message'] != null) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('Generation failed: ${data['error_message']}'),
                  backgroundColor: Colors.red,
                ),
              );
            }
          }
          if (mounted) {
            setState(() => _isGenerating = false);
          }
        }
      } else if (response.statusCode == 401) {
        // Token expired - stop polling and notify user
        _pollTimer?.cancel();
        if (mounted) {
          setState(() => _isGenerating = false);
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Session expired. Please log in again.'),
              backgroundColor: Colors.red,
            ),
          );
        }
      } else {
        // Handle other non-200 status codes
        _pollErrorCount++;
        debugPrint('[DocumentGeneration] Poll error: status ${response.statusCode}, count: $_pollErrorCount');

        if (_pollErrorCount >= _maxPollErrors) {
          _pollTimer?.cancel();
          if (mounted) {
            setState(() => _isGenerating = false);
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Generation status check failed. Please try again.'),
                backgroundColor: Colors.red,
              ),
            );
          }
        }
      }
    } catch (e) {
      _pollErrorCount++;
      debugPrint('[DocumentGeneration] Poll exception: $e, count: $_pollErrorCount');

      // Stop polling after max errors to prevent infinite loop
      if (_pollErrorCount >= _maxPollErrors && mounted) {
        _pollTimer?.cancel();
        setState(() => _isGenerating = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Connection error: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _loadGeneratedDocuments() async {
    if (!mounted) return;

    try {
      final response = await authService.get(
        '/assessments/${widget.assessmentId}/generated',
      );

      if (!mounted) return;

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _generatedDocs = List<Map<String, dynamic>>.from(data['items'] ?? []);
        });
      } else {
        debugPrint('[DocumentGeneration] Failed to load generated docs: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('[DocumentGeneration] Error loading generated docs: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load documents: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // Check if user has access to document generation
    if (!subscriptionService.hasFeature('document_generation')) {
      return Scaffold(
        backgroundColor: AppTheme.bg(context),
        appBar: AppBar(
          backgroundColor: AppTheme.surfaceOf(context),
          elevation: 0,
          leading: IconButton(
            onPressed: () => context.pop(),
            icon: Icon(Icons.arrow_back),
            color: AppTheme.text1(context),
          ),
          title: Text(
            'Generate Documents',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: AppTheme.text1(context),
              fontFamily: 'Inter',
            ),
          ),
          centerTitle: true,
        ),
        body: Center(
          child: PremiumLockedBanner(
            featureName: 'document_generation',
            onUpgrade: () => showDialog(
              context: context,
              builder: (context) => const UpgradeDialog(featureName: 'document_generation'),
            ),
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceOf(context),
        elevation: 0,
        leading: IconButton(
          onPressed: () => context.pop(),
          icon: Icon(Icons.arrow_back),
          color: AppTheme.text1(context),
        ),
        title: Text(
          'Generate Documents',
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: AppTheme.text1(context),
            fontFamily: 'Inter',
          ),
        ),
        centerTitle: true,
      ),
      body: _isLoadingSuggestions
          ? _buildLoadingState()
          : _isGenerating
              ? _buildGenerationProgress()
              : _generatedDocs.isNotEmpty
                  ? _buildGeneratedDocsList()
                  : _buildSuggestionsList(),
    );
  }

  Widget _buildLoadingState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: AppTheme.primaryDark.withOpacity(0.1),
              shape: BoxShape.circle,
            ),
            child: const Center(
              child: SizedBox(
                width: 40,
                height: 40,
                child: CircularProgressIndicator(strokeWidth: 3),
              ),
            ),
          ),
          const SizedBox(height: 24),
          Text(
            _loadingStatus,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: AppTheme.text1(context),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Preparing document generation...',
            style: TextStyle(
              fontSize: 14,
              color: AppTheme.text2(context),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSuggestionsList() {
    if (_suggestions.isEmpty && _lmaClauses.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.description_outlined,
              size: 64,
              color: AppTheme.textH(context),
            ),
            const SizedBox(height: 16),
            Text(
              'No documents suggested',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: AppTheme.text2(context),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Complete the assessment to get document suggestions',
              style: TextStyle(color: AppTheme.textH(context)),
            ),
          ],
        ),
      );
    }

    return Column(
      children: [
        // Scrollable content
        Expanded(
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // God Mode: Vision OCR confidence card
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                  child: PropertyRiskCard(
                    assessmentId: widget.assessmentId,
                  ),
                ),
                const SizedBox(height: 16),

                // Document Suggestions Header
                Container(
                  padding: EdgeInsets.all(16),
                  color: AppTheme.surfaceOf(context),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.description, size: 20, color: AppTheme.primaryDark),
                          const SizedBox(width: 8),
                          Text(
                            'AI Recommended Documents',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.text1(context),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Select the documents you want to generate',
                        style: TextStyle(
                          fontSize: 13,
                          color: AppTheme.text2(context),
                        ),
                      ),
                    ],
                  ),
                ),

                // Document Suggestions List
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Column(
                    children: _suggestions.map((doc) => _buildSuggestionCard(doc)).toList(),
                  ),
                ),

                // Language Selection Section
                Container(
                  padding: EdgeInsets.all(16),
                  color: AppTheme.surfaceOf(context),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.language, size: 20, color: AppTheme.primaryDark),
                          const SizedBox(width: 8),
                          Text(
                            'Document Language',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.text1(context),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        decoration: BoxDecoration(
                          border: Border.all(color: AppTheme.borderOf(context)),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: DropdownButtonHideUnderline(
                          child: DropdownButton<String>(
                            value: _selectedLanguage,
                            isExpanded: true,
                            icon: const Icon(Icons.keyboard_arrow_down),
                            items: _availableLanguages.map((lang) {
                              return DropdownMenuItem<String>(
                                value: lang['code'],
                                child: Text(lang['name']!),
                              );
                            }).toList(),
                            onChanged: (value) {
                              if (value != null) {
                                setState(() => _selectedLanguage = value);
                              }
                            },
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                // Clauses Library Section
                _buildClausesLibrarySection(),

                const SizedBox(height: 80), // Space for bottom button
              ],
            ),
          ),
        ),

        // Generate Button
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.surfaceOf(context),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.05),
                blurRadius: 10,
                offset: const Offset(0, -4),
              ),
            ],
          ),
          child: SafeArea(
            child: SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _selectedDocs.isEmpty ? null : _showGenerationConfirmation,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryDark,
                  disabledBackgroundColor: AppTheme.borderOf(context),
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: Text(
                  _selectedDocs.isEmpty
                      ? 'Select Documents to Generate'
                      : 'Generate ${_selectedDocs.length} Document${_selectedDocs.length > 1 ? 's' : ''} with ${_selectedClauses.length} Clauses',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: _selectedDocs.isEmpty ? AppTheme.textH(context) : Colors.white,
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSuggestionCard(Map<String, dynamic> suggestion) {
    final docType = suggestion['document_type'] as String;
    final isSelected = _selectedDocs.contains(docType);
    final isMandatory = suggestion['mandatory'] == true;
    final confidence = (suggestion['confidence'] as num?)?.toDouble() ?? 0.0;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: isSelected ? AppTheme.primaryDark : AppTheme.borderOf(context),
          width: isSelected ? 2 : 1,
        ),
      ),
      child: InkWell(
        onTap: () {
          setState(() {
            if (isSelected) {
              _selectedDocs.remove(docType);
            } else {
              _selectedDocs.add(docType);
            }
          });
        },
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              // Checkbox
              Container(
                width: 24,
                height: 24,
                decoration: BoxDecoration(
                  color: isSelected ? AppTheme.primaryDark : Colors.transparent,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(
                    color: isSelected ? AppTheme.primaryDark : AppTheme.borderOf(context),
                    width: 2,
                  ),
                ),
                child: isSelected
                    ? const Icon(Icons.check, size: 16, color: Colors.white)
                    : null,
              ),
              const SizedBox(width: 16),

              // Content
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          suggestion['template_name'] as String? ?? docType.replaceAll('_', ' '),
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.text1(context),
                          ),
                        ),
                        if (isMandatory) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: Colors.red.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              'REQUIRED',
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w600,
                                color: Colors.red,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      suggestion['reason'] as String? ?? '',
                      style: TextStyle(
                        fontSize: 13,
                        color: AppTheme.text2(context),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Icon(Icons.psychology_outlined, size: 14, color: AppTheme.textH(context)),
                        const SizedBox(width: 4),
                        Text(
                          'AI Confidence: ${(confidence * 100).toInt()}%',
                          style: TextStyle(
                            fontSize: 12,
                            color: AppTheme.textH(context),
                          ),
                        ),
                        const SizedBox(width: 16),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: AppTheme.borderOf(context),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            'Priority ${suggestion['priority'] ?? 1}',
                            style: TextStyle(
                              fontSize: 11,
                              color: AppTheme.text2(context),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildClausesLibrarySection() {
    return Container(
      margin: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.borderOf(context)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [Colors.orange.shade400, Colors.deepOrange.shade600],
                    ),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.library_books, size: 24, color: Colors.white),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Clauses Library',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.text1(context),
                        ),
                      ),
                      Text(
                        'Insurance clauses with AI recommendations',
                        style: TextStyle(
                          fontSize: 13,
                          color: AppTheme.text2(context),
                        ),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: _selectedClauses.isNotEmpty
                        ? Colors.green.withOpacity(0.1)
                        : Colors.grey.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: _selectedClauses.isNotEmpty
                          ? Colors.green.withOpacity(0.3)
                          : Colors.grey.withOpacity(0.3),
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.check_circle,
                        size: 16,
                        color: _selectedClauses.isNotEmpty ? Colors.green : Colors.grey,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        '${_selectedClauses.length} selected',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: _selectedClauses.isNotEmpty ? Colors.green : Colors.grey,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          const Divider(height: 1),

          // Features row
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                _buildFeatureChip(Icons.auto_awesome, 'AI Guided', Colors.purple),
                const SizedBox(width: 8),
                _buildFeatureChip(Icons.search, 'Full-Text Search', Colors.blue),
                const SizedBox(width: 8),
                _buildFeatureChip(Icons.category, '100+ Categories', Colors.teal),
              ],
            ),
          ),

          // Action button
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _openClausesLibrary,
                icon: const Icon(Icons.library_books, size: 20),
                label: const Text('Browse & Select Clauses'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.orange.shade600,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  elevation: 0,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFeatureChip(IconData icon, String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w500,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  void _openClausesLibrary() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.92,
        maxChildSize: 0.95,
        minChildSize: 0.5,
        builder: (context, scrollController) => Container(
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
          ),
          child: Column(
            children: [
              // Handle
              Container(
                margin: const EdgeInsets.only(top: 12),
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey[300],
                  borderRadius: BorderRadius.circular(2),
                ),
              ),

              // Close button row
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 8, 0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Select Clauses for Document',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.text1(context),
                      ),
                    ),
                    IconButton(
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close),
                    ),
                  ],
                ),
              ),

              // Clause selector widget
              Expanded(
                child: ClauseSelectorWidget(
                  assessmentId: widget.assessmentId,
                  selectedClauseIds: _selectedClauses,
                  onSelectionChanged: (selectedIds) {
                    setState(() {
                      _selectedClauses = Set<String>.from(selectedIds);
                    });
                  },
                ),
              ),

              // Done button
              Container(
                padding: EdgeInsets.fromLTRB(
                  16, 12, 16, 12 + MediaQuery.of(context).padding.bottom,
                ),
                decoration: BoxDecoration(
                  color: Colors.white,
                  border: Border(top: BorderSide(color: AppTheme.borderOf(context))),
                ),
                child: SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: () => Navigator.pop(context),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primaryDark,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: Text(
                      'Done (${_selectedClauses.length} clauses selected)',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildGenerationProgress() {
    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            const SizedBox(height: 20),

            // Header
            Text(
              'Generating Documents',
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: AppTheme.text1(context),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'InstantRisk Engine is generating your documents',
              style: TextStyle(
                fontSize: 14,
                color: AppTheme.text2(context),
              ),
            ),

            const SizedBox(height: 32),

            // Animated progress indicator
            SizedBox(
              width: 220,
              height: 220,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  CircularProgressIndicator(
                    value: _progressPercentage / 100,
                    strokeWidth: 14,
                    backgroundColor: AppTheme.borderOf(context),
                    color: AppTheme.primaryDark,
                  ),
                  Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        '$_progressPercentage%',
                        style: TextStyle(
                          fontSize: 42,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.text1(context),
                        ),
                      ),
                      Text(
                        'Complete',
                        style: TextStyle(
                          fontSize: 16,
                          color: AppTheme.text2(context),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),

            // Current agent activity
            if (_currentAgent != null) ...[
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.primaryDark.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.primaryDark.withOpacity(0.3)),
                ),
                child: Row(
                  children: [
                    _buildAgentIcon(_currentAgent!),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            _currentAgent!,
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.text1(context),
                            ),
                          ),
                          if (_currentDescription != null) ...[
                            const SizedBox(height: 4),
                            Text(
                              _currentDescription!,
                              style: TextStyle(
                                fontSize: 13,
                                color: AppTheme.text2(context),
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                    const SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
            ],

            // Agent pipeline visual
            _buildAgentPipeline(),

            const SizedBox(height: 24),

            // Live activity log
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.grey.shade100,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.terminal, size: 16, color: AppTheme.text2(context)),
                      const SizedBox(width: 8),
                      Text(
                        'Live Activity',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text2(context),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  if (_progressSteps.isEmpty)
                    Text(
                      _currentDescription ?? 'Initializing...',
                      style: TextStyle(
                        fontSize: 12,
                        fontFamily: 'monospace',
                        color: AppTheme.text2(context),
                      ),
                    )
                  else
                    ..._progressSteps.take(5).map((step) => Padding(
                          padding: const EdgeInsets.only(bottom: 6),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(
                                step['status'] == 'completed'
                                    ? Icons.check_circle
                                    : step['status'] == 'running'
                                        ? Icons.sync
                                        : Icons.circle_outlined,
                                size: 14,
                                color: step['status'] == 'completed'
                                    ? Colors.green
                                    : step['status'] == 'running'
                                        ? AppTheme.primaryDark
                                        : AppTheme.textH(context),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  step['description'] ?? step['agent'] ?? '',
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontFamily: 'monospace',
                                    color: step['status'] == 'running'
                                        ? AppTheme.text1(context)
                                        : AppTheme.text2(context),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        )),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGenerationProgressOld() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Animated progress indicator
            SizedBox(
              width: 120,
              height: 120,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  CircularProgressIndicator(
                    value: _progressPercentage / 100,
                    strokeWidth: 8,
                    backgroundColor: AppTheme.borderOf(context),
                    color: AppTheme.primaryDark,
                  ),
                  Text(
                    '$_progressPercentage%',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.text1(context),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),

            // Current agent
            if (_currentAgent != null) ...[
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _buildAgentIcon(_currentAgent!),
                  const SizedBox(width: 12),
                  Text(
                    _currentAgent!,
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.text1(context),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
            ],

            if (_currentDescription != null)
              Text(
                _currentDescription!,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 14,
                  color: AppTheme.text2(context),
                ),
              ),

            const SizedBox(height: 32),

            // Agent pipeline
            _buildAgentPipeline(),
          ],
        ),
      ),
    );
  }

  Widget _buildAgentIcon(String agentName) {
    IconData icon;
    Color color;

    // Map 19 agent names to icons and colors by phase
    switch (agentName) {
      // Phase 1: Research
      case 'RiskResearcher':
        icon = Icons.search;
        color = AppTheme.phaseResearch;
        break;
      case 'ClauseExtractor':
        icon = Icons.content_paste_search;
        color = AppTheme.phaseResearch;
        break;
      case 'GapAnalyzer':
        icon = Icons.find_replace;
        color = AppTheme.phaseResearch;
        break;
      // Phase 2: Structure
      case 'ClauseManager':
        icon = Icons.library_books;
        color = AppTheme.phaseStructure;
        break;
      case 'StructurePlanner':
        icon = Icons.account_tree;
        color = AppTheme.phaseStructure;
        break;
      case 'LloydFormatter':
        icon = Icons.format_align_left;
        color = AppTheme.phaseStructure;
        break;
      // Phase 3: Compose
      case 'SectionDrafter':
        icon = Icons.edit_document;
        color = AppTheme.phaseCompose;
        break;
      case 'ConsistencyChecker':
        icon = Icons.fact_check;
        color = AppTheme.phaseCompose;
        break;
      case 'ToneUnifier':
        icon = Icons.record_voice_over;
        color = AppTheme.phaseCompose;
        break;
      // Phase 4: Validate
      case 'RiskChallenger':
        icon = Icons.gavel;
        color = AppTheme.phaseValidate;
        break;
      case 'ClauseVerifier':
        icon = Icons.verified_user;
        color = AppTheme.phaseValidate;
        break;
      case 'ComplianceReviewer':
        icon = Icons.policy;
        color = AppTheme.phaseValidate;
        break;
      // Phase 5: Refine
      case 'HouseStyleAgent':
        icon = Icons.style;
        color = AppTheme.phaseRefine;
        break;
      case 'LanguageVarier':
        icon = Icons.text_rotation_none;
        color = AppTheme.phaseRefine;
        break;
      case 'ProofReader':
        icon = Icons.spellcheck;
        color = AppTheme.phaseRefine;
        break;
      case 'ClauseCompiler':
        icon = Icons.integration_instructions;
        color = AppTheme.phaseRefine;
        break;
      // Phase 6: Export
      case 'ScheduleBuilder':
        icon = Icons.table_chart;
        color = AppTheme.phaseExport;
        break;
      case 'PDFExporter':
        icon = Icons.picture_as_pdf;
        color = AppTheme.phaseExport;
        break;
      case 'QualityGate':
        icon = Icons.check_circle_outline;
        color = AppTheme.phaseExport;
        break;
      default:
        icon = Icons.smart_toy;
        color = AppTheme.primaryDark;
    }

    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Icon(icon, color: color, size: 20),
    );
  }

  Widget _buildAgentPipeline() {
    // Show 6 phases instead of individual agents for compact display
    final phases = [
      {'name': 'Research', 'icon': Icons.search, 'color': AppTheme.phaseResearch, 'threshold': 16},
      {'name': 'Structure', 'icon': Icons.account_tree, 'color': AppTheme.phaseStructure, 'threshold': 32},
      {'name': 'Compose', 'icon': Icons.edit_document, 'color': AppTheme.phaseCompose, 'threshold': 48},
      {'name': 'Validate', 'icon': Icons.verified, 'color': AppTheme.phaseValidate, 'threshold': 64},
      {'name': 'Refine', 'icon': Icons.auto_fix_high, 'color': AppTheme.phaseRefine, 'threshold': 84},
      {'name': 'Export', 'icon': Icons.output, 'color': AppTheme.phaseExport, 'threshold': 100},
    ];

    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: phases.asMap().entries.map((entry) {
        final index = entry.key;
        final phase = entry.value;
        final threshold = phase['threshold'] as int;
        final prevThreshold = index > 0 ? (phases[index - 1]['threshold'] as int) : 0;
        final isActive = _progressPercentage >= prevThreshold;
        final isCurrent = _progressPercentage >= prevThreshold && _progressPercentage < threshold;
        final phaseColor = phase['color'] as Color;

        return Row(
          children: [
            Column(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: isActive
                        ? phaseColor.withOpacity(isCurrent ? 1 : 0.2)
                        : AppTheme.borderOf(context),
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: Icon(
                    phase['icon'] as IconData,
                    color: isActive ? (isCurrent ? Colors.white : phaseColor) : AppTheme.textH(context),
                    size: 18,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  phase['name'] as String,
                  style: TextStyle(
                    fontSize: 9,
                    fontWeight: isCurrent ? FontWeight.w700 : FontWeight.w400,
                    color: isActive ? AppTheme.text1(context) : AppTheme.textH(context),
                  ),
                ),
              ],
            ),
            if (index < phases.length - 1)
              Container(
                width: 16,
                height: 2,
                color: isActive && !isCurrent ? phaseColor : AppTheme.borderOf(context),
                margin: const EdgeInsets.only(bottom: 16),
              ),
          ],
        );
      }).toList(),
    );
  }

  Widget _buildGeneratedDocsList() {
    return Column(
      children: [
        // Success header
        Container(
          padding: const EdgeInsets.all(16),
          color: Colors.green.withOpacity(0.1),
          child: Row(
            children: [
              const Icon(Icons.check_circle, color: Colors.green),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Documents Generated Successfully',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: Colors.green,
                      ),
                    ),
                    Text(
                      '${_generatedDocs.length} document${_generatedDocs.length > 1 ? 's' : ''} ready for review',
                      style: TextStyle(
                        fontSize: 13,
                        color: AppTheme.text2(context),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),

        // Documents list
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: _generatedDocs.length,
            itemBuilder: (context, index) => _buildGeneratedDocCard(_generatedDocs[index]),
          ),
        ),

        // Actions
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.surfaceOf(context),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.05),
                blurRadius: 10,
                offset: const Offset(0, -4),
              ),
            ],
          ),
          child: SafeArea(
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      setState(() {
                        _generatedDocs.clear();
                        _selectedDocs.clear();
                      });
                      _loadSuggestions();
                    },
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      side: BorderSide(color: AppTheme.primaryDark),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: const Text('Generate More'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton(
                    onPressed: () => context.pop(),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primaryDark,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: const Text(
                      'Done',
                      style: TextStyle(color: Colors.white),
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

  Widget _buildGeneratedDocCard(Map<String, dynamic> doc) {
    final status = doc['status'] as String? ?? 'draft';
    final placeholders = doc['placeholders_remaining'] as int? ?? 0;
    final confidence = (doc['ai_confidence'] as num?)?.toDouble() ?? 0.0;

    Color statusColor;
    switch (status) {
      case 'finalized':
        statusColor = Colors.green;
        break;
      case 'approved':
        statusColor = Colors.blue;
        break;
      case 'review_required':
        statusColor = Colors.orange;
        break;
      default:
        statusColor = AppTheme.text2(context);
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: AppTheme.borderOf(context)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: statusColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(
                    Icons.description,
                    color: statusColor,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        doc['title'] as String? ?? 'Untitled',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text1(context),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: statusColor.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              status.toUpperCase().replaceAll('_', ' '),
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w600,
                                color: statusColor,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            '${(confidence * 100).toInt()}% confidence',
                            style: TextStyle(
                              fontSize: 12,
                              color: AppTheme.textH(context),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),

            if (placeholders > 0) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.orange.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.warning_amber, size: 16, color: Colors.orange),
                    const SizedBox(width: 8),
                    Text(
                      '$placeholders placeholder${placeholders > 1 ? 's' : ''} need attention',
                      style: const TextStyle(
                        fontSize: 12,
                        color: Colors.orange,
                      ),
                    ),
                  ],
                ),
              ),
            ],

            const SizedBox(height: 12),

            // Actions
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton.icon(
                  onPressed: () {
                    final docId = doc['id']?.toString();
                    if (docId != null) {
                      context.push('/documents/preview/$docId', extra: {
                        'assessmentId': widget.assessmentId,
                      });
                    }
                  },
                  icon: const Icon(Icons.visibility_outlined, size: 18),
                  label: const Text('View'),
                ),
                const SizedBox(width: 8),
                TextButton.icon(
                  onPressed: () {
                    final docId = doc['id']?.toString();
                    if (docId != null) {
                      context.push('/documents/edit/$docId');
                    }
                  },
                  icon: const Icon(Icons.edit_outlined, size: 18),
                  label: const Text('Edit'),
                  style: TextButton.styleFrom(
                    foregroundColor: AppTheme.primaryDark,
                  ),
                ),
                const SizedBox(width: 8),
                if (status != 'finalized')
                  TextButton.icon(
                    onPressed: () async {
                      final docId = doc['id']?.toString();
                      if (docId == null) return;
                      try {
                        final response = await authService.post(
                          '/generated-documents/$docId/finalize',
                        );
                        if (response.statusCode == 200 && mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Document finalized successfully')),
                          );
                          _loadGeneratedDocuments();
                        }
                      } catch (e) {
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Failed to finalize: $e')),
                          );
                        }
                      }
                    },
                    icon: const Icon(Icons.check_circle_outline, size: 18),
                    label: const Text('Finalize'),
                    style: TextButton.styleFrom(
                      foregroundColor: Colors.green,
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
