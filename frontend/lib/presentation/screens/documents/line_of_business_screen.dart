import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Line of Business Selection Screen - V3 Document Generator
/// Allows users to select the insurance line of business for document generation
class LineOfBusinessScreen extends StatefulWidget {
  final String documentType;
  final String documentTypeName;

  const LineOfBusinessScreen({
    super.key,
    required this.documentType,
    required this.documentTypeName,
  });

  @override
  State<LineOfBusinessScreen> createState() => _LineOfBusinessScreenState();
}

class _LineOfBusinessScreenState extends State<LineOfBusinessScreen> {
  String? _selectedLob;

  // Define lines of business with metadata
  static final List<Map<String, dynamic>> _linesOfBusiness = [
    {
      'id': 'marine',
      'name': 'Marine',
      'icon': Icons.directions_boat,
      'color': AppTheme.lobColors[1],
      'subtypes': ['Hull', 'Cargo', 'P&I', 'War'],
      'templates': 23,
    },
    {
      'id': 'aviation',
      'name': 'Aviation',
      'icon': Icons.flight,
      'color': AppTheme.lobColors[2],
      'subtypes': ['Hull', 'Liability', 'War', 'Space'],
      'templates': 12,
    },
    {
      'id': 'property',
      'name': 'Property',
      'icon': Icons.business,
      'color': AppTheme.lobColors[3],
      'subtypes': ['Fire', 'BI', 'CAT', 'Terrorism'],
      'templates': 18,
    },
    {
      'id': 'casualty',
      'name': 'Casualty',
      'icon': Icons.person_outline,
      'color': AppTheme.lobColors[4],
      'subtypes': ['GL', 'EL', 'PL', 'Umbrella'],
      'templates': 15,
    },
    {
      'id': 'financial',
      'name': 'Financial Lines',
      'icon': Icons.account_balance,
      'color': AppTheme.lobColors[5],
      'subtypes': ['D&O', 'E&O', 'Crime', 'PI'],
      'templates': 14,
    },
    {
      'id': 'cyber',
      'name': 'Cyber',
      'icon': Icons.security,
      'color': AppTheme.lobColors[0],
      'subtypes': ['Network', 'Data Breach', 'Ransomware', 'BI'],
      'templates': 15,
    },
    {
      'id': 'energy',
      'name': 'Energy',
      'icon': Icons.bolt,
      'color': AppTheme.lobColors[6],
      'subtypes': ['Upstream', 'Downstream', 'Power', 'Renewable'],
      'templates': 11,
    },
    {
      'id': 'reinsurance',
      'name': 'Reinsurance',
      'icon': Icons.autorenew,
      'color': AppTheme.lobColors[7],
      'subtypes': ['Treaty', 'Facultative', 'XoL', 'QS'],
      'templates': 8,
    },
    {
      'id': 'specialty',
      'name': 'Specialty',
      'icon': Icons.star_outline,
      'color': AppTheme.lobColors[8],
      'subtypes': ['Political Risk', 'Credit', 'K&R', 'Contingency'],
      'templates': 9,
    },
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: AppTheme.surface,
        elevation: 0,
        leading: IconButton(
          onPressed: () => context.pop(),
          icon: const Icon(Icons.arrow_back_ios),
          color: AppTheme.textPrimary,
        ),
        title: Text(
          widget.documentTypeName,
          style: const TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
            fontFamily: 'Inter',
          ),
        ),
        centerTitle: true,
      ),
      body: Column(
        children: [
          // Header
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            color: AppTheme.surface,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Select Line of Business',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                    fontFamily: 'Inter',
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  'Choose the insurance class for your ${widget.documentTypeName.toLowerCase()}',
                  style: TextStyle(
                    fontSize: 14,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),

          // Grid of Lines of Business
          Expanded(
            child: GridView.builder(
              padding: const EdgeInsets.all(16),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 3,
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 0.85,
              ),
              itemCount: _linesOfBusiness.length,
              itemBuilder: (context, index) {
                final lob = _linesOfBusiness[index];
                final isSelected = _selectedLob == lob['id'];
                return _buildLobCard(lob, isSelected);
              },
            ),
          ),

          // Bottom action bar
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppTheme.surface,
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
                  onPressed: _selectedLob == null
                      ? null
                      : () {
                          context.push('/documents/create/configure', extra: {
                            'documentType': widget.documentType,
                            'documentTypeName': widget.documentTypeName,
                            'lineOfBusiness': _selectedLob,
                            'lineOfBusinessName': _linesOfBusiness
                                .firstWhere((l) => l['id'] == _selectedLob)['name'],
                          });
                        },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryDark,
                    disabledBackgroundColor: AppTheme.border,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: Text(
                    _selectedLob == null
                        ? 'Select a Line of Business'
                        : 'Continue with ${_linesOfBusiness.firstWhere((l) => l['id'] == _selectedLob)['name']}',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: _selectedLob == null ? AppTheme.textHint : Colors.white,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLobCard(Map<String, dynamic> lob, bool isSelected) {
    final Color color = lob['color'] as Color;
    final subtypes = lob['subtypes'] as List<String>;
    final templates = lob['templates'] as int;

    return GestureDetector(
      onTap: () {
        setState(() {
          _selectedLob = lob['id'] as String;
        });
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        decoration: BoxDecoration(
          color: isSelected ? color.withOpacity(0.1) : AppTheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isSelected ? color : AppTheme.border,
            width: isSelected ? 2 : 1,
          ),
          boxShadow: isSelected
              ? [
                  BoxShadow(
                    color: color.withOpacity(0.2),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ]
              : null,
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Icon
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: isSelected ? color : color.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  lob['icon'] as IconData,
                  color: isSelected ? Colors.white : color,
                  size: 24,
                ),
              ),
              const SizedBox(height: 10),

              // Name
              Text(
                lob['name'] as String,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: isSelected ? color : AppTheme.textPrimary,
                ),
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 4),

              // Subtypes
              Text(
                subtypes.take(2).join(', '),
                style: TextStyle(
                  fontSize: 10,
                  color: AppTheme.textSecondary,
                ),
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),

              const SizedBox(height: 6),

              // Templates count
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: isSelected ? color.withOpacity(0.2) : AppTheme.background,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '$templates templates',
                  style: TextStyle(
                    fontSize: 9,
                    fontWeight: FontWeight.w500,
                    color: isSelected ? color : AppTheme.textHint,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
