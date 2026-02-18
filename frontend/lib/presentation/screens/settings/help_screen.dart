import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';
import '../../widgets/common/screen_header.dart';

/// Help & Features Screen - Shows all 15 platform features and how they work
class HelpScreen extends StatelessWidget {
  const HelpScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const ScreenHeader(
                title: 'Help & Features',
                subtitle: 'Everything InstantRisk can do',
              ),

              // Platform Overview
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [AppTheme.primaryDark, AppTheme.accent],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'InstantRisk v5.0',
                        style: TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'AI-Powered Insurance Underwriting Platform with 15 breakthrough capabilities powered by machine learning, computer vision, and real-time intelligence.',
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.white.withValues(alpha: 0.9),
                          height: 1.5,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Core Features Section
              _buildSectionTitle(context, 'CORE UNDERWRITING'),
              _buildFeatureCard(
                context,
                icon: Icons.upload_file,
                color: AppTheme.primaryDark,
                title: 'AI Document Analysis',
                description: 'Upload insurance submissions (PDFs, scans, photos) and get instant AI-powered risk analysis. Our ML models extract key data, assess risk factors, and generate comprehensive underwriting reports in minutes.',
                howItWorks: 'Upload documents \u2192 AI extracts data \u2192 ML model scores risk \u2192 Get full assessment with pricing recommendations.',
              ),
              _buildFeatureCard(
                context,
                icon: Icons.psychology,
                color: Colors.deepPurple,
                title: 'SHAP Explainability',
                description: 'Understand exactly why AI made each decision. SHAP (SHapley Additive exPlanations) waterfall charts show which risk factors contribute most to each score.',
                howItWorks: 'After analysis \u2192 View AI Decision Explanation panel \u2192 See factor-by-factor breakdown with positive/negative impacts.',
              ),
              _buildFeatureCard(
                context,
                icon: Icons.compare_arrows,
                color: Colors.indigo,
                title: 'Precedent Search',
                description: 'Find similar historical assessments using vector embeddings. Compare current risk against past decisions to ensure consistency and identify patterns.',
                howItWorks: 'Open assessment results \u2192 Similar Precedents panel \u2192 See matching risks with similarity scores and outcomes.',
              ),
              const SizedBox(height: 24),

              // God Mode Features Section
              _buildSectionTitle(context, 'ADVANCED AI FEATURES'),
              _buildFeatureCard(
                context,
                icon: Icons.camera_alt,
                color: Colors.orange,
                title: 'Computer Vision Risk Assessment',
                description: 'Upload property photos and get instant AI inspection. Detects 100+ risk factors: roof condition, fire hazards, structural issues, security features. Replaces \$500-2000 manual inspections.',
                howItWorks: 'Upload property images \u2192 AI analyzes via AWS Bedrock vision \u2192 Get instant property inspection report.',
              ),
              _buildFeatureCard(
                context,
                icon: Icons.public,
                color: Colors.blue,
                title: 'Global Event Intelligence',
                description: 'Real-time monitoring of earthquakes, hurricanes, wildfires, cyber events, and geopolitical changes. Auto-alerts when events affect your portfolio.',
                howItWorks: 'Navigate to Risk Monitor \u2192 Events tab \u2192 See live global events with portfolio impact analysis.',
              ),
              _buildFeatureCard(
                context,
                icon: Icons.mic,
                color: Colors.teal,
                title: 'Voice-First Underwriting',
                description: 'Create assessments, search risks, and generate documents using voice commands. Supports dictation, meeting transcription, and natural language queries.',
                howItWorks: 'Tap microphone icon \u2192 Speak your command \u2192 AI transcribes and executes (e.g., "Create cyber assessment for Acme Corp").',
              ),
              _buildFeatureCard(
                context,
                icon: Icons.hub,
                color: Colors.green,
                title: 'Entity Relationship Graphs',
                description: 'Automatic corporate ownership mapping using Companies House, OpenCorporates, and SEC EDGAR. Detects fraud patterns, shell companies, and circular ownership.',
                howItWorks: 'Open assessment \u2192 Entity Mapping panel \u2192 See corporate structure graph with fraud risk indicators.',
              ),
              _buildFeatureCard(
                context,
                icon: Icons.smart_toy,
                color: Colors.purple,
                title: 'Autonomous Investigation Agent',
                description: 'AI agent that autonomously researches every risk: checks SEC filings, news, reviews, regulatory violations, and competitor pricing. Generates comprehensive investigation reports.',
                howItWorks: 'Start analysis \u2192 Select Deep mode \u2192 Agent runs 10+ research tasks in parallel \u2192 Get 20-page investigation report.',
              ),
              _buildFeatureCard(
                context,
                icon: Icons.dashboard_customize,
                color: Colors.blueGrey,
                title: 'Live Portfolio Analytics',
                description: 'Real-time portfolio dashboard with exposure heatmaps, concentration risk, renewal pipeline, win rates, and predictive analytics powered by DuckDB.',
                howItWorks: 'Navigate to Portfolio Analytics \u2192 See live charts, KPIs, territory maps \u2192 Export automated reports.',
              ),
              _buildFeatureCard(
                context,
                icon: Icons.link,
                color: Colors.amber.shade800,
                title: 'Smart Contract Automation',
                description: 'Blockchain-backed policy issuance on Polygon. Assessment approved \u2192 NFT policy auto-minted \u2192 Tamper-proof audit trail. Parametric triggers for instant claims.',
                howItWorks: 'After assessment approval \u2192 Smart Contracts panel \u2192 View NFT policy token with on-chain verification.',
              ),
              _buildFeatureCard(
                context,
                icon: Icons.visibility,
                color: Colors.red,
                title: 'Multi-Modal AI Analysis',
                description: 'Combined vision + text + voice analysis. Analyze property videos, meeting recordings, handwritten documents, and compare signatures for fraud detection.',
                howItWorks: 'Upload images/videos/audio \u2192 AI processes all modalities \u2192 Get unified risk report.',
              ),
              const SizedBox(height: 24),

              // Monitoring & Intelligence
              _buildSectionTitle(context, 'MONITORING & INTELLIGENCE'),
              _buildFeatureCard(
                context,
                icon: Icons.security,
                color: AppTheme.danger,
                title: 'Data Breach Monitoring (HIBP)',
                description: 'Continuous monitoring of data breaches via Have I Been Pwned. Alerts when insured entities appear in breaches. Critical for cyber insurance risk assessment.',
                howItWorks: 'Risk Monitor \u2192 Breaches tab \u2192 See active breach alerts for portfolio \u2192 Auto-alerts on new breaches.',
              ),
              _buildFeatureCard(
                context,
                icon: Icons.gavel,
                color: Colors.brown,
                title: 'Regulatory Compliance Scanner',
                description: 'Automated scanning of FCA, PRA, EIOPA, and NAIC regulations. Checks each assessment for compliance requirements and flags potential violations.',
                howItWorks: 'Open assessment \u2192 Compliance tab \u2192 See regulatory checklist with pass/fail status.',
              ),
              _buildFeatureCard(
                context,
                icon: Icons.shield,
                color: Colors.deepOrange,
                title: 'Sanctions Screening',
                description: 'Screen insured entities against OFAC, UN, EU, and HMT sanctions lists. Multi-level screening from basic to deep investigation with fuzzy matching.',
                howItWorks: 'Open assessment \u2192 Sanctions section \u2192 Run screening \u2192 See match results with risk scores.',
              ),
              const SizedBox(height: 24),

              // Productivity
              _buildSectionTitle(context, 'PRODUCTIVITY & COLLABORATION'),
              _buildFeatureCard(
                context,
                icon: Icons.chat,
                color: Colors.cyan,
                title: 'AI Copilot Chat',
                description: 'ChatGPT-style AI assistant trained on insurance knowledge. Ask questions about assessments, get market insights, draft emails to brokers, or query your portfolio.',
                howItWorks: 'Navigate to Chat \u2192 Ask anything about insurance \u2192 AI responds with context-aware answers.',
              ),
              _buildFeatureCard(
                context,
                icon: Icons.description,
                color: Colors.lime.shade800,
                title: 'AI Document Generator',
                description: 'Generate MRC slips, policy wordings, endorsements, and regulatory filings. Select document type \u2192 Configure clauses \u2192 AI generates professional documents.',
                howItWorks: 'Documents tab \u2192 Create New \u2192 Select type & line of business \u2192 Review clauses \u2192 Generate.',
              ),
              const SizedBox(height: 24),

              // Quick start guide
              _buildSectionTitle(context, 'QUICK START GUIDE'),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceOf(context),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.borderOf(context)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildStep(context, '1', 'Upload a submission document (PDF, scan, or photo)'),
                      _buildStep(context, '2', 'Select analysis mode (Quick for speed, Deep for comprehensive)'),
                      _buildStep(context, '3', 'Review AI analysis results with risk scores and recommendations'),
                      _buildStep(context, '4', 'Explore advanced features: SHAP explanation, similar precedents, entity mapping'),
                      _buildStep(context, '5', 'Generate professional documents (MRC slips, policy wordings)'),
                      _buildStep(context, '6', 'Monitor portfolio risks via Risk Monitor and Portfolio Analytics'),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Contact
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceOf(context),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.borderOf(context)),
                  ),
                  child: Column(
                    children: [
                      Icon(Icons.support_agent, size: 40, color: AppTheme.primaryDark),
                      const SizedBox(height: 12),
                      Text(
                        'Need Help?',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.text1(context),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Contact support@instantrisk.io for assistance',
                        style: TextStyle(
                          fontSize: 14,
                          color: AppTheme.text2(context),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 40),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSectionTitle(BuildContext context, String title) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Text(
        title,
        style: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w700,
          color: AppTheme.text2(context),
          letterSpacing: 1.2,
        ),
      ),
    );
  }

  Widget _buildFeatureCard(
    BuildContext context, {
    required IconData icon,
    required Color color,
    required String title,
    required String description,
    required String howItWorks,
  }) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
      child: Container(
        decoration: BoxDecoration(
          color: AppTheme.surfaceOf(context),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppTheme.borderOf(context)),
        ),
        child: Theme(
          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
          child: ExpansionTile(
            tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            leading: Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 22),
            ),
            title: Text(
              title,
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w600,
                color: AppTheme.text1(context),
              ),
            ),
            children: [
              Text(
                description,
                style: TextStyle(
                  fontSize: 14,
                  color: AppTheme.text2(context),
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.primaryDark.withValues(alpha: 0.06),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'How it works',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.primaryDark,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      howItWorks,
                      style: TextStyle(
                        fontSize: 13,
                        color: AppTheme.text1(context),
                        height: 1.4,
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

  Widget _buildStep(BuildContext context, String number, String text) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: AppTheme.primaryDark,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Center(
              child: Text(
                number,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                text,
                style: TextStyle(
                  fontSize: 14,
                  color: AppTheme.text1(context),
                  height: 1.4,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
