import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ar.dart';
import 'app_localizations_de.dart';
import 'app_localizations_en.dart';
import 'app_localizations_es.dart';
import 'app_localizations_fr.dart';
import 'app_localizations_hi.dart';
import 'app_localizations_it.dart';
import 'app_localizations_ja.dart';
import 'app_localizations_ko.dart';
import 'app_localizations_nl.dart';
import 'app_localizations_pt.dart';
import 'app_localizations_zh.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'generated/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale) : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate = _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates = <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('ar'),
    Locale('de'),
    Locale('en'),
    Locale('es'),
    Locale('fr'),
    Locale('hi'),
    Locale('it'),
    Locale('ja'),
    Locale('ko'),
    Locale('nl'),
    Locale('pt'),
    Locale('zh')
  ];

  /// The application name
  ///
  /// In en, this message translates to:
  /// **'InstantRisk'**
  String get appName;

  /// Settings page title
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get settings;

  /// Language settings title
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get language;

  /// Language settings subtitle
  ///
  /// In en, this message translates to:
  /// **'Choose your preferred language'**
  String get languageSubtitle;

  /// Info message on language settings page
  ///
  /// In en, this message translates to:
  /// **'Choose your preferred language. The app will update immediately when you save.'**
  String get languageChangeInfo;

  /// Save button text
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get save;

  /// Cancel button text
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// Change button text
  ///
  /// In en, this message translates to:
  /// **'Change'**
  String get change;

  /// Success message when language is changed
  ///
  /// In en, this message translates to:
  /// **'Language changed successfully'**
  String get languageChanged;

  /// Home tab label
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get home;

  /// Reports tab label
  ///
  /// In en, this message translates to:
  /// **'Reports'**
  String get reports;

  /// Chat tab label
  ///
  /// In en, this message translates to:
  /// **'Chat'**
  String get chat;

  /// Analytics tab label
  ///
  /// In en, this message translates to:
  /// **'Analytics'**
  String get analytics;

  /// Documents tab label
  ///
  /// In en, this message translates to:
  /// **'Documents'**
  String get documents;

  /// Templates tab label
  ///
  /// In en, this message translates to:
  /// **'Templates'**
  String get templates;

  /// Profile settings title
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get profile;

  /// Profile settings subtitle
  ///
  /// In en, this message translates to:
  /// **'Manage your personal information'**
  String get profileSubtitle;

  /// Subscription settings title
  ///
  /// In en, this message translates to:
  /// **'Subscription'**
  String get subscription;

  /// Current subscription plan
  ///
  /// In en, this message translates to:
  /// **'Professional Plan'**
  String get subscriptionPlan;

  /// Security settings title
  ///
  /// In en, this message translates to:
  /// **'Security'**
  String get security;

  /// Security settings subtitle
  ///
  /// In en, this message translates to:
  /// **'Password, 2FA, sessions'**
  String get securitySubtitle;

  /// Account section title
  ///
  /// In en, this message translates to:
  /// **'Account'**
  String get account;

  /// Team admin section title
  ///
  /// In en, this message translates to:
  /// **'Team & Administration'**
  String get teamAdmin;

  /// Team management title
  ///
  /// In en, this message translates to:
  /// **'Team Management'**
  String get teamManagement;

  /// Team management subtitle
  ///
  /// In en, this message translates to:
  /// **'Manage teams, members & roles'**
  String get teamManagementSubtitle;

  /// Roles and permissions title
  ///
  /// In en, this message translates to:
  /// **'Roles & Permissions'**
  String get rolesPermissions;

  /// Roles and permissions subtitle
  ///
  /// In en, this message translates to:
  /// **'Configure access control'**
  String get rolesPermissionsSubtitle;

  /// Lloyd's admin dashboard title
  ///
  /// In en, this message translates to:
  /// **'Lloyd\'s Admin Dashboard'**
  String get lloydsAdminDashboard;

  /// Lloyd's admin dashboard subtitle
  ///
  /// In en, this message translates to:
  /// **'View all syndicates & market data'**
  String get lloydsAdminSubtitle;

  /// Lloyd's market section title
  ///
  /// In en, this message translates to:
  /// **'Lloyd\'s Market'**
  String get lloydsMarket;

  /// Syndicate dashboard title
  ///
  /// In en, this message translates to:
  /// **'Syndicate Dashboard'**
  String get syndicateDashboard;

  /// Syndicate dashboard subtitle
  ///
  /// In en, this message translates to:
  /// **'Overview of syndicate metrics'**
  String get syndicateDashboardSubtitle;

  /// Placement board title
  ///
  /// In en, this message translates to:
  /// **'Placement Board'**
  String get placementBoard;

  /// Placement board subtitle
  ///
  /// In en, this message translates to:
  /// **'Active placements & pipeline'**
  String get placementBoardSubtitle;

  /// Exposure dashboard title
  ///
  /// In en, this message translates to:
  /// **'Exposure Dashboard'**
  String get exposureDashboard;

  /// Exposure dashboard subtitle
  ///
  /// In en, this message translates to:
  /// **'Risk exposure analysis'**
  String get exposureDashboardSubtitle;

  /// Regulatory compliance title
  ///
  /// In en, this message translates to:
  /// **'Regulatory Compliance'**
  String get regulatoryCompliance;

  /// Regulatory compliance subtitle
  ///
  /// In en, this message translates to:
  /// **'Returns & compliance reports'**
  String get regulatoryComplianceSubtitle;

  /// Pricing engine title
  ///
  /// In en, this message translates to:
  /// **'Pricing Engine'**
  String get pricingEngine;

  /// Pricing engine subtitle
  ///
  /// In en, this message translates to:
  /// **'InstantRisk Engine pricing models'**
  String get pricingEngineSubtitle;

  /// Data quality title
  ///
  /// In en, this message translates to:
  /// **'Data Quality'**
  String get dataQuality;

  /// Data quality subtitle
  ///
  /// In en, this message translates to:
  /// **'Data validation & quality metrics'**
  String get dataQualitySubtitle;

  /// UMR management title
  ///
  /// In en, this message translates to:
  /// **'UMR Management'**
  String get umrManagement;

  /// UMR management subtitle
  ///
  /// In en, this message translates to:
  /// **'Unique Market Reference tracking'**
  String get umrManagementSubtitle;

  /// App settings section title
  ///
  /// In en, this message translates to:
  /// **'App Settings'**
  String get appSettings;

  /// Document repository title
  ///
  /// In en, this message translates to:
  /// **'Document Repository'**
  String get documentRepository;

  /// Document repository subtitle
  ///
  /// In en, this message translates to:
  /// **'Manage stored documents'**
  String get documentRepositorySubtitle;

  /// Notifications title
  ///
  /// In en, this message translates to:
  /// **'Notifications'**
  String get notifications;

  /// Notifications subtitle
  ///
  /// In en, this message translates to:
  /// **'Push, email, SMS alerts'**
  String get notificationsSubtitle;

  /// Appearance title
  ///
  /// In en, this message translates to:
  /// **'Appearance'**
  String get appearance;

  /// Appearance subtitle
  ///
  /// In en, this message translates to:
  /// **'Light mode'**
  String get appearanceSubtitle;

  /// Support section title
  ///
  /// In en, this message translates to:
  /// **'Support'**
  String get support;

  /// Help center title
  ///
  /// In en, this message translates to:
  /// **'Help Center'**
  String get helpCenter;

  /// Help center subtitle
  ///
  /// In en, this message translates to:
  /// **'FAQs and guides'**
  String get helpCenterSubtitle;

  /// Contact support title
  ///
  /// In en, this message translates to:
  /// **'Contact Support'**
  String get contactSupport;

  /// Contact support subtitle
  ///
  /// In en, this message translates to:
  /// **'Get help from our team'**
  String get contactSupportSubtitle;

  /// Report bug title
  ///
  /// In en, this message translates to:
  /// **'Report a Bug'**
  String get reportBug;

  /// Report bug subtitle
  ///
  /// In en, this message translates to:
  /// **'Help us improve'**
  String get reportBugSubtitle;

  /// About section title
  ///
  /// In en, this message translates to:
  /// **'About'**
  String get about;

  /// About InstantRisk title
  ///
  /// In en, this message translates to:
  /// **'About InstantRisk'**
  String get aboutInstantRisk;

  /// Version text
  ///
  /// In en, this message translates to:
  /// **'Version {version}'**
  String version(String version);

  /// Terms of service title
  ///
  /// In en, this message translates to:
  /// **'Terms of Service'**
  String get termsOfService;

  /// Privacy policy title
  ///
  /// In en, this message translates to:
  /// **'Privacy Policy'**
  String get privacyPolicy;

  /// Log out button text
  ///
  /// In en, this message translates to:
  /// **'Log Out'**
  String get logOut;

  /// Log out confirmation message
  ///
  /// In en, this message translates to:
  /// **'Are you sure you want to log out of InstantRisk?'**
  String get logOutConfirmation;

  /// Login button/title
  ///
  /// In en, this message translates to:
  /// **'Login'**
  String get login;

  /// Register button/title
  ///
  /// In en, this message translates to:
  /// **'Register'**
  String get register;

  /// Email field label
  ///
  /// In en, this message translates to:
  /// **'Email'**
  String get email;

  /// Password field label
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get password;

  /// Forgot password link
  ///
  /// In en, this message translates to:
  /// **'Forgot Password?'**
  String get forgotPassword;

  /// Welcome back message
  ///
  /// In en, this message translates to:
  /// **'Welcome Back'**
  String get welcomeBack;

  /// Create account title
  ///
  /// In en, this message translates to:
  /// **'Create Account'**
  String get createAccount;

  /// Full name field label
  ///
  /// In en, this message translates to:
  /// **'Full Name'**
  String get fullName;

  /// Confirm password field label
  ///
  /// In en, this message translates to:
  /// **'Confirm Password'**
  String get confirmPassword;

  /// Dashboard title
  ///
  /// In en, this message translates to:
  /// **'Dashboard'**
  String get dashboard;

  /// Upload document button
  ///
  /// In en, this message translates to:
  /// **'Upload Document'**
  String get uploadDocument;

  /// Recent assessments title
  ///
  /// In en, this message translates to:
  /// **'Recent Assessments'**
  String get recentAssessments;

  /// View all link
  ///
  /// In en, this message translates to:
  /// **'View All'**
  String get viewAll;

  /// Processing status
  ///
  /// In en, this message translates to:
  /// **'Processing'**
  String get processing;

  /// Completed status
  ///
  /// In en, this message translates to:
  /// **'Completed'**
  String get completed;

  /// Failed status
  ///
  /// In en, this message translates to:
  /// **'Failed'**
  String get failed;

  /// GO decision
  ///
  /// In en, this message translates to:
  /// **'GO'**
  String get goDecision;

  /// NO-GO decision
  ///
  /// In en, this message translates to:
  /// **'NO-GO'**
  String get noGoDecision;

  /// REFER decision
  ///
  /// In en, this message translates to:
  /// **'REFER'**
  String get referDecision;

  /// Risk score label
  ///
  /// In en, this message translates to:
  /// **'Risk Score'**
  String get riskScore;

  /// Overall risk label
  ///
  /// In en, this message translates to:
  /// **'Overall Risk'**
  String get overallRisk;

  /// Low risk level
  ///
  /// In en, this message translates to:
  /// **'Low Risk'**
  String get lowRisk;

  /// Medium risk level
  ///
  /// In en, this message translates to:
  /// **'Medium Risk'**
  String get mediumRisk;

  /// High risk level
  ///
  /// In en, this message translates to:
  /// **'High Risk'**
  String get highRisk;

  /// Sanctions title
  ///
  /// In en, this message translates to:
  /// **'Sanctions'**
  String get sanctions;

  /// Sanctions screening title
  ///
  /// In en, this message translates to:
  /// **'Sanctions Screening'**
  String get sanctionsScreening;

  /// No sanctions matches
  ///
  /// In en, this message translates to:
  /// **'No Matches'**
  String get noMatches;

  /// Number of potential sanctions matches
  ///
  /// In en, this message translates to:
  /// **'{count} Potential Matches'**
  String potentialMatches(int count);

  /// Analysis title
  ///
  /// In en, this message translates to:
  /// **'Analysis'**
  String get analysis;

  /// Quick analysis option
  ///
  /// In en, this message translates to:
  /// **'Quick Analysis'**
  String get quickAnalysis;

  /// Deep analysis option
  ///
  /// In en, this message translates to:
  /// **'Deep Analysis'**
  String get deepAnalysis;

  /// Start analysis button
  ///
  /// In en, this message translates to:
  /// **'Start Analysis'**
  String get startAnalysis;

  /// Analysis in progress message
  ///
  /// In en, this message translates to:
  /// **'Analysis in Progress'**
  String get analysisInProgress;

  /// Analysis complete message
  ///
  /// In en, this message translates to:
  /// **'Analysis Complete'**
  String get analysisComplete;

  /// View results button
  ///
  /// In en, this message translates to:
  /// **'View Results'**
  String get viewResults;

  /// Generate report button
  ///
  /// In en, this message translates to:
  /// **'Generate Report'**
  String get generateReport;

  /// Download PDF button
  ///
  /// In en, this message translates to:
  /// **'Download PDF'**
  String get downloadPdf;

  /// Share button
  ///
  /// In en, this message translates to:
  /// **'Share'**
  String get share;

  /// Error title
  ///
  /// In en, this message translates to:
  /// **'Error'**
  String get error;

  /// Try again button
  ///
  /// In en, this message translates to:
  /// **'Try Again'**
  String get tryAgain;

  /// Loading message
  ///
  /// In en, this message translates to:
  /// **'Loading...'**
  String get loading;

  /// No data message
  ///
  /// In en, this message translates to:
  /// **'No data available'**
  String get noData;

  /// Search placeholder
  ///
  /// In en, this message translates to:
  /// **'Search'**
  String get search;

  /// Filter button
  ///
  /// In en, this message translates to:
  /// **'Filter'**
  String get filter;

  /// Sort by label
  ///
  /// In en, this message translates to:
  /// **'Sort by'**
  String get sortBy;

  /// Date label
  ///
  /// In en, this message translates to:
  /// **'Date'**
  String get date;

  /// Name label
  ///
  /// In en, this message translates to:
  /// **'Name'**
  String get name;

  /// Status label
  ///
  /// In en, this message translates to:
  /// **'Status'**
  String get status;

  /// Type label
  ///
  /// In en, this message translates to:
  /// **'Type'**
  String get type;

  /// Actions label
  ///
  /// In en, this message translates to:
  /// **'Actions'**
  String get actions;

  /// Delete action
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get delete;

  /// Edit action
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get edit;

  /// View action
  ///
  /// In en, this message translates to:
  /// **'View'**
  String get view;

  /// Confirm button
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get confirm;

  /// Yes option
  ///
  /// In en, this message translates to:
  /// **'Yes'**
  String get yes;

  /// No option
  ///
  /// In en, this message translates to:
  /// **'No'**
  String get no;

  /// OK button
  ///
  /// In en, this message translates to:
  /// **'OK'**
  String get ok;

  /// Close button
  ///
  /// In en, this message translates to:
  /// **'Close'**
  String get close;

  /// Back button
  ///
  /// In en, this message translates to:
  /// **'Back'**
  String get back;

  /// Next button
  ///
  /// In en, this message translates to:
  /// **'Next'**
  String get next;

  /// Previous button
  ///
  /// In en, this message translates to:
  /// **'Previous'**
  String get previous;

  /// Submit button
  ///
  /// In en, this message translates to:
  /// **'Submit'**
  String get submit;

  /// Done button
  ///
  /// In en, this message translates to:
  /// **'Done'**
  String get done;

  /// Refresh button
  ///
  /// In en, this message translates to:
  /// **'Refresh'**
  String get refresh;

  /// Retry button
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get retry;

  /// Unsaved changes warning
  ///
  /// In en, this message translates to:
  /// **'You have unsaved changes'**
  String get unsavedChanges;

  /// Discard changes button
  ///
  /// In en, this message translates to:
  /// **'Discard Changes'**
  String get discardChanges;

  /// Save changes button
  ///
  /// In en, this message translates to:
  /// **'Save Changes'**
  String get saveChanges;

  /// Message shown when user has unsaved language changes
  ///
  /// In en, this message translates to:
  /// **'You have unsaved changes. Press Save to apply the new language.'**
  String get unsavedChangesPressSave;

  /// Banner text when language is changed
  ///
  /// In en, this message translates to:
  /// **'Language changed to {languageName}'**
  String languageChangedTo(String languageName);

  /// Undo button text
  ///
  /// In en, this message translates to:
  /// **'Undo'**
  String get undo;

  /// Save language preference button
  ///
  /// In en, this message translates to:
  /// **'Save Language Preference'**
  String get saveLanguagePreference;

  /// Error message when language save fails
  ///
  /// In en, this message translates to:
  /// **'Failed to save language preference. Please try again.'**
  String get failedToSaveLanguage;

  /// Discard changes dialog title
  ///
  /// In en, this message translates to:
  /// **'Discard Changes?'**
  String get discardChangesQuestion;

  /// Discard changes dialog message
  ///
  /// In en, this message translates to:
  /// **'You have unsaved changes. Do you want to discard them?'**
  String get discardChangesMessage;

  /// Discard button text
  ///
  /// In en, this message translates to:
  /// **'Discard'**
  String get discard;

  /// Right-to-left language indicator
  ///
  /// In en, this message translates to:
  /// **'RTL'**
  String get rtlLabel;

  /// Back to dashboard button text
  ///
  /// In en, this message translates to:
  /// **'Back to Dashboard'**
  String get backToDashboard;

  /// Message when AI analysis is not yet available
  ///
  /// In en, this message translates to:
  /// **'No AI analysis available yet.\nClick \"Analyze\" to generate risk insights.'**
  String get noAiAnalysisYet;

  /// Message prompting user to calculate pricing
  ///
  /// In en, this message translates to:
  /// **'Click \"Calculate\" to generate a technical premium for this risk.'**
  String get clickCalculatePricing;

  /// Message when pricing is not available for declined risks
  ///
  /// In en, this message translates to:
  /// **'Pricing not available for declined risks.'**
  String get pricingNotAvailableDeclined;

  /// Leave analysis dialog title
  ///
  /// In en, this message translates to:
  /// **'Leave Analysis?'**
  String get leaveAnalysis;

  /// Stay here button text
  ///
  /// In en, this message translates to:
  /// **'Stay Here'**
  String get stayHere;

  /// Run in background button text
  ///
  /// In en, this message translates to:
  /// **'Run in Background'**
  String get runInBackground;

  /// Ask AI about category button
  ///
  /// In en, this message translates to:
  /// **'Ask AI About This Category'**
  String get askAiAboutCategory;

  /// Copy button text
  ///
  /// In en, this message translates to:
  /// **'Copy'**
  String get copy;

  /// Analysis mode screen title
  ///
  /// In en, this message translates to:
  /// **'Analysis Mode'**
  String get analysisMode;

  /// Recommended badge text
  ///
  /// In en, this message translates to:
  /// **'RECOMMENDED'**
  String get recommended;

  /// Agents label
  ///
  /// In en, this message translates to:
  /// **'agents'**
  String get agents;

  /// Documents to analyze count
  ///
  /// In en, this message translates to:
  /// **'{count} document(s) to analyze'**
  String documentsToAnalyze(int count);

  /// Characters label
  ///
  /// In en, this message translates to:
  /// **'characters'**
  String get characters;

  /// Analysis failed message
  ///
  /// In en, this message translates to:
  /// **'Analysis Failed'**
  String get analysisFailed;

  /// Go back button text
  ///
  /// In en, this message translates to:
  /// **'Go Back'**
  String get goBack;

  /// Document center title
  ///
  /// In en, this message translates to:
  /// **'Document Center'**
  String get documentCenter;

  /// Create new document title
  ///
  /// In en, this message translates to:
  /// **'Create New Document'**
  String get createNewDocument;

  /// New document button text
  ///
  /// In en, this message translates to:
  /// **'New Document'**
  String get newDocument;

  /// Recent documents section title
  ///
  /// In en, this message translates to:
  /// **'Recent Documents'**
  String get recentDocuments;

  /// Templates library section title
  ///
  /// In en, this message translates to:
  /// **'Templates Library'**
  String get templatesLibrary;

  /// Browse by line of business subtitle
  ///
  /// In en, this message translates to:
  /// **'Browse by line of business'**
  String get browseByLineOfBusiness;

  /// Assessment documents section title
  ///
  /// In en, this message translates to:
  /// **'Assessment Documents'**
  String get assessmentDocuments;

  /// No assessments yet message
  ///
  /// In en, this message translates to:
  /// **'No Assessments Yet'**
  String get noAssessmentsYet;

  /// Upload documents button
  ///
  /// In en, this message translates to:
  /// **'Upload Documents'**
  String get uploadDocuments;

  /// Search documents dialog title
  ///
  /// In en, this message translates to:
  /// **'Search Documents'**
  String get searchDocuments;

  /// Get started button text
  ///
  /// In en, this message translates to:
  /// **'Get Started'**
  String get getStarted;

  /// Generate button text
  ///
  /// In en, this message translates to:
  /// **'Generate'**
  String get generate;

  /// Uploaded label
  ///
  /// In en, this message translates to:
  /// **'Uploaded'**
  String get uploaded;

  /// Generated label
  ///
  /// In en, this message translates to:
  /// **'Generated'**
  String get generated;

  /// Generate documents screen title
  ///
  /// In en, this message translates to:
  /// **'Generate Documents'**
  String get generateDocuments;

  /// AI recommended documents title
  ///
  /// In en, this message translates to:
  /// **'Recommended Documents'**
  String get aiRecommendedDocuments;

  /// Select documents to generate subtitle
  ///
  /// In en, this message translates to:
  /// **'Select the documents you want to generate'**
  String get selectDocumentsToGenerate;

  /// LMA clauses title
  ///
  /// In en, this message translates to:
  /// **'LMA Clauses'**
  String get lmaClauses;

  /// Selected label
  ///
  /// In en, this message translates to:
  /// **'selected'**
  String get selected;

  /// Required badge text
  ///
  /// In en, this message translates to:
  /// **'REQUIRED'**
  String get required;

  /// Generating documents title
  ///
  /// In en, this message translates to:
  /// **'Generating Documents'**
  String get generatingDocuments;

  /// Engine working message
  ///
  /// In en, this message translates to:
  /// **'InstantRisk Engine is generating your documents'**
  String get aiAgentsWorking;

  /// Complete label
  ///
  /// In en, this message translates to:
  /// **'Complete'**
  String get complete;

  /// Live activity label
  ///
  /// In en, this message translates to:
  /// **'Live Activity'**
  String get liveActivity;

  /// Initializing message
  ///
  /// In en, this message translates to:
  /// **'Initializing...'**
  String get initializing;

  /// Documents generated successfully message
  ///
  /// In en, this message translates to:
  /// **'Documents Generated Successfully'**
  String get documentsGeneratedSuccessfully;

  /// Documents ready for review message
  ///
  /// In en, this message translates to:
  /// **'{count} document(s) ready for review'**
  String documentsReadyForReview(int count);

  /// Preview button text
  ///
  /// In en, this message translates to:
  /// **'Preview'**
  String get preview;

  /// Finalize button text
  ///
  /// In en, this message translates to:
  /// **'Finalize'**
  String get finalize;

  /// Generate more button text
  ///
  /// In en, this message translates to:
  /// **'Generate More'**
  String get generateMore;

  /// Select line of business title
  ///
  /// In en, this message translates to:
  /// **'Select Line of Business'**
  String get selectLineOfBusiness;

  /// Continue with button text
  ///
  /// In en, this message translates to:
  /// **'Continue with {name}'**
  String continueWith(String name);

  /// Select a line of business prompt
  ///
  /// In en, this message translates to:
  /// **'Select a Line of Business'**
  String get selectALineOfBusiness;

  /// Document library title
  ///
  /// In en, this message translates to:
  /// **'Document Library'**
  String get documentLibrary;

  /// Insurance knowledge base subtitle
  ///
  /// In en, this message translates to:
  /// **'Insurance Knowledge Base'**
  String get insuranceKnowledgeBase;

  /// Data label
  ///
  /// In en, this message translates to:
  /// **'Data'**
  String get data;

  /// Categories label
  ///
  /// In en, this message translates to:
  /// **'Categories'**
  String get categories;

  /// All filter option
  ///
  /// In en, this message translates to:
  /// **'All'**
  String get all;

  /// Insurance filter option
  ///
  /// In en, this message translates to:
  /// **'Insurance'**
  String get insurance;

  /// Training filter option
  ///
  /// In en, this message translates to:
  /// **'Training'**
  String get training;

  /// Favorites filter option
  ///
  /// In en, this message translates to:
  /// **'Favorites'**
  String get favorites;

  /// No favorites yet message
  ///
  /// In en, this message translates to:
  /// **'No favorites yet'**
  String get noFavoritesYet;

  /// No documents found message
  ///
  /// In en, this message translates to:
  /// **'No documents found'**
  String get noDocumentsFound;

  /// New chat title
  ///
  /// In en, this message translates to:
  /// **'New Chat'**
  String get newChat;

  /// AI assistant title
  ///
  /// In en, this message translates to:
  /// **'InstantRisk Assistant'**
  String get aiAssistant;

  /// Knowledge sources title
  ///
  /// In en, this message translates to:
  /// **'Knowledge Sources'**
  String get knowledgeSources;

  /// Copied to clipboard message
  ///
  /// In en, this message translates to:
  /// **'Copied to clipboard'**
  String get copiedToClipboard;

  /// Screening levels section title
  ///
  /// In en, this message translates to:
  /// **'SCREENING LEVELS'**
  String get screeningLevels;

  /// Screening history section title
  ///
  /// In en, this message translates to:
  /// **'SCREENING HISTORY'**
  String get screeningHistory;

  /// Run button text
  ///
  /// In en, this message translates to:
  /// **'Run'**
  String get run;

  /// Live findings section title
  ///
  /// In en, this message translates to:
  /// **'LIVE FINDINGS'**
  String get liveFindings;

  /// Message informing user they can close the analysis window
  ///
  /// In en, this message translates to:
  /// **'You can close this window. Analysis will continue in background and results will be available in Reports.'**
  String get analysisCanContinueInBackground;

  /// Minimize live results panel button
  ///
  /// In en, this message translates to:
  /// **'Minimize'**
  String get minimizeLiveResults;

  /// Expand live results panel button
  ///
  /// In en, this message translates to:
  /// **'Show Live Results'**
  String get expandLiveResults;

  /// Checks section title
  ///
  /// In en, this message translates to:
  /// **'CHECKS'**
  String get checks;

  /// Pending status
  ///
  /// In en, this message translates to:
  /// **'Pending'**
  String get pending;

  /// Checking status
  ///
  /// In en, this message translates to:
  /// **'Checking...'**
  String get checking;

  /// Clear status
  ///
  /// In en, this message translates to:
  /// **'CLEAR'**
  String get clear;

  /// Review required status
  ///
  /// In en, this message translates to:
  /// **'REVIEW REQUIRED'**
  String get reviewRequired;

  /// Match found status
  ///
  /// In en, this message translates to:
  /// **'MATCH FOUND'**
  String get matchFound;

  /// No entities found status
  ///
  /// In en, this message translates to:
  /// **'NO ENTITIES FOUND'**
  String get noEntitiesFound;

  /// Screening results section title
  ///
  /// In en, this message translates to:
  /// **'SCREENING RESULTS'**
  String get screeningResults;

  /// View full results button
  ///
  /// In en, this message translates to:
  /// **'View Full Results'**
  String get viewFullResults;

  /// Sections tab label
  ///
  /// In en, this message translates to:
  /// **'Sections'**
  String get sections;

  /// Details tab label
  ///
  /// In en, this message translates to:
  /// **'Details'**
  String get details;

  /// Core sections title
  ///
  /// In en, this message translates to:
  /// **'Core Sections'**
  String get coreSections;

  /// Exclusions title
  ///
  /// In en, this message translates to:
  /// **'Exclusions'**
  String get exclusions;

  /// Conditions title
  ///
  /// In en, this message translates to:
  /// **'Conditions'**
  String get conditions;

  /// Insured information title
  ///
  /// In en, this message translates to:
  /// **'Insured Information'**
  String get insuredInformation;

  /// Coverage limits title
  ///
  /// In en, this message translates to:
  /// **'Coverage Limits'**
  String get coverageLimits;

  /// Premium label
  ///
  /// In en, this message translates to:
  /// **'Premium'**
  String get premium;

  /// Generate document button
  ///
  /// In en, this message translates to:
  /// **'Generate Document'**
  String get generateDocument;

  /// Generating your document title
  ///
  /// In en, this message translates to:
  /// **'Generating Your Document'**
  String get generatingYourDocument;

  /// UMR generate tab
  ///
  /// In en, this message translates to:
  /// **'Generate'**
  String get umrGenerate;

  /// UMR registry tab
  ///
  /// In en, this message translates to:
  /// **'Registry'**
  String get umrRegistry;

  /// UMR validation tab
  ///
  /// In en, this message translates to:
  /// **'Validation'**
  String get umrValidation;

  /// Multi-agent analysis title
  ///
  /// In en, this message translates to:
  /// **'Multi-Agent Analysis'**
  String get multiAgentAnalysis;

  /// 5-agent pipeline label
  ///
  /// In en, this message translates to:
  /// **'5-Agent Pipeline'**
  String get agentPipeline;

  /// Overall progress label
  ///
  /// In en, this message translates to:
  /// **'Overall Progress'**
  String get overallProgress;

  /// Document classifier agent name
  ///
  /// In en, this message translates to:
  /// **'Document Classifier'**
  String get documentClassifier;

  /// Classifying document title
  ///
  /// In en, this message translates to:
  /// **'Classifying Document'**
  String get classifyingDocument;

  /// Classifier agent subtitle
  ///
  /// In en, this message translates to:
  /// **'Identifying document type and validating insurance relevance'**
  String get identifyingDocumentType;

  /// Data extractor agent name
  ///
  /// In en, this message translates to:
  /// **'Data Extractor'**
  String get dataExtractor;

  /// Extracting data title
  ///
  /// In en, this message translates to:
  /// **'Extracting Data'**
  String get extractingData;

  /// Extractor agent subtitle
  ///
  /// In en, this message translates to:
  /// **'Pulling all insurance fields from document'**
  String get pullingInsuranceFields;

  /// Risk analyst agent name
  ///
  /// In en, this message translates to:
  /// **'Risk Analyst'**
  String get riskAnalyst;

  /// Analyzing risks title
  ///
  /// In en, this message translates to:
  /// **'Analyzing Risks'**
  String get analyzingRisks;

  /// Risk analyst subtitle
  ///
  /// In en, this message translates to:
  /// **'Identifying risk factors and exposures'**
  String get identifyingRiskFactors;

  /// Senior underwriter agent name
  ///
  /// In en, this message translates to:
  /// **'Senior Underwriter'**
  String get seniorUnderwriter;

  /// Underwriting decision title
  ///
  /// In en, this message translates to:
  /// **'Underwriting Decision'**
  String get underwritingDecision;

  /// Underwriter agent subtitle
  ///
  /// In en, this message translates to:
  /// **'Making GO/NO-GO/REFER recommendation'**
  String get makingGoNoGoDecision;

  /// Quality assurance agent name
  ///
  /// In en, this message translates to:
  /// **'Quality Assurance'**
  String get qualityAssurance;

  /// Final validation title
  ///
  /// In en, this message translates to:
  /// **'Final Validation'**
  String get finalValidation;

  /// QA agent subtitle
  ///
  /// In en, this message translates to:
  /// **'Ensuring accuracy and completeness'**
  String get ensuringAccuracy;

  /// New assessment title
  ///
  /// In en, this message translates to:
  /// **'New Assessment'**
  String get newAssessment;

  /// InstantRisk Engine analysis label
  ///
  /// In en, this message translates to:
  /// **'AI-Powered Analysis'**
  String get aiPoweredAnalysis;

  /// Risk type auto detection description
  ///
  /// In en, this message translates to:
  /// **'Risk type will be automatically detected from your documents using OCR & AI'**
  String get riskTypeAutoDetected;

  /// Add documents title
  ///
  /// In en, this message translates to:
  /// **'Add Documents'**
  String get addDocuments;

  /// Upload from phone option
  ///
  /// In en, this message translates to:
  /// **'Upload from Phone'**
  String get uploadFromPhone;

  /// Scan QR with phone option
  ///
  /// In en, this message translates to:
  /// **'Scan QR with Phone'**
  String get scanQrWithPhone;

  /// Use phone camera subtitle
  ///
  /// In en, this message translates to:
  /// **'Use phone camera to capture documents'**
  String get usePhoneCamera;

  /// Take photo option
  ///
  /// In en, this message translates to:
  /// **'Take Photo'**
  String get takePhoto;

  /// Capture with camera subtitle
  ///
  /// In en, this message translates to:
  /// **'Capture document with camera'**
  String get captureWithCamera;

  /// Photo gallery option
  ///
  /// In en, this message translates to:
  /// **'Photo Gallery'**
  String get photoGallery;

  /// Select from photos subtitle
  ///
  /// In en, this message translates to:
  /// **'Select from your photos'**
  String get selectFromPhotos;

  /// Browse files option
  ///
  /// In en, this message translates to:
  /// **'Browse Files'**
  String get browseFiles;

  /// Supported file types
  ///
  /// In en, this message translates to:
  /// **'PDF, DOC, XLS and more'**
  String get pdfDocXlsAndMore;

  /// Tap to add documents prompt
  ///
  /// In en, this message translates to:
  /// **'Tap to add documents'**
  String get tapToAddDocuments;

  /// Upload options description
  ///
  /// In en, this message translates to:
  /// **'Take photo, browse files, or select from gallery'**
  String get takePhotoBrowseOrGallery;

  /// Uploaded documents section title
  ///
  /// In en, this message translates to:
  /// **'Uploaded Documents'**
  String get uploadedDocuments;

  /// Files count label
  ///
  /// In en, this message translates to:
  /// **'{count} file(s)'**
  String filesCount(int count);

  /// Recommended documents section title
  ///
  /// In en, this message translates to:
  /// **'Recommended Documents'**
  String get recommendedDocuments;

  /// Recommended documents list
  ///
  /// In en, this message translates to:
  /// **'Application form, Loss history, Financial statements, Prior policy'**
  String get applicationFormLossHistory;

  /// Start risk assessment button
  ///
  /// In en, this message translates to:
  /// **'Start Risk Assessment'**
  String get startRiskAssessment;

  /// Failed to create session error
  ///
  /// In en, this message translates to:
  /// **'Failed to create upload session'**
  String get failedToCreateSession;

  /// Documents received message
  ///
  /// In en, this message translates to:
  /// **'{count} document(s) received'**
  String documentsReceived(int count);

  /// Scan with phone camera instructions
  ///
  /// In en, this message translates to:
  /// **'Scan with your phone camera\nto capture and upload documents'**
  String get scanWithPhoneCamera;

  /// Documents added from phone message
  ///
  /// In en, this message translates to:
  /// **'{count} document(s) added from phone'**
  String documentsAddedFromPhone(int count);

  /// Personal information section title
  ///
  /// In en, this message translates to:
  /// **'Personal Information'**
  String get personalInformation;

  /// Professional information section title
  ///
  /// In en, this message translates to:
  /// **'Professional Information'**
  String get professionalInformation;

  /// Company field label
  ///
  /// In en, this message translates to:
  /// **'Company'**
  String get company;

  /// Role field label
  ///
  /// In en, this message translates to:
  /// **'Role'**
  String get role;

  /// Phone field label
  ///
  /// In en, this message translates to:
  /// **'Phone'**
  String get phone;

  /// Account statistics section title
  ///
  /// In en, this message translates to:
  /// **'Account Statistics'**
  String get accountStatistics;

  /// Member since label
  ///
  /// In en, this message translates to:
  /// **'Member Since'**
  String get memberSince;

  /// Total assessments label
  ///
  /// In en, this message translates to:
  /// **'Total Assessments'**
  String get totalAssessments;

  /// Contracts generated label
  ///
  /// In en, this message translates to:
  /// **'Contracts Generated'**
  String get contractsGenerated;

  /// Last login label
  ///
  /// In en, this message translates to:
  /// **'Last Login'**
  String get lastLogin;

  /// Danger zone section title
  ///
  /// In en, this message translates to:
  /// **'Danger Zone'**
  String get dangerZone;

  /// Delete account warning message
  ///
  /// In en, this message translates to:
  /// **'Once you delete your account, there is no going back. Please be certain.'**
  String get deleteAccountWarning;

  /// Delete account button
  ///
  /// In en, this message translates to:
  /// **'Delete Account'**
  String get deleteAccount;

  /// Profile updated success message
  ///
  /// In en, this message translates to:
  /// **'Profile updated successfully'**
  String get profileUpdatedSuccessfully;

  /// Field required validation message
  ///
  /// In en, this message translates to:
  /// **'This field is required'**
  String get thisFieldRequired;

  /// Delete account confirmation message
  ///
  /// In en, this message translates to:
  /// **'Are you sure you want to delete your account? This action cannot be undone and all your data will be permanently lost.'**
  String get deleteAccountConfirmation;

  /// Professional plan name
  ///
  /// In en, this message translates to:
  /// **'Professional Plan'**
  String get professionalPlan;

  /// Active until date
  ///
  /// In en, this message translates to:
  /// **'Active until {date}'**
  String activeUntil(String date);

  /// Active status badge
  ///
  /// In en, this message translates to:
  /// **'ACTIVE'**
  String get active;

  /// This month's usage section title
  ///
  /// In en, this message translates to:
  /// **'This Month\'s Usage'**
  String get thisMonthsUsage;

  /// Assessments label
  ///
  /// In en, this message translates to:
  /// **'Assessments'**
  String get assessments;

  /// Contract generations label
  ///
  /// In en, this message translates to:
  /// **'Contract Generations'**
  String get contractGenerations;

  /// AI chat messages label
  ///
  /// In en, this message translates to:
  /// **'Engine Chat Messages'**
  String get aiChatMessages;

  /// Document storage label
  ///
  /// In en, this message translates to:
  /// **'Document Storage'**
  String get documentStorage;

  /// Available plans section title
  ///
  /// In en, this message translates to:
  /// **'Available Plans'**
  String get availablePlans;

  /// Basic plan name
  ///
  /// In en, this message translates to:
  /// **'Basic'**
  String get basic;

  /// Enterprise plan name
  ///
  /// In en, this message translates to:
  /// **'Enterprise'**
  String get enterprise;

  /// Popular badge
  ///
  /// In en, this message translates to:
  /// **'POPULAR'**
  String get popular;

  /// Current plan badge
  ///
  /// In en, this message translates to:
  /// **'CURRENT'**
  String get current;

  /// Per month pricing suffix
  ///
  /// In en, this message translates to:
  /// **'/month'**
  String get perMonth;

  /// Assessments per month feature
  ///
  /// In en, this message translates to:
  /// **'{count} assessments/month'**
  String assessmentsPerMonth(String count);

  /// Contract generations count feature
  ///
  /// In en, this message translates to:
  /// **'{count} contract generations'**
  String contractGenerationsCount(String count);

  /// AI chat messages count feature
  ///
  /// In en, this message translates to:
  /// **'{count} AI chat messages'**
  String aiChatMessagesCount(String count);

  /// Document storage amount feature
  ///
  /// In en, this message translates to:
  /// **'{amount} document storage'**
  String documentStorageAmount(String amount);

  /// Email support feature
  ///
  /// In en, this message translates to:
  /// **'Email support'**
  String get emailSupport;

  /// Priority support feature
  ///
  /// In en, this message translates to:
  /// **'Priority support'**
  String get prioritySupport;

  /// Advanced analytics feature
  ///
  /// In en, this message translates to:
  /// **'Advanced analytics'**
  String get advancedAnalytics;

  /// Dedicated support feature
  ///
  /// In en, this message translates to:
  /// **'24/7 dedicated support'**
  String get dedicatedSupport;

  /// Custom integrations feature
  ///
  /// In en, this message translates to:
  /// **'Custom integrations'**
  String get customIntegrations;

  /// White-label options feature
  ///
  /// In en, this message translates to:
  /// **'White-label options'**
  String get whiteLabelOptions;

  /// Unlimited label
  ///
  /// In en, this message translates to:
  /// **'Unlimited'**
  String get unlimited;

  /// Upgrade button
  ///
  /// In en, this message translates to:
  /// **'Upgrade'**
  String get upgrade;

  /// Downgrade button
  ///
  /// In en, this message translates to:
  /// **'Downgrade'**
  String get downgrade;

  /// Billing history section title
  ///
  /// In en, this message translates to:
  /// **'Billing History'**
  String get billingHistory;

  /// Visa card ending in
  ///
  /// In en, this message translates to:
  /// **'Visa ending in {last4}'**
  String visaEndingIn(String last4);

  /// Card expiration date
  ///
  /// In en, this message translates to:
  /// **'Expires {date}'**
  String expires(String date);

  /// Update button
  ///
  /// In en, this message translates to:
  /// **'Update'**
  String get update;

  /// Enterprise edition label
  ///
  /// In en, this message translates to:
  /// **'ENTERPRISE EDITION'**
  String get enterpriseEdition;

  /// Go/No-Go analysis mode
  ///
  /// In en, this message translates to:
  /// **'Go/No-Go Analysis'**
  String get goNoGoAnalysis;

  /// Approved decision
  ///
  /// In en, this message translates to:
  /// **'Approved'**
  String get approved;

  /// Declined decision
  ///
  /// In en, this message translates to:
  /// **'Declined'**
  String get declined;

  /// Refer decision
  ///
  /// In en, this message translates to:
  /// **'Refer'**
  String get refer;

  /// Confidence label
  ///
  /// In en, this message translates to:
  /// **'Confidence'**
  String get confidence;

  /// Completed in time
  ///
  /// In en, this message translates to:
  /// **'Completed in {time}'**
  String completedIn(String time);

  /// Estimated time remaining
  ///
  /// In en, this message translates to:
  /// **'Estimated: {time} remaining'**
  String estimatedRemaining(String time);

  /// Agents section label
  ///
  /// In en, this message translates to:
  /// **'AGENTS'**
  String get agentsLabel;

  /// Findings section label
  ///
  /// In en, this message translates to:
  /// **'FINDINGS'**
  String get findingsLabel;

  /// Done status
  ///
  /// In en, this message translates to:
  /// **'Done'**
  String get doneStatus;

  /// Running status
  ///
  /// In en, this message translates to:
  /// **'Running'**
  String get runningStatus;

  /// Pending status
  ///
  /// In en, this message translates to:
  /// **'Pending'**
  String get pendingStatus;

  /// Identify document type description
  ///
  /// In en, this message translates to:
  /// **'Identify document type'**
  String get identifyDocumentType;

  /// Extract insurance data description
  ///
  /// In en, this message translates to:
  /// **'Extract insurance data'**
  String get extractInsuranceData;

  /// Analyze risk factors description
  ///
  /// In en, this message translates to:
  /// **'Analyze risk factors'**
  String get analyzeRiskFactors;

  /// Make decision description
  ///
  /// In en, this message translates to:
  /// **'Make decision'**
  String get makeDecision;

  /// Underwriter agent name
  ///
  /// In en, this message translates to:
  /// **'Underwriter'**
  String get underwriter;

  /// Analysis running dialog message
  ///
  /// In en, this message translates to:
  /// **'The analysis is running. You can:\n\n• Run in background - analysis continues, check results later in Reports\n• Stay here - wait for completion'**
  String get analysisRunningMessage;

  /// Unexpected error message
  ///
  /// In en, this message translates to:
  /// **'An unexpected error occurred'**
  String get unexpectedError;

  /// Clauses label
  ///
  /// In en, this message translates to:
  /// **'Clauses'**
  String get clauses;

  /// Knowledge label
  ///
  /// In en, this message translates to:
  /// **'Knowledge'**
  String get knowledge;

  /// Languages label
  ///
  /// In en, this message translates to:
  /// **'Languages'**
  String get languages;

  /// Search placeholder for document library
  ///
  /// In en, this message translates to:
  /// **'Search documents, clauses, policies...'**
  String get searchDocumentsClausesPolicies;

  /// Docs abbreviation
  ///
  /// In en, this message translates to:
  /// **'docs'**
  String get docs;

  /// Tap star to favorite instruction
  ///
  /// In en, this message translates to:
  /// **'Tap the star icon on any category to add it to favorites'**
  String get tapStarToFavorite;

  /// Try adjusting search message
  ///
  /// In en, this message translates to:
  /// **'Try adjusting your search or filter'**
  String get tryAdjustingSearch;

  /// Search in category placeholder
  ///
  /// In en, this message translates to:
  /// **'Search in this category...'**
  String get searchInThisCategory;

  /// No documents match search message
  ///
  /// In en, this message translates to:
  /// **'No documents match your search'**
  String get noDocumentsMatchSearch;

  /// No documents in category message
  ///
  /// In en, this message translates to:
  /// **'No documents in this category'**
  String get noDocumentsInCategory;

  /// Content copied message
  ///
  /// In en, this message translates to:
  /// **'Content copied'**
  String get contentCopied;

  /// Path copied to clipboard message
  ///
  /// In en, this message translates to:
  /// **'Path copied to clipboard'**
  String get pathCopiedToClipboard;

  /// Reset password title
  ///
  /// In en, this message translates to:
  /// **'Reset Password'**
  String get resetPassword;

  /// Reset password instructions
  ///
  /// In en, this message translates to:
  /// **'Enter your email address and we\'ll send you instructions to reset your password.'**
  String get resetPasswordInstructions;

  /// Enter your email placeholder
  ///
  /// In en, this message translates to:
  /// **'Enter your email'**
  String get enterYourEmail;

  /// Please enter email validation
  ///
  /// In en, this message translates to:
  /// **'Please enter your email'**
  String get pleaseEnterYourEmail;

  /// Please enter valid email validation
  ///
  /// In en, this message translates to:
  /// **'Please enter a valid email'**
  String get pleaseEnterValidEmail;

  /// Send reset link button
  ///
  /// In en, this message translates to:
  /// **'Send Reset Link'**
  String get sendResetLink;

  /// Back to sign in button
  ///
  /// In en, this message translates to:
  /// **'Back to Sign In'**
  String get backToSignIn;

  /// Check your email title
  ///
  /// In en, this message translates to:
  /// **'Check Your Email'**
  String get checkYourEmail;

  /// Password reset sent to message
  ///
  /// In en, this message translates to:
  /// **'We\'ve sent password reset instructions to'**
  String get passwordResetSentTo;

  /// Didn't receive email resend link
  ///
  /// In en, this message translates to:
  /// **'Didn\'t receive the email? Resend'**
  String get didntReceiveEmailResend;

  /// Start risk assessment journey subtitle
  ///
  /// In en, this message translates to:
  /// **'Start your risk assessment journey'**
  String get startRiskAssessmentJourney;

  /// Enter full name placeholder
  ///
  /// In en, this message translates to:
  /// **'Enter your full name'**
  String get enterYourFullName;

  /// Please enter name validation
  ///
  /// In en, this message translates to:
  /// **'Please enter your name'**
  String get pleaseEnterYourName;

  /// Company optional field label
  ///
  /// In en, this message translates to:
  /// **'Company (Optional)'**
  String get companyOptional;

  /// Enter company name placeholder
  ///
  /// In en, this message translates to:
  /// **'Enter your company name'**
  String get enterYourCompanyName;

  /// Create password placeholder
  ///
  /// In en, this message translates to:
  /// **'Create a password'**
  String get createPassword;

  /// Please enter password validation
  ///
  /// In en, this message translates to:
  /// **'Please enter a password'**
  String get pleaseEnterPassword;

  /// Password minimum length validation
  ///
  /// In en, this message translates to:
  /// **'Password must be at least 8 characters'**
  String get passwordMinLength;

  /// Confirm password placeholder
  ///
  /// In en, this message translates to:
  /// **'Confirm your password'**
  String get confirmYourPassword;

  /// Please confirm password validation
  ///
  /// In en, this message translates to:
  /// **'Please confirm your password'**
  String get pleaseConfirmPassword;

  /// Passwords do not match validation
  ///
  /// In en, this message translates to:
  /// **'Passwords do not match'**
  String get passwordsDoNotMatch;

  /// I agree to the prefix
  ///
  /// In en, this message translates to:
  /// **'I agree to the'**
  String get iAgreeToThe;

  /// And conjunction
  ///
  /// In en, this message translates to:
  /// **'and'**
  String get and;

  /// Already have account text
  ///
  /// In en, this message translates to:
  /// **'Already have an account?'**
  String get alreadyHaveAccount;

  /// Sign in button
  ///
  /// In en, this message translates to:
  /// **'Sign In'**
  String get signIn;

  /// Please accept terms validation
  ///
  /// In en, this message translates to:
  /// **'Please accept the terms and conditions'**
  String get pleaseAcceptTerms;

  /// First onboarding screen title
  ///
  /// In en, this message translates to:
  /// **'AI-Powered Risk Assessment'**
  String get onboardingTitle1;

  /// First onboarding screen description
  ///
  /// In en, this message translates to:
  /// **'Upload insurance documents and get instant risk analysis with GO/NO-GO recommendations powered by the InstantRisk Engine'**
  String get onboardingDesc1;

  /// Second onboarding screen title
  ///
  /// In en, this message translates to:
  /// **'Smart Document Generation'**
  String get onboardingTitle2;

  /// Second onboarding screen description
  ///
  /// In en, this message translates to:
  /// **'Generate professional insurance documents, contracts, and clauses tailored to Lloyd\'s market standards'**
  String get onboardingDesc2;

  /// Third onboarding screen title
  ///
  /// In en, this message translates to:
  /// **'24/7 InstantRisk Assistant'**
  String get onboardingTitle3;

  /// Third onboarding screen description
  ///
  /// In en, this message translates to:
  /// **'Get instant answers to insurance questions from our AI trained on 20GB+ of Lloyd\'s market knowledge'**
  String get onboardingDesc3;

  /// Skip button
  ///
  /// In en, this message translates to:
  /// **'Skip'**
  String get skip;

  /// Get started button on onboarding
  ///
  /// In en, this message translates to:
  /// **'Get Started'**
  String get getStartedNow;
}

class _AppLocalizationsDelegate extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) => <String>['ar', 'de', 'en', 'es', 'fr', 'hi', 'it', 'ja', 'ko', 'nl', 'pt', 'zh'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {


  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'ar': return AppLocalizationsAr();
    case 'de': return AppLocalizationsDe();
    case 'en': return AppLocalizationsEn();
    case 'es': return AppLocalizationsEs();
    case 'fr': return AppLocalizationsFr();
    case 'hi': return AppLocalizationsHi();
    case 'it': return AppLocalizationsIt();
    case 'ja': return AppLocalizationsJa();
    case 'ko': return AppLocalizationsKo();
    case 'nl': return AppLocalizationsNl();
    case 'pt': return AppLocalizationsPt();
    case 'zh': return AppLocalizationsZh();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.'
  );
}
