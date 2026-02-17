import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Document Configuration Screen - V3 Document Generator
/// Allows users to configure clauses, sections, and details for document generation
class DocumentConfigureScreen extends StatefulWidget {
  final String documentType;
  final String documentTypeName;
  final String lineOfBusiness;
  final String lineOfBusinessName;

  const DocumentConfigureScreen({
    super.key,
    required this.documentType,
    required this.documentTypeName,
    required this.lineOfBusiness,
    required this.lineOfBusinessName,
  });

  @override
  State<DocumentConfigureScreen> createState() => _DocumentConfigureScreenState();
}

class _DocumentConfigureScreenState extends State<DocumentConfigureScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool _isLoading = true;
  bool _isGenerating = false;
  int _generationProgress = 0;
  String? _currentStep;
  List<Map<String, dynamic>> _generationSteps = [];

  // Dynamic policy sections loaded from API
  Map<String, bool> _coreSections = {};
  Map<String, bool> _exclusions = {};
  Map<String, bool> _conditions = {};

  // Section metadata (name, description, required)
  Map<String, Map<String, dynamic>> _sectionMetadata = {};
  bool _sectionsLoaded = false;

  // LMA Clauses
  List<Map<String, dynamic>> _lmaClauses = [];
  Set<String> _selectedLmaClauses = {};

  // Policy details
  final _insuredNameController = TextEditingController();
  final _insuredAddressController = TextEditingController();
  final _businessActivityController = TextEditingController();
  final _aggregateLimitController = TextEditingController(text: '5,000,000');
  final _perClaimLimitController = TextEditingController(text: '5,000,000');
  final _retentionController = TextEditingController(text: '25,000');
  final _premiumController = TextEditingController();

  // Pricing benchmark
  Map<String, dynamic>? _pricingBenchmark;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadTemplateData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _insuredNameController.dispose();
    _insuredAddressController.dispose();
    _businessActivityController.dispose();
    _aggregateLimitController.dispose();
    _perClaimLimitController.dispose();
    _retentionController.dispose();
    _premiumController.dispose();
    super.dispose();
  }

  Future<void> _loadTemplateData() async {
    try {
      setState(() => _isLoading = true);

      // Load dynamic sections for this line of business
      await _loadDynamicSections();

      // Load LMA clauses for this line of business
      final clausesResponse = await authService.get(
        '/templates/lma/all?line_of_business=${widget.lineOfBusiness}',
      );

      if (clausesResponse.statusCode == 200) {
        final data = jsonDecode(clausesResponse.body);
        _lmaClauses = List<Map<String, dynamic>>.from(data['items'] ?? []);

        // Pre-select recommended clauses
        for (final clause in _lmaClauses) {
          if (clause['mandatory'] == true || clause['recommended'] == true) {
            final clauseId = clause['id']?.toString();
            if (clauseId != null && clauseId.isNotEmpty) {
              _selectedLmaClauses.add(clauseId);
            }
          }
        }
      }

      // Load pricing benchmark
      try {
        final benchmarkResponse = await authService.post(
          '/pricing/technical',
          body: {
            'line_of_business': widget.lineOfBusiness,
            'limit': 5000000,
          },
        );
        if (benchmarkResponse.statusCode == 200) {
          _pricingBenchmark = jsonDecode(benchmarkResponse.body);
        }
      } catch (_) {
        // Pricing benchmark is optional
      }

      setState(() => _isLoading = false);
    } catch (e) {
      setState(() => _isLoading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load template data: $e')),
        );
      }
    }
  }

  Future<void> _loadDynamicSections() async {
    try {
      final response = await authService.get(
        '/templates-v3/sections?line_of_business=${widget.lineOfBusiness}&document_type=${widget.documentType}',
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final categories = List<Map<String, dynamic>>.from(data['categories'] ?? []);

        // Reset sections
        _coreSections = {};
        _exclusions = {};
        _conditions = {};
        _sectionMetadata = {};

        for (final category in categories) {
          final categoryId = category['id'].toString();
          final sections = List<Map<String, dynamic>>.from(category['sections'] ?? []);

          for (final section in sections) {
            final sectionId = section['id'].toString();
            final defaultEnabled = section['default_enabled'] ?? true;
            final required = section['required'] ?? false;

            // Store metadata
            _sectionMetadata[sectionId] = {
              'name': section['name'] ?? sectionId,
              'description': section['description'] ?? '',
              'required': required,
              'category': categoryId,
            };

            // Add to appropriate map based on category
            switch (categoryId) {
              case 'core':
                _coreSections[sectionId] = defaultEnabled;
                break;
              case 'exclusions':
                _exclusions[sectionId] = defaultEnabled;
                break;
              case 'conditions':
                _conditions[sectionId] = defaultEnabled;
                break;
            }
          }
        }

        _sectionsLoaded = true;
      }
    } catch (e) {
      debugPrint('Error loading dynamic sections: $e');
      // Fall back to default sections if API fails
      _loadDefaultSections();
    }
  }

  void _loadDefaultSections() {
    // Fallback default sections
    _coreSections = {
      'insuring_agreement': true,
      'definitions': true,
      'coverage_a': true,
      'coverage_b': true,
      'coverage_c': false,
      'schedule': true,
    };

    _exclusions = {
      'war_terrorism': true,
      'prior_acts': true,
      'bodily_injury': true,
      'infrastructure': true,
      'contractual_liability': false,
      'unencrypted_devices': false,
    };

    _conditions = {
      'notice_of_claim': true,
      'cooperation': true,
      'subrogation': true,
      'other_insurance': true,
      'cancellation': true,
      'jurisdiction': true,
    };

    _sectionMetadata = {
      'insuring_agreement': {'name': 'Insuring Agreement', 'description': 'Core coverage grant', 'required': true},
      'definitions': {'name': 'Definitions', 'description': 'Key terms and definitions', 'required': true},
      'coverage_a': {'name': 'Coverage A', 'description': 'Primary coverage section', 'required': false},
      'coverage_b': {'name': 'Coverage B', 'description': 'Secondary coverage section', 'required': false},
      'coverage_c': {'name': 'Coverage C', 'description': 'Additional coverage section', 'required': false},
      'schedule': {'name': 'Schedule', 'description': 'Policy schedule', 'required': true},
      'war_terrorism': {'name': 'War & Terrorism', 'description': 'War exclusion', 'required': true},
      'prior_acts': {'name': 'Prior Acts', 'description': 'Prior acts exclusion', 'required': false},
      'bodily_injury': {'name': 'Bodily Injury', 'description': 'Bodily injury exclusion', 'required': false},
      'infrastructure': {'name': 'Infrastructure', 'description': 'Infrastructure exclusion', 'required': false},
      'contractual_liability': {'name': 'Contractual Liability', 'description': 'Contractual liability exclusion', 'required': false},
      'unencrypted_devices': {'name': 'Unencrypted Devices', 'description': 'Unencrypted devices exclusion', 'required': false},
      'notice_of_claim': {'name': 'Notice of Claim', 'description': 'Claim notification requirements', 'required': true},
      'cooperation': {'name': 'Cooperation', 'description': 'Duty to cooperate', 'required': true},
      'subrogation': {'name': 'Subrogation', 'description': 'Subrogation rights', 'required': true},
      'other_insurance': {'name': 'Other Insurance', 'description': 'Coordination with other policies', 'required': true},
      'cancellation': {'name': 'Cancellation', 'description': 'Cancellation terms', 'required': true},
      'jurisdiction': {'name': 'Jurisdiction', 'description': 'Jurisdiction and venue', 'required': false},
    };

    _sectionsLoaded = true;
  }

  Future<void> _startGeneration() async {
    if (_insuredNameController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter the insured name')),
      );
      _tabController.animateTo(2); // Go to details tab
      return;
    }

    setState(() {
      _isGenerating = true;
      _generationProgress = 0;
      _currentStep = 'Initializing...';
      _generationSteps = [];
    });

    try {
      // Start document generation
      final response = await authService.post(
        '/documents/generate-v3',
        body: {
          'document_type': widget.documentType,
          'line_of_business': widget.lineOfBusiness,
          'core_sections': _coreSections.entries
              .where((e) => e.value)
              .map((e) => e.key)
              .toList(),
          'exclusions': _exclusions.entries
              .where((e) => e.value)
              .map((e) => e.key)
              .toList(),
          'conditions': _conditions.entries
              .where((e) => e.value)
              .map((e) => e.key)
              .toList(),
          'lma_clauses': _selectedLmaClauses.toList(),
          'policy_details': {
            'insured_name': _insuredNameController.text,
            'insured_address': _insuredAddressController.text,
            'business_activity': _businessActivityController.text,
            'aggregate_limit': _aggregateLimitController.text,
            'per_claim_limit': _perClaimLimitController.text,
            'retention': _retentionController.text,
            'premium': _premiumController.text,
          },
        },
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final jobId = data['job_id'] as String;

        // Poll for progress
        await _pollGenerationProgress(jobId);
      } else {
        throw Exception('Failed to start generation');
      }
    } catch (e) {
      setState(() => _isGenerating = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Generation failed: $e')),
        );
      }
    }
  }

  Future<void> _pollGenerationProgress(String jobId) async {
    while (_isGenerating && mounted) {
      try {
        final response = await authService.get('/documents/jobs/$jobId/status');

        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);

          setState(() {
            _generationProgress = data['progress'] as int? ?? 0;
            _currentStep = data['current_step'] as String?;
            if (data['steps'] != null) {
              _generationSteps = List<Map<String, dynamic>>.from(data['steps']);
            }
          });

          if (data['status'] == 'completed') {
            setState(() => _isGenerating = false);
            // Navigate to document preview
            if (mounted) {
              final documentId = data['document_id'] as String?;
              if (documentId != null) {
                context.push('/documents/preview/$documentId');
              } else {
                context.go('/documents');
              }
            }
            return;
          } else if (data['status'] == 'failed') {
            throw Exception(data['error'] ?? 'Generation failed');
          }
        }

        await Future.delayed(const Duration(seconds: 2));
      } catch (e) {
        setState(() => _isGenerating = false);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error: $e')),
          );
        }
        return;
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isGenerating) {
      return _buildGenerationProgress();
    }

    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceOf(context),
        elevation: 0,
        leading: IconButton(
          onPressed: () => context.pop(),
          icon: Icon(Icons.arrow_back_ios),
          color: AppTheme.text1(context),
        ),
        title: Column(
          children: [
            Text(
              widget.lineOfBusinessName,
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppTheme.text1(context),
                fontFamily: 'Inter',
              ),
            ),
            Text(
              widget.documentTypeName,
              style: TextStyle(
                fontSize: 12,
                color: AppTheme.text2(context),
              ),
            ),
          ],
        ),
        centerTitle: true,
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppTheme.primaryDark,
          unselectedLabelColor: AppTheme.text2(context),
          indicatorColor: AppTheme.primaryDark,
          tabs: const [
            Tab(text: 'Sections'),
            Tab(text: 'LMA Clauses'),
            Tab(text: 'Details'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                Expanded(
                  child: TabBarView(
                    controller: _tabController,
                    children: [
                      _buildSectionsTab(),
                      _buildLmaClausesTab(),
                      _buildDetailsTab(),
                    ],
                  ),
                ),
                _buildBottomBar(),
              ],
            ),
    );
  }

  Widget _buildSectionsTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Line of business indicator
          Container(
            padding: const EdgeInsets.all(12),
            margin: const EdgeInsets.only(bottom: 16),
            decoration: BoxDecoration(
              color: AppTheme.primaryDark.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppTheme.primaryDark.withOpacity(0.2)),
            ),
            child: Row(
              children: [
                Icon(Icons.auto_awesome, color: AppTheme.primaryDark, size: 18),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Sections configured for ${widget.lineOfBusinessName} ${widget.documentTypeName}',
                    style: TextStyle(
                      fontSize: 13,
                      color: AppTheme.primaryDark,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Core Sections
          _buildSectionHeader('Core Sections', 'Essential policy sections'),
          const SizedBox(height: 12),
          _buildDynamicCheckboxGroup(_coreSections, 'core'),

          const SizedBox(height: 24),

          // Exclusions
          _buildSectionHeader('Exclusions', 'Risks and situations not covered'),
          const SizedBox(height: 12),
          _buildDynamicCheckboxGroup(_exclusions, 'exclusions'),

          const SizedBox(height: 24),

          // Conditions
          _buildSectionHeader('Conditions', 'Policy conditions and requirements'),
          const SizedBox(height: 12),
          _buildDynamicCheckboxGroup(_conditions, 'conditions'),

          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title, String subtitle) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.text1(context),
            fontFamily: 'Inter',
          ),
        ),
        Text(
          subtitle,
          style: TextStyle(
            fontSize: 13,
            color: AppTheme.text2(context),
          ),
        ),
      ],
    );
  }

  Widget _buildCheckboxGroup(
    Map<String, bool> items,
    Map<String, String> labels,
  ) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Column(
        children: items.entries.map((entry) {
          final isLast = entry.key == items.keys.last;
          return Column(
            children: [
              CheckboxListTile(
                value: entry.value,
                onChanged: (value) {
                  setState(() {
                    items[entry.key] = value ?? false;
                  });
                },
                title: Text(
                  labels[entry.key] ?? entry.key,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                activeColor: AppTheme.primaryDark,
                controlAffinity: ListTileControlAffinity.leading,
                dense: true,
              ),
              if (!isLast)
                const Divider(height: 1, indent: 56),
            ],
          );
        }).toList(),
      ),
    );
  }

  Widget _buildDynamicCheckboxGroup(Map<String, bool> items, String category) {
    if (items.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.surfaceOf(context),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.borderOf(context)),
        ),
        child: Center(
          child: Text(
            'Loading sections...',
            style: TextStyle(color: AppTheme.text2(context)),
          ),
        ),
      );
    }

    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Column(
        children: items.entries.map((entry) {
          final isLast = entry.key == items.keys.last;
          final metadata = _sectionMetadata[entry.key] ?? {};
          final name = metadata['name'] ?? entry.key.replaceAll('_', ' ').split(' ').map((w) => w.isNotEmpty ? '${w[0].toUpperCase()}${w.substring(1)}' : '').join(' ');
          final description = metadata['description'] ?? '';
          final isRequired = metadata['required'] ?? false;

          return Column(
            children: [
              CheckboxListTile(
                value: entry.value,
                onChanged: isRequired
                    ? null // Required sections cannot be unchecked
                    : (value) {
                        setState(() {
                          items[entry.key] = value ?? false;
                        });
                      },
                title: Row(
                  children: [
                    Expanded(
                      child: Text(
                        name,
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                    if (isRequired)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.red.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text(
                          'REQUIRED',
                          style: TextStyle(
                            fontSize: 9,
                            fontWeight: FontWeight.w600,
                            color: Colors.red,
                          ),
                        ),
                      ),
                  ],
                ),
                subtitle: description.isNotEmpty
                    ? Text(
                        description,
                        style: TextStyle(
                          fontSize: 12,
                          color: AppTheme.textH(context),
                        ),
                      )
                    : null,
                activeColor: AppTheme.primaryDark,
                controlAffinity: ListTileControlAffinity.leading,
              ),
              if (!isLast)
                const Divider(height: 1, indent: 56),
            ],
          );
        }).toList(),
      ),
    );
  }

  Widget _buildLmaClausesTab() {
    if (_lmaClauses.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.gavel_outlined,
              size: 64,
              color: AppTheme.textH(context).withOpacity(0.5),
            ),
            const SizedBox(height: 16),
            Text(
              'No LMA Clauses Available',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: AppTheme.text2(context),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'LMA clauses for ${widget.lineOfBusinessName} will be added automatically',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                color: AppTheme.textH(context),
              ),
            ),
          ],
        ),
      );
    }

    // Group clauses by category
    final groupedClauses = <String, List<Map<String, dynamic>>>{};
    for (final clause in _lmaClauses) {
      final category = clause['category'] as String? ?? 'general';
      groupedClauses.putIfAbsent(category, () => []).add(clause);
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header with count
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildSectionHeader(
                "Lloyd's Market Clauses",
                'Select applicable LMA clauses',
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.orange.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Text(
                  '${_selectedLmaClauses.length} selected',
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: Colors.orange,
                  ),
                ),
              ),
            ],
          ),

          const SizedBox(height: 16),

          // Clause groups
          ...groupedClauses.entries.map((entry) {
            final categoryName = _getCategoryName(entry.key);
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.only(bottom: 8, top: 8),
                  child: Text(
                    categoryName,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.text2(context),
                    ),
                  ),
                ),
                ...entry.value.map((clause) => _buildClauseCard(clause)),
              ],
            );
          }),

          const SizedBox(height: 32),
        ],
      ),
    );
  }

  String _getCategoryName(String category) {
    const names = {
      'general': 'General/Core Clauses',
      'marine': 'Marine Clauses',
      'property': 'Property Clauses',
      'cyber': 'Cyber & Technology',
      'professional_lines': 'Professional Lines',
      'casualty': 'Casualty/Liability',
      'aviation': 'Aviation Clauses',
      'energy': 'Energy Clauses',
      'war_terrorism': 'War & Terrorism',
      'sanctions': 'Sanctions & Compliance',
    };
    return names[category] ?? category.replaceAll('_', ' ').toUpperCase();
  }

  Widget _buildClauseCard(Map<String, dynamic> clause) {
    final clauseId = clause['id']?.toString() ?? '';
    final isSelected = _selectedLmaClauses.contains(clauseId);
    final isMandatory = clause['mandatory'] == true;

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(
          color: isSelected ? Colors.orange : AppTheme.borderOf(context),
          width: isSelected ? 2 : 1,
        ),
      ),
      child: InkWell(
        onTap: () {
          if (!isMandatory) {
            setState(() {
              if (isSelected) {
                _selectedLmaClauses.remove(clauseId);
              } else {
                _selectedLmaClauses.add(clauseId);
              }
            });
          }
        },
        borderRadius: BorderRadius.circular(10),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              // Checkbox
              Container(
                width: 22,
                height: 22,
                decoration: BoxDecoration(
                  color: isSelected ? Colors.orange : Colors.transparent,
                  borderRadius: BorderRadius.circular(5),
                  border: Border.all(
                    color: isSelected ? Colors.orange : AppTheme.borderOf(context),
                    width: 2,
                  ),
                ),
                child: isSelected
                    ? const Icon(Icons.check, size: 14, color: Colors.white)
                    : null,
              ),
              const SizedBox(width: 12),

              // Content
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.grey.shade200,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            clauseId,
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.text2(context),
                              fontFamily: 'monospace',
                            ),
                          ),
                        ),
                        if (isMandatory) ...[
                          const SizedBox(width: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 4,
                              vertical: 1,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.red.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              'REQUIRED',
                              style: TextStyle(
                                fontSize: 8,
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
                      clause['name'] as String? ?? '',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w500,
                        color: AppTheme.text1(context),
                      ),
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

  Widget _buildDetailsTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Insured Information
          _buildSectionHeader('Insured Information', 'Enter policyholder details'),
          const SizedBox(height: 16),

          _buildTextField(
            controller: _insuredNameController,
            label: 'Named Insured *',
            hint: 'e.g., Acme Technology Corp',
          ),
          const SizedBox(height: 12),
          _buildTextField(
            controller: _insuredAddressController,
            label: 'Address',
            hint: 'e.g., 123 Tech Park, London EC2A 1NT',
          ),
          const SizedBox(height: 12),
          _buildTextField(
            controller: _businessActivityController,
            label: 'Business Activity',
            hint: 'e.g., Cloud Software Provider',
          ),

          const SizedBox(height: 24),

          // Coverage Limits
          _buildSectionHeader('Coverage Limits', 'Set policy limits'),
          const SizedBox(height: 16),

          Row(
            children: [
              Expanded(
                child: _buildTextField(
                  controller: _aggregateLimitController,
                  label: 'Aggregate Limit',
                  prefix: '\u00A3',
                  keyboardType: TextInputType.number,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildTextField(
                  controller: _perClaimLimitController,
                  label: 'Per Claim Limit',
                  prefix: '\u00A3',
                  keyboardType: TextInputType.number,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildTextField(
            controller: _retentionController,
            label: 'Retention/Deductible',
            prefix: '\u00A3',
            keyboardType: TextInputType.number,
          ),

          const SizedBox(height: 24),

          // Premium
          _buildSectionHeader('Premium', 'Enter premium amount'),
          const SizedBox(height: 16),

          _buildTextField(
            controller: _premiumController,
            label: 'Annual Premium',
            prefix: '\u00A3',
            keyboardType: TextInputType.number,
          ),

          // AI Benchmark
          if (_pricingBenchmark != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.info.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.info.withOpacity(0.3)),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.psychology,
                    color: AppTheme.info,
                    size: 24,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'AI Pricing Benchmark',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.text1(context),
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '\u00A3${_pricingBenchmark!['min_premium'] ?? 42000} - \u00A3${_pricingBenchmark!['max_premium'] ?? 55000}',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.info,
                          ),
                        ),
                        Text(
                          'Based on similar ${widget.lineOfBusinessName} risks',
                          style: TextStyle(
                            fontSize: 11,
                            color: AppTheme.text2(context),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],

          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    String? hint,
    String? prefix,
    TextInputType? keyboardType,
  }) {
    return TextField(
      controller: controller,
      keyboardType: keyboardType,
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixText: prefix,
        filled: true,
        fillColor: AppTheme.surfaceOf(context),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: AppTheme.borderOf(context)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: AppTheme.borderOf(context)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: AppTheme.primaryDark, width: 2),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
    );
  }

  Widget _buildBottomBar() {
    final selectedSectionsCount = _coreSections.values.where((v) => v).length +
        _exclusions.values.where((v) => v).length +
        _conditions.values.where((v) => v).length;

    return Container(
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
            // Summary
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    '$selectedSectionsCount sections',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.text1(context),
                    ),
                  ),
                  Text(
                    '${_selectedLmaClauses.length} LMA clauses',
                    style: TextStyle(
                      fontSize: 12,
                      color: AppTheme.text2(context),
                    ),
                  ),
                ],
              ),
            ),

            // Generate Button
            ElevatedButton.icon(
              onPressed: _startGeneration,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryDark,
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              icon: const Icon(Icons.auto_awesome, color: Colors.white, size: 20),
              label: const Text(
                'Generate Document',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGenerationProgress() {
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              const Spacer(),

              // Header
              const Icon(
                Icons.auto_awesome,
                size: 48,
                color: AppTheme.primaryDark,
              ),
              const SizedBox(height: 24),
              Text(
                'Generating Your Document',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.text1(context),
                  fontFamily: 'Inter',
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'InstantRisk Engine is generating your ${widget.lineOfBusinessName} ${widget.documentTypeName.toLowerCase()}',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 14,
                  color: AppTheme.text2(context),
                ),
              ),

              const SizedBox(height: 48),

              // Circular progress
              SizedBox(
                width: 160,
                height: 160,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    SizedBox(
                      width: 160,
                      height: 160,
                      child: CircularProgressIndicator(
                        value: _generationProgress / 100,
                        strokeWidth: 12,
                        backgroundColor: AppTheme.borderOf(context),
                        color: AppTheme.primaryDark,
                      ),
                    ),
                    Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          '$_generationProgress%',
                          style: TextStyle(
                            fontSize: 36,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.text1(context),
                          ),
                        ),
                        Text(
                          'Complete',
                          style: TextStyle(
                            fontSize: 14,
                            color: AppTheme.text2(context),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 32),

              // Current step
              if (_currentStep != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryDark.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: AppTheme.primaryDark,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Text(
                        _currentStep!,
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                          color: AppTheme.primaryDark,
                        ),
                      ),
                    ],
                  ),
                ),

              const SizedBox(height: 32),

              // Progress steps
              if (_generationSteps.isNotEmpty)
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceOf(context),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.borderOf(context)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: _generationSteps.map((step) {
                      final status = step['status'] as String? ?? 'pending';
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 6),
                        child: Row(
                          children: [
                            Icon(
                              status == 'completed'
                                  ? Icons.check_circle
                                  : status == 'running'
                                      ? Icons.sync
                                      : Icons.circle_outlined,
                              size: 18,
                              color: status == 'completed'
                                  ? AppTheme.success
                                  : status == 'running'
                                      ? AppTheme.primaryDark
                                      : AppTheme.textH(context),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                step['name'] as String? ?? '',
                                style: TextStyle(
                                  fontSize: 13,
                                  color: status == 'running'
                                      ? AppTheme.text1(context)
                                      : AppTheme.text2(context),
                                  fontWeight: status == 'running'
                                      ? FontWeight.w600
                                      : FontWeight.w400,
                                ),
                              ),
                            ),
                          ],
                        ),
                      );
                    }).toList(),
                  ),
                ),

              const Spacer(),

              // AI info
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.info.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.psychology,
                      color: AppTheme.info,
                      size: 24,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'AI is using DocumentGen model trained on 31,610 insurance clauses to ensure accuracy and compliance',
                        style: TextStyle(
                          fontSize: 12,
                          color: AppTheme.info,
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
    );
  }
}
