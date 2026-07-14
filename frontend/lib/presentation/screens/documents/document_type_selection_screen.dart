import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Document Type Selection Screen - V3 Document Generator
/// Allows users to select what type of document to create
class DocumentTypeSelectionScreen extends StatelessWidget {
  const DocumentTypeSelectionScreen({super.key});

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
        title: const Text(
          'Create Document',
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: AppTheme.textPrimary,
            fontFamily: 'Inter',
          ),
        ),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            const Text(
              'What would you like to create?',
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
                fontFamily: 'Inter',
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Select a document type to get started with AI-powered generation',
              style: TextStyle(
                fontSize: 15,
                color: AppTheme.textSecondary,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 32),

            // Document Type Cards
            _buildDocumentTypeCard(
              context: context,
              icon: Icons.description,
              iconColor: AppTheme.primaryDark,
              title: 'Full Policy Wording',
              description: 'Complete insurance policy with all sections',
              features: [
                'Insuring Agreement',
                'Definitions',
                'Exclusions',
                'Conditions',
                'Claims Procedure',
                'Schedule',
              ],
              documentType: 'full_policy',
            ),

            const SizedBox(height: 16),

            _buildDocumentTypeCard(
              context: context,
              icon: Icons.edit_document,
              iconColor: Colors.purple,
              title: 'Endorsement / Extension',
              description: 'Modify existing policy coverage',
              features: [
                'Additional insureds',
                'Coverage extensions',
                'Policy amendments',
              ],
              documentType: 'endorsement',
            ),

            const SizedBox(height: 16),

            _buildDocumentTypeCard(
              context: context,
              icon: Icons.assignment,
              iconColor: Colors.orange,
              title: "Lloyd's Slip",
              description: "Market placing slip for Lloyd's syndicates",
              features: [
                'Risk details',
                'Lines & shares',
                'Special conditions',
              ],
              documentType: 'lloyds_slip',
            ),

            const SizedBox(height: 16),

            _buildDocumentTypeCard(
              context: context,
              icon: Icons.analytics,
              iconColor: Colors.teal,
              title: 'Risk Summary',
              description: 'Underwriting summary for review',
              features: [
                'Risk overview',
                'Key metrics',
                'Recommendations',
              ],
              documentType: 'risk_summary',
            ),

            const SizedBox(height: 16),

            _buildDocumentTypeCard(
              context: context,
              icon: Icons.format_quote,
              iconColor: Colors.blue,
              title: 'Individual Clause',
              description: 'Generate specific clauses only',
              features: [
                'Custom clauses',
                'LMA clauses',
                'Exclusion clauses',
              ],
              documentType: 'individual_clause',
            ),

            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  Widget _buildDocumentTypeCard({
    required BuildContext context,
    required IconData icon,
    required Color iconColor,
    required String title,
    required String description,
    required List<String> features,
    required String documentType,
  }) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: AppTheme.border),
      ),
      child: InkWell(
        onTap: () {
          context.push('/documents/line-of-business', extra: {
            'documentType': documentType,
            'documentTypeName': title,
          });
        },
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Icon
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: iconColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  icon,
                  color: iconColor,
                  size: 28,
                ),
              ),
              const SizedBox(width: 16),

              // Content
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textPrimary,
                        fontFamily: 'Inter',
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      description,
                      style: TextStyle(
                        fontSize: 14,
                        color: AppTheme.textSecondary,
                        height: 1.3,
                      ),
                    ),
                    const SizedBox(height: 12),

                    // Features chips
                    Wrap(
                      spacing: 8,
                      runSpacing: 6,
                      children: features.map((feature) {
                        return Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: AppTheme.background,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            feature,
                            style: const TextStyle(
                              fontSize: 12,
                              color: AppTheme.textSecondary,
                            ),
                          ),
                        );
                      }).toList(),
                    ),
                  ],
                ),
              ),

              // Arrow
              Icon(
                Icons.arrow_forward_ios,
                color: AppTheme.textHint,
                size: 16,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
