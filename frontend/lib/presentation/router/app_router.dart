import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/services/auth_service.dart';

// Auth Screens
import '../screens/auth/splash_screen.dart';
import '../screens/auth/onboarding_screen.dart';
import '../screens/auth/welcome_screen.dart';
import '../screens/auth/login_screen.dart';
import '../screens/auth/register_screen.dart';
import '../screens/auth/forgot_password_screen.dart';
import '../screens/auth/pending_approval_screen.dart';
import '../screens/auth/two_factor_verify_screen.dart';
import '../screens/admin/user_approvals_screen.dart';

// Main Screens
import '../screens/home/dashboard_screen.dart';
import '../screens/home/document_intake_screen.dart';
import '../screens/home/processing_screen.dart';

import '../screens/reports/history_screen.dart';
import '../screens/reports/results_screen.dart';
import '../screens/reports/refinement_screen.dart';
import '../screens/reports/contract_screen.dart';
import '../screens/reports/share_view_screen.dart';

import '../screens/chat/unified_chat_screen.dart';

import '../screens/analytics/portfolio_screen.dart';
import '../screens/analytics/performance_screen.dart';

import '../screens/settings/settings_screen.dart';
import '../screens/settings/profile_screen.dart';
import '../screens/settings/subscription_screen.dart';
import '../screens/settings/language_screen.dart';
import '../screens/settings/appearance_screen.dart';
import '../screens/settings/repository_screen.dart';
import '../screens/settings/team_management_screen.dart';
import '../screens/settings/two_factor_screen.dart';
import '../screens/settings/security_screen.dart';
import '../screens/settings/change_password_screen.dart';
import '../screens/settings/sessions_screen.dart';
import '../screens/settings/help_screen.dart';
import '../screens/upload/qr_upload_screen.dart';
import '../screens/training/training_screen.dart';
import '../screens/documents/reference_documents_screen.dart';
import '../screens/documents/document_generation_screen.dart';
import '../screens/documents/documents_hub_screen.dart';
import '../screens/documents/document_editor_screen.dart';
import '../screens/documents/document_type_selection_screen.dart';
import '../screens/documents/line_of_business_screen.dart';
import '../screens/documents/document_configure_screen.dart';
import '../screens/documents/document_preview_screen.dart';
import '../screens/documents/assessment_documents_screen.dart';
import '../screens/documents/ai_document_advisor_screen.dart';
import '../screens/documents/clause_review_screen.dart';
import '../screens/documents/generation_progress_screen.dart';

// Analysis Screens
import '../screens/analysis/analysis_mode_screen.dart';
import '../screens/analysis/analysis_progress_screen.dart';

// Sanctions Screens
import '../screens/sanctions/sanctions_detail_screen.dart';
import '../screens/sanctions/sanctions_screening_progress_screen.dart';

// God Mode Screens
import '../screens/monitoring/risk_monitor_dashboard.dart';
import '../screens/analytics/portfolio_dashboard.dart';
import '../screens/entities/entity_graph_screen.dart';

// Shell for bottom navigation
import '../widgets/common/main_shell.dart';

/// App Router Configuration
class AppRouter {
  static final GlobalKey<NavigatorState> _rootNavigatorKey =
      GlobalKey<NavigatorState>(debugLabel: 'root');
  static final GlobalKey<NavigatorState> _shellNavigatorKey =
      GlobalKey<NavigatorState>(debugLabel: 'shell');

  /// Public routes that don't require authentication
  static const List<String> _publicRoutes = [
    '/',
    '/welcome',
    '/login',
    '/register',
    '/forgot-password',
    '/onboarding',
    '/pending-approval',
    '/2fa-verify',
  ];

  /// Initialize the router and set up auth service callback
  static void init() {
    // Set up the 401 handler to redirect to login
    AuthService.onUnauthorized = () {
      router.go('/login');
    };
  }

  /// Check if a route is public (no auth required)
  static bool _isPublicRoute(String location) {
    // Check exact matches
    if (_publicRoutes.contains(location)) return true;
    // Check if it's a deep link upload route (public for mobile uploads)
    if (location.startsWith('/upload/')) return true;
    // Share links are public (no auth required)
    if (location.startsWith('/share/')) return true;
    return false;
  }

  static final GoRouter router = GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/',
    debugLogDiagnostics: true,

    // Authentication redirect guard
    redirect: (BuildContext context, GoRouterState state) {
      final isLoggedIn = authService.isLoggedIn;
      final location = state.uri.toString();
      final path = state.uri.path;

      // Deep link routes bypass auth entirely (QR upload flow)
      // Check both location and path to handle different URL formats
      if (location.startsWith('/upload/') ||
          path.startsWith('/upload/') ||
          location.contains('/upload/') ||
          state.matchedLocation.startsWith('/upload/')) {
        return null;
      }

      final isPublicRoute = _isPublicRoute(location) || _isPublicRoute(path);

      // If not logged in and trying to access protected route, redirect to welcome
      if (!isLoggedIn && !isPublicRoute) {
        return '/welcome';
      }

      // If logged in and on auth pages (welcome, login, register), redirect to main app
      if (isLoggedIn && (location == '/welcome' || location == '/login' || location == '/register')) {
        return '/home';
      }

      // No redirect needed
      return null;
    },

    routes: [
      // ==================== AUTH ROUTES ====================
      GoRoute(
        path: '/',
        name: 'splash',
        builder: (context, state) => const SplashScreen(),
      ),
      GoRoute(
        path: '/onboarding',
        name: 'onboarding',
        builder: (context, state) => const OnboardingScreen(),
      ),
      GoRoute(
        path: '/welcome',
        name: 'welcome',
        builder: (context, state) => const WelcomeScreen(),
      ),
      GoRoute(
        path: '/login',
        name: 'login',
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: '/register',
        name: 'register',
        builder: (context, state) => const RegisterScreen(),
      ),
      GoRoute(
        path: '/forgot-password',
        name: 'forgotPassword',
        builder: (context, state) => const ForgotPasswordScreen(),
      ),
      GoRoute(
        path: '/pending-approval',
        name: 'pendingApproval',
        builder: (context, state) => const PendingApprovalScreen(),
      ),
      GoRoute(
        path: '/2fa-verify',
        name: '2faVerify',
        builder: (context, state) {
          final extra = state.extra as Map<String, String>?;
          return TwoFactorVerifyScreen(
            email: extra?['email'] ?? '',
            password: extra?['password'] ?? '',
          );
        },
      ),

      // ==================== QR UPLOAD (Deep Link) ====================
      GoRoute(
        path: '/upload/:token',
        name: 'qrUpload',
        builder: (context, state) => QRUploadScreen(
          token: state.pathParameters['token']!,
        ),
      ),

      // ==================== SHARED ASSESSMENT (Public) ====================
      GoRoute(
        path: '/share/:token',
        name: 'sharedAssessment',
        builder: (context, state) => ShareViewScreen(
          token: state.pathParameters['token']!,
        ),
      ),

      // ==================== DOCUMENT EDITOR ====================
      GoRoute(
        path: '/documents/edit/:documentId',
        name: 'documentEditor',
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>? ?? {};
          return DocumentEditorScreen(
            documentId: state.pathParameters['documentId']!,
            assessmentId: extra['assessmentId'] as String?,
          );
        },
      ),

      // ==================== MAIN APP (with bottom nav) ====================
      ShellRoute(
        navigatorKey: _shellNavigatorKey,
        builder: (context, state, child) => MainShell(child: child),
        routes: [
          // HOME TAB
          GoRoute(
            path: '/home',
            name: 'home',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: DashboardScreen(),
            ),
            routes: [
              GoRoute(
                path: 'intake',
                name: 'documentIntake',
                builder: (context, state) => const DocumentIntakeScreen(),
              ),
              GoRoute(
                path: 'processing/:documentId',
                name: 'processing',
                builder: (context, state) => ProcessingScreen(
                  documentId: state.pathParameters['documentId']!,
                ),
              ),
            ],
          ),

          // REPORTS TAB
          GoRoute(
            path: '/reports',
            name: 'reports',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: HistoryScreen(),
            ),
            routes: [
              GoRoute(
                path: 'results/:assessmentId',
                name: 'results',
                builder: (context, state) {
                  final extra = state.extra as Map<String, dynamic>? ?? {};
                  return ResultsScreen(
                    assessmentId: state.pathParameters['assessmentId']!,
                    analysisData: extra['analysisData'] as Map<String, dynamic>?,
                    isProcessing: extra['isProcessing'] as bool? ?? false,
                    sessionId: extra['sessionId'] as String?,
                    sessionToken: extra['sessionToken'] as String?,
                    documentCount: extra['documentCount'] as int? ?? 1,
                  );
                },
              ),
              GoRoute(
                path: 'refine/:assessmentId',
                name: 'refinement',
                builder: (context, state) => RefinementScreen(
                  assessmentId: state.pathParameters['assessmentId']!,
                ),
              ),
              GoRoute(
                path: 'contract/:assessmentId',
                name: 'contract',
                builder: (context, state) => ContractScreen(
                  assessmentId: state.pathParameters['assessmentId']!,
                ),
              ),
              GoRoute(
                path: 'generate/:assessmentId',
                name: 'generateDocuments',
                builder: (context, state) => DocumentGenerationScreen(
                  assessmentId: state.pathParameters['assessmentId']!,
                ),
              ),
              GoRoute(
                path: 'documents/:assessmentId',
                name: 'assessmentDocuments',
                builder: (context, state) => AssessmentDocumentsScreen(
                  assessmentId: state.pathParameters['assessmentId']!,
                ),
              ),
            ],
          ),

          // ANALYSIS ROUTES (inside ShellRoute for nav bar)
          GoRoute(
            path: '/analysis/mode/:assessmentId',
            name: 'analysisMode',
            builder: (context, state) {
              final extra = state.extra as Map<String, dynamic>? ?? {};
              return AnalysisModeScreen(
                assessmentId: state.pathParameters['assessmentId']!,
                documentCount: extra['documentCount'] as int? ?? 1,
                totalChars: extra['totalChars'] as int? ?? 2000,
              );
            },
          ),
          GoRoute(
            path: '/analysis/progress/:assessmentId',
            name: 'analysisProgress',
            builder: (context, state) {
              final extra = state.extra as Map<String, dynamic>? ?? {};
              return AnalysisProgressScreen(
                assessmentId: state.pathParameters['assessmentId']!,
                mode: extra['mode'] as String? ?? 'deep',
                documentCount: extra['documentCount'] as int? ?? 1,
                totalChars: extra['totalChars'] as int? ?? 2000,
              );
            },
          ),
          GoRoute(
            path: '/assessments/:assessmentId/results',
            name: 'assessmentResults',
            builder: (context, state) {
              final extra = state.extra as Map<String, dynamic>? ?? {};
              return ResultsScreen(
                assessmentId: state.pathParameters['assessmentId']!,
                analysisData: extra['analysisData'] as Map<String, dynamic>?,
                isProcessing: extra['isProcessing'] as bool? ?? false,
                sessionId: extra['sessionId'] as String?,
                    sessionToken: extra['sessionToken'] as String?,
                documentCount: extra['documentCount'] as int? ?? 1,
              );
            },
          ),

          // ─── GOD MODE ROUTES ───

          // Risk Monitor Dashboard - 24/7 alerts
          GoRoute(
            path: '/monitoring',
            name: 'riskMonitor',
            builder: (context, state) => const RiskMonitorDashboard(),
          ),

          // Portfolio Analytics Dashboard - DuckDB analytics
          GoRoute(
            path: '/analytics/portfolio-dashboard',
            name: 'portfolioDashboard',
            builder: (context, state) => const PortfolioDashboard(),
          ),

          // Entity Graph - per assessment
          GoRoute(
            path: '/assessments/:assessmentId/entities',
            name: 'entityGraph',
            builder: (context, state) => EntityGraphScreen(
              assessmentId: state.pathParameters['assessmentId']!,
            ),
          ),

          // ─── SANCTIONS SCREENING (inside shell for nav bar) ───
          GoRoute(
            path: '/assessments/:assessmentId/sanctions',
            name: 'sanctionsDetail',
            builder: (context, state) => SanctionsDetailScreen(
              assessmentId: state.pathParameters['assessmentId']!,
            ),
          ),
          GoRoute(
            path: '/assessments/:assessmentId/sanctions/screening',
            name: 'sanctionsScreeningProgress',
            builder: (context, state) {
              final extra = state.extra as Map<String, dynamic>? ?? {};
              return SanctionsScreeningProgressScreen(
                assessmentId: state.pathParameters['assessmentId']!,
                level: extra['level'] as String? ?? 'standard',
              );
            },
          ),

          // CHAT TAB - Unified AI Chat (Claude/ChatGPT style)
          GoRoute(
            path: '/chat',
            name: 'chat',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: UnifiedChatScreen(),
            ),
            routes: [
              GoRoute(
                path: 'conversation/:conversationId',
                name: 'chatConversation',
                builder: (context, state) => UnifiedChatScreen(
                  conversationId: state.pathParameters['conversationId'],
                ),
              ),
            ],
          ),

          // ANALYTICS TAB
          GoRoute(
            path: '/analytics',
            name: 'analytics',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: PortfolioScreen(),
            ),
            routes: [
              GoRoute(
                path: 'performance',
                name: 'performance',
                builder: (context, state) => const PerformanceScreen(),
              ),
            ],
          ),

          // TRAINING TAB - Upload documents to improve AI
          GoRoute(
            path: '/training',
            name: 'training',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: TrainingScreen(),
            ),
          ),

          // DOCUMENTS TAB (Reference + Assessment Documents)
          GoRoute(
            path: '/documents',
            name: 'documents',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: DocumentsHubScreen(),
            ),
            routes: [
              // V3 Document Generator - Create Flow
              GoRoute(
                path: 'create',
                name: 'documentCreate',
                builder: (context, state) => const DocumentTypeSelectionScreen(),
              ),
              GoRoute(
                path: 'line-of-business',
                name: 'documentLineOfBusiness',
                builder: (context, state) {
                  final extra = state.extra as Map<String, dynamic>? ?? {};
                  return LineOfBusinessScreen(
                    documentType: extra['documentType'] as String? ?? 'full_policy',
                    documentTypeName: extra['documentTypeName'] as String? ?? 'Full Policy',
                  );
                },
              ),
              GoRoute(
                path: 'create/configure',
                name: 'documentConfigure',
                builder: (context, state) {
                  final extra = state.extra as Map<String, dynamic>? ?? {};
                  return DocumentConfigureScreen(
                    documentType: extra['documentType'] as String? ?? 'full_policy',
                    documentTypeName: extra['documentTypeName'] as String? ?? 'Full Policy',
                    lineOfBusiness: extra['lineOfBusiness'] as String? ?? 'cyber',
                    lineOfBusinessName: extra['lineOfBusinessName'] as String? ?? 'Cyber',
                  );
                },
              ),
              // Document Preview
              GoRoute(
                path: 'preview/:documentId',
                name: 'documentPreview',
                builder: (context, state) {
                  final extra = state.extra as Map<String, dynamic>? ?? {};
                  return DocumentPreviewScreen(
                    documentId: state.pathParameters['documentId']!,
                    assessmentId: extra['assessmentId'] as String?,
                  );
                },
              ),
              // Reference Documents
              GoRoute(
                path: 'reference',
                name: 'referenceDocuments',
                builder: (context, state) => const ReferenceDocumentsScreen(),
              ),
              // AI Document Advisor (replaces static type selection)
              GoRoute(
                path: 'ai-advisor/:assessmentId',
                name: 'aiDocumentAdvisor',
                builder: (context, state) => AIDocumentAdvisorScreen(
                  assessmentId: state.pathParameters['assessmentId']!,
                ),
              ),
              // Clause Review
              GoRoute(
                path: 'clause-review',
                name: 'clauseReview',
                builder: (context, state) {
                  final extra = state.extra as Map<String, dynamic>? ?? {};
                  return ClauseReviewScreen(
                    assessmentId: extra['assessmentId'] as String? ?? '',
                    selectedDocuments: (extra['selectedDocuments'] as List?)
                        ?.map((d) => Map<String, dynamic>.from(d as Map))
                        .toList() ?? [],
                  );
                },
              ),
              // Generation Progress + Preview
              GoRoute(
                path: 'generation-progress',
                name: 'generationProgress',
                builder: (context, state) {
                  final extra = state.extra as Map<String, dynamic>? ?? {};
                  return GenerationProgressScreen(
                    assessmentId: extra['assessmentId'] as String? ?? '',
                    selectedDocuments: (extra['selectedDocuments'] as List?)
                        ?.map((d) => Map<String, dynamic>.from(d as Map))
                        .toList() ?? [],
                    clausesByDoc: (extra['clausesByDoc'] as Map?)?.map(
                      (k, v) => MapEntry(
                        k.toString(),
                        (v as List).map((c) => Map<String, dynamic>.from(c as Map)).toList(),
                      ),
                    ),
                  );
                },
              ),
            ],
          ),

          // SETTINGS TAB
          GoRoute(
            path: '/settings',
            name: 'settings',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: SettingsScreen(),
            ),
            routes: [
              GoRoute(
                path: 'profile',
                name: 'profile',
                builder: (context, state) => const ProfileScreen(),
              ),
              GoRoute(
                path: 'subscription',
                name: 'subscription',
                builder: (context, state) => const SubscriptionScreen(),
              ),
              GoRoute(
                path: 'language',
                name: 'language',
                builder: (context, state) => const LanguageScreen(),
              ),
              GoRoute(
                path: 'appearance',
                name: 'appearance',
                builder: (context, state) => const AppearanceScreen(),
              ),
              GoRoute(
                path: 'repository',
                name: 'repository',
                builder: (context, state) => const RepositoryScreen(),
              ),
              GoRoute(
                path: 'teams',
                name: 'teamManagement',
                builder: (context, state) => const TeamManagementScreen(),
              ),
              GoRoute(
                path: 'approvals',
                name: 'userApprovals',
                builder: (context, state) => const UserApprovalsScreen(),
              ),
              GoRoute(
                path: 'security',
                name: 'security',
                builder: (context, state) => const SecurityScreen(),
                routes: [
                  GoRoute(
                    path: 'password',
                    name: 'changePassword',
                    builder: (context, state) => const ChangePasswordScreen(),
                  ),
                  GoRoute(
                    path: '2fa',
                    name: 'twoFactor',
                    builder: (context, state) => const TwoFactorScreen(),
                  ),
                  GoRoute(
                    path: 'sessions',
                    name: 'sessions',
                    builder: (context, state) => const SessionsScreen(),
                  ),
                ],
              ),
              GoRoute(
                path: 'help',
                name: 'help',
                builder: (context, state) => const HelpScreen(),
              ),
            ],
          ),
        ],
      ),
    ],

    // Error handling
    errorBuilder: (context, state) => Scaffold(
      body: Center(
        child: Text('Page not found: ${state.uri}'),
      ),
    ),
  );
}
