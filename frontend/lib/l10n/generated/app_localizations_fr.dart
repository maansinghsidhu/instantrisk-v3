// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for French (`fr`).
class AppLocalizationsFr extends AppLocalizations {
  AppLocalizationsFr([String locale = 'fr']) : super(locale);

  @override
  String get appName => 'InstantRisk';

  @override
  String get settings => 'Parametres';

  @override
  String get language => 'Langue';

  @override
  String get languageSubtitle => 'Choisissez votre langue preferee';

  @override
  String get languageChangeInfo => 'Choisissez votre langue preferee. L\'application se mettra a jour immediatement lors de l\'enregistrement.';

  @override
  String get save => 'Enregistrer';

  @override
  String get cancel => 'Annuler';

  @override
  String get change => 'Changer';

  @override
  String get languageChanged => 'Langue changee avec succes';

  @override
  String get home => 'Accueil';

  @override
  String get reports => 'Rapports';

  @override
  String get chat => 'Discussion';

  @override
  String get analytics => 'Analyses';

  @override
  String get documents => 'Documents';

  @override
  String get templates => 'Modeles';

  @override
  String get profile => 'Profil';

  @override
  String get profileSubtitle => 'Gerez vos informations personnelles';

  @override
  String get subscription => 'Abonnement';

  @override
  String get subscriptionPlan => 'Plan Professionnel';

  @override
  String get security => 'Securite';

  @override
  String get securitySubtitle => 'Mot de passe, 2FA, sessions';

  @override
  String get account => 'Compte';

  @override
  String get teamAdmin => 'Equipe & Administration';

  @override
  String get teamManagement => 'Gestion d\'equipe';

  @override
  String get teamManagementSubtitle => 'Gerez les equipes, membres et roles';

  @override
  String get rolesPermissions => 'Roles et Permissions';

  @override
  String get rolesPermissionsSubtitle => 'Configurez le controle d\'acces';

  @override
  String get lloydsAdminDashboard => 'Tableau de bord Admin Lloyd\'s';

  @override
  String get lloydsAdminSubtitle => 'Voir tous les syndicats et donnees du marche';

  @override
  String get lloydsMarket => 'Marche Lloyd\'s';

  @override
  String get syndicateDashboard => 'Tableau de bord Syndicat';

  @override
  String get syndicateDashboardSubtitle => 'Apercu des metriques du syndicat';

  @override
  String get placementBoard => 'Tableau des Placements';

  @override
  String get placementBoardSubtitle => 'Placements actifs et pipeline';

  @override
  String get exposureDashboard => 'Tableau de bord Exposition';

  @override
  String get exposureDashboardSubtitle => 'Analyse de l\'exposition aux risques';

  @override
  String get regulatoryCompliance => 'Conformite Reglementaire';

  @override
  String get regulatoryComplianceSubtitle => 'Declarations et rapports de conformite';

  @override
  String get pricingEngine => 'Moteur de Tarification';

  @override
  String get pricingEngineSubtitle => 'Modeles de tarification IA';

  @override
  String get dataQuality => 'Qualite des Donnees';

  @override
  String get dataQualitySubtitle => 'Validation et metriques de qualite';

  @override
  String get umrManagement => 'Gestion UMR';

  @override
  String get umrManagementSubtitle => 'Suivi des references marche uniques';

  @override
  String get appSettings => 'Parametres de l\'Application';

  @override
  String get documentRepository => 'Depot de Documents';

  @override
  String get documentRepositorySubtitle => 'Gerez les documents stockes';

  @override
  String get notifications => 'Notifications';

  @override
  String get notificationsSubtitle => 'Alertes push, email, SMS';

  @override
  String get appearance => 'Apparence';

  @override
  String get appearanceSubtitle => 'Mode clair';

  @override
  String get support => 'Support';

  @override
  String get helpCenter => 'Centre d\'aide';

  @override
  String get helpCenterSubtitle => 'FAQ et guides';

  @override
  String get contactSupport => 'Contacter le Support';

  @override
  String get contactSupportSubtitle => 'Obtenez de l\'aide de notre equipe';

  @override
  String get reportBug => 'Signaler un Bug';

  @override
  String get reportBugSubtitle => 'Aidez-nous a nous ameliorer';

  @override
  String get about => 'A propos';

  @override
  String get aboutInstantRisk => 'A propos d\'InstantRisk';

  @override
  String version(String version) {
    return 'Version $version';
  }

  @override
  String get termsOfService => 'Conditions d\'utilisation';

  @override
  String get privacyPolicy => 'Politique de confidentialite';

  @override
  String get logOut => 'Deconnexion';

  @override
  String get logOutConfirmation => 'Etes-vous sur de vouloir vous deconnecter d\'InstantRisk?';

  @override
  String get login => 'Connexion';

  @override
  String get register => 'S\'inscrire';

  @override
  String get email => 'Email';

  @override
  String get password => 'Mot de passe';

  @override
  String get forgotPassword => 'Mot de passe oublie?';

  @override
  String get welcomeBack => 'Bienvenue';

  @override
  String get createAccount => 'Creer un compte';

  @override
  String get fullName => 'Nom complet';

  @override
  String get confirmPassword => 'Confirmer le mot de passe';

  @override
  String get dashboard => 'Tableau de bord';

  @override
  String get uploadDocument => 'Telecharger un document';

  @override
  String get recentAssessments => 'Evaluations recentes';

  @override
  String get viewAll => 'Voir tout';

  @override
  String get processing => 'En cours';

  @override
  String get completed => 'Termine';

  @override
  String get failed => 'Echoue';

  @override
  String get goDecision => 'APPROUVE';

  @override
  String get noGoDecision => 'REFUSE';

  @override
  String get referDecision => 'A REVOIR';

  @override
  String get riskScore => 'Score de risque';

  @override
  String get overallRisk => 'Risque global';

  @override
  String get lowRisk => 'Risque faible';

  @override
  String get mediumRisk => 'Risque moyen';

  @override
  String get highRisk => 'Risque eleve';

  @override
  String get sanctions => 'Sanctions';

  @override
  String get sanctionsScreening => 'Verification des sanctions';

  @override
  String get noMatches => 'Aucune correspondance';

  @override
  String potentialMatches(int count) {
    return '$count correspondances potentielles';
  }

  @override
  String get analysis => 'Analyse';

  @override
  String get quickAnalysis => 'Analyse rapide';

  @override
  String get deepAnalysis => 'Analyse approfondie';

  @override
  String get startAnalysis => 'Demarrer l\'analyse';

  @override
  String get analysisInProgress => 'Analyse en cours';

  @override
  String get analysisComplete => 'Analyse terminee';

  @override
  String get viewResults => 'Voir les resultats';

  @override
  String get generateReport => 'Generer un rapport';

  @override
  String get downloadPdf => 'Telecharger PDF';

  @override
  String get share => 'Partager';

  @override
  String get error => 'Erreur';

  @override
  String get tryAgain => 'Reessayer';

  @override
  String get loading => 'Chargement...';

  @override
  String get noData => 'Aucune donnee disponible';

  @override
  String get search => 'Rechercher';

  @override
  String get filter => 'Filtrer';

  @override
  String get sortBy => 'Trier par';

  @override
  String get date => 'Date';

  @override
  String get name => 'Nom';

  @override
  String get status => 'Statut';

  @override
  String get type => 'Type';

  @override
  String get actions => 'Actions';

  @override
  String get delete => 'Supprimer';

  @override
  String get edit => 'Modifier';

  @override
  String get view => 'Voir';

  @override
  String get confirm => 'Confirmer';

  @override
  String get yes => 'Oui';

  @override
  String get no => 'Non';

  @override
  String get ok => 'OK';

  @override
  String get close => 'Fermer';

  @override
  String get back => 'Retour';

  @override
  String get next => 'Suivant';

  @override
  String get previous => 'Precedent';

  @override
  String get submit => 'Soumettre';

  @override
  String get done => 'Termine';

  @override
  String get refresh => 'Actualiser';

  @override
  String get retry => 'Reessayer';

  @override
  String get unsavedChanges => 'Vous avez des modifications non enregistrees';

  @override
  String get discardChanges => 'Annuler les modifications';

  @override
  String get saveChanges => 'Enregistrer les modifications';

  @override
  String get unsavedChangesPressSave => 'You have unsaved changes. Press Save to apply the new language.';

  @override
  String languageChangedTo(String languageName) {
    return 'Language changed to $languageName';
  }

  @override
  String get undo => 'Undo';

  @override
  String get saveLanguagePreference => 'Save Language Preference';

  @override
  String get failedToSaveLanguage => 'Failed to save language preference. Please try again.';

  @override
  String get discardChangesQuestion => 'Discard Changes?';

  @override
  String get discardChangesMessage => 'You have unsaved changes. Do you want to discard them?';

  @override
  String get discard => 'Discard';

  @override
  String get rtlLabel => 'RTL';

  @override
  String get backToDashboard => 'Retour au tableau de bord';

  @override
  String get noAiAnalysisYet => 'No AI analysis available yet.\nClick \"Analyze\" to generate risk insights.';

  @override
  String get clickCalculatePricing => 'Click \"Calculate\" to generate a technical premium for this risk.';

  @override
  String get pricingNotAvailableDeclined => 'Pricing not available for declined risks.';

  @override
  String get leaveAnalysis => 'Quitter l\'analyse?';

  @override
  String get stayHere => 'Rester ici';

  @override
  String get runInBackground => 'Executer en arriere-plan';

  @override
  String get askAiAboutCategory => 'Interroger l\'IA sur cette categorie';

  @override
  String get copy => 'Copier';

  @override
  String get analysisMode => 'Mode d\'analyse';

  @override
  String get recommended => 'RECOMMANDE';

  @override
  String get agents => 'agents';

  @override
  String documentsToAnalyze(int count) {
    return '$count document(s) a analyser';
  }

  @override
  String get characters => 'caracteres';

  @override
  String get analysisFailed => 'Analyse echouee';

  @override
  String get goBack => 'Retour';

  @override
  String get documentCenter => 'Centre de documents';

  @override
  String get createNewDocument => 'Creer un nouveau document';

  @override
  String get newDocument => 'Nouveau document';

  @override
  String get recentDocuments => 'Documents recents';

  @override
  String get templatesLibrary => 'Bibliotheque de modeles';

  @override
  String get browseByLineOfBusiness => 'Parcourir par branche d\'activite';

  @override
  String get assessmentDocuments => 'Documents d\'evaluation';

  @override
  String get noAssessmentsYet => 'Pas encore d\'evaluations';

  @override
  String get uploadDocuments => 'Telecharger des documents';

  @override
  String get searchDocuments => 'Rechercher des documents';

  @override
  String get getStarted => 'Commencer';

  @override
  String get generate => 'Generer';

  @override
  String get uploaded => 'Telecharge';

  @override
  String get generated => 'Genere';

  @override
  String get generateDocuments => 'Generer des documents';

  @override
  String get aiRecommendedDocuments => 'Documents recommandes par l\'IA';

  @override
  String get selectDocumentsToGenerate => 'Selectionnez les documents a generer';

  @override
  String get lmaClauses => 'Clauses LMA';

  @override
  String get selected => 'selectionne';

  @override
  String get required => 'REQUIS';

  @override
  String get generatingDocuments => 'Generation des documents';

  @override
  String get aiAgentsWorking => 'Les agents IA travaillent sur vos documents';

  @override
  String get complete => 'Termine';

  @override
  String get liveActivity => 'Activite en direct';

  @override
  String get initializing => 'Initialisation...';

  @override
  String get documentsGeneratedSuccessfully => 'Documents generes avec succes';

  @override
  String documentsReadyForReview(int count) {
    return '$count document(s) pret(s) pour revision';
  }

  @override
  String get preview => 'Apercu';

  @override
  String get finalize => 'Finaliser';

  @override
  String get generateMore => 'Generer plus';

  @override
  String get selectLineOfBusiness => 'Selectionner la branche d\'activite';

  @override
  String continueWith(String name) {
    return 'Continuer avec $name';
  }

  @override
  String get selectALineOfBusiness => 'Selectionnez une branche d\'activite';

  @override
  String get documentLibrary => 'Bibliotheque de documents';

  @override
  String get insuranceKnowledgeBase => 'Base de connaissances assurance';

  @override
  String get data => 'Donnees';

  @override
  String get categories => 'Categories';

  @override
  String get all => 'Tout';

  @override
  String get insurance => 'Assurance';

  @override
  String get training => 'Formation';

  @override
  String get favorites => 'Favoris';

  @override
  String get noFavoritesYet => 'Pas encore de favoris';

  @override
  String get noDocumentsFound => 'Aucun document trouve';

  @override
  String get newChat => 'Nouvelle discussion';

  @override
  String get aiAssistant => 'Assistant IA';

  @override
  String get knowledgeSources => 'Sources de connaissances';

  @override
  String get copiedToClipboard => 'Copie dans le presse-papiers';

  @override
  String get screeningLevels => 'NIVEAUX DE VERIFICATION';

  @override
  String get screeningHistory => 'HISTORIQUE DE VERIFICATION';

  @override
  String get run => 'Executer';

  @override
  String get liveFindings => 'RESULTATS EN DIRECT';

  @override
  String get analysisCanContinueInBackground => 'You can close this window. Analysis will continue in background and results will be available in Reports.';

  @override
  String get minimizeLiveResults => 'Minimize';

  @override
  String get expandLiveResults => 'Show Live Results';

  @override
  String get checks => 'VERIFICATIONS';

  @override
  String get pending => 'En attente';

  @override
  String get checking => 'Verification...';

  @override
  String get clear => 'AUCUN PROBLEME';

  @override
  String get reviewRequired => 'REVISION REQUISE';

  @override
  String get matchFound => 'CORRESPONDANCE TROUVEE';

  @override
  String get noEntitiesFound => 'AUCUNE ENTITE TROUVEE';

  @override
  String get screeningResults => 'RESULTATS DE VERIFICATION';

  @override
  String get viewFullResults => 'Voir les resultats complets';

  @override
  String get sections => 'Sections';

  @override
  String get details => 'Details';

  @override
  String get coreSections => 'Sections principales';

  @override
  String get exclusions => 'Exclusions';

  @override
  String get conditions => 'Conditions';

  @override
  String get insuredInformation => 'Informations de l\'assure';

  @override
  String get coverageLimits => 'Limites de couverture';

  @override
  String get premium => 'Prime';

  @override
  String get generateDocument => 'Generer le document';

  @override
  String get generatingYourDocument => 'Generation de votre document';

  @override
  String get umrGenerate => 'Generer';

  @override
  String get umrRegistry => 'Registre';

  @override
  String get umrValidation => 'Validation';

  @override
  String get multiAgentAnalysis => 'Analyse Multi-Agents';

  @override
  String get agentPipeline => 'Pipeline 5 Agents';

  @override
  String get overallProgress => 'Progression globale';

  @override
  String get documentClassifier => 'Classificateur de Documents';

  @override
  String get classifyingDocument => 'Classification du Document';

  @override
  String get identifyingDocumentType => 'Identification du type de document et validation de la pertinence assurance';

  @override
  String get dataExtractor => 'Extracteur de Donnees';

  @override
  String get extractingData => 'Extraction des Donnees';

  @override
  String get pullingInsuranceFields => 'Extraction de tous les champs d\'assurance du document';

  @override
  String get riskAnalyst => 'Analyste de Risques';

  @override
  String get analyzingRisks => 'Analyse des Risques';

  @override
  String get identifyingRiskFactors => 'Identification des facteurs de risque et des expositions';

  @override
  String get seniorUnderwriter => 'Souscripteur Senior';

  @override
  String get underwritingDecision => 'Decision de Souscription';

  @override
  String get makingGoNoGoDecision => 'Elaboration de la recommandation GO/NO-GO/REFER';

  @override
  String get qualityAssurance => 'Assurance Qualite';

  @override
  String get finalValidation => 'Validation Finale';

  @override
  String get ensuringAccuracy => 'Garantir l\'exactitude et l\'exhaustivite';

  @override
  String get newAssessment => 'Nouvelle Evaluation';

  @override
  String get aiPoweredAnalysis => 'Analyse IA';

  @override
  String get riskTypeAutoDetected => 'Le type de risque sera automatiquement detecte a partir de vos documents via OCR et IA';

  @override
  String get addDocuments => 'Ajouter des Documents';

  @override
  String get uploadFromPhone => 'Telecharger depuis le telephone';

  @override
  String get scanQrWithPhone => 'Scanner le QR avec le telephone';

  @override
  String get usePhoneCamera => 'Utiliser la camera du telephone pour capturer des documents';

  @override
  String get takePhoto => 'Prendre une Photo';

  @override
  String get captureWithCamera => 'Capturer le document avec la camera';

  @override
  String get photoGallery => 'Galerie Photos';

  @override
  String get selectFromPhotos => 'Selectionner parmi vos photos';

  @override
  String get browseFiles => 'Parcourir les Fichiers';

  @override
  String get pdfDocXlsAndMore => 'PDF, DOC, XLS et plus';

  @override
  String get tapToAddDocuments => 'Appuyez pour ajouter des documents';

  @override
  String get takePhotoBrowseOrGallery => 'Prendre une photo, parcourir les fichiers ou selectionner dans la galerie';

  @override
  String get uploadedDocuments => 'Documents Telecharges';

  @override
  String filesCount(int count) {
    return '$count fichier(s)';
  }

  @override
  String get recommendedDocuments => 'Documents Recommandes';

  @override
  String get applicationFormLossHistory => 'Formulaire de demande, Historique des sinistres, Etats financiers, Police precedente';

  @override
  String get startRiskAssessment => 'Demarrer l\'Evaluation des Risques';

  @override
  String get failedToCreateSession => 'Echec de la creation de la session de telechargement';

  @override
  String documentsReceived(int count) {
    return '$count document(s) recu(s)';
  }

  @override
  String get scanWithPhoneCamera => 'Scannez avec la camera de votre telephone\npour capturer et telecharger des documents';

  @override
  String documentsAddedFromPhone(int count) {
    return '$count document(s) ajoute(s) depuis le telephone';
  }

  @override
  String get personalInformation => 'Informations Personnelles';

  @override
  String get professionalInformation => 'Informations Professionnelles';

  @override
  String get company => 'Entreprise';

  @override
  String get role => 'Role';

  @override
  String get phone => 'Telephone';

  @override
  String get accountStatistics => 'Statistiques du Compte';

  @override
  String get memberSince => 'Membre depuis';

  @override
  String get totalAssessments => 'Total des Evaluations';

  @override
  String get contractsGenerated => 'Contrats Generes';

  @override
  String get lastLogin => 'Derniere Connexion';

  @override
  String get dangerZone => 'Zone de Danger';

  @override
  String get deleteAccountWarning => 'Une fois votre compte supprime, il n\'y a pas de retour en arriere. Soyez certain.';

  @override
  String get deleteAccount => 'Supprimer le Compte';

  @override
  String get profileUpdatedSuccessfully => 'Profil mis a jour avec succes';

  @override
  String get thisFieldRequired => 'Ce champ est requis';

  @override
  String get deleteAccountConfirmation => 'Etes-vous sur de vouloir supprimer votre compte? Cette action est irreversible et toutes vos donnees seront definitivement perdues.';

  @override
  String get professionalPlan => 'Plan Professionnel';

  @override
  String activeUntil(String date) {
    return 'Actif jusqu\'au $date';
  }

  @override
  String get active => 'ACTIF';

  @override
  String get thisMonthsUsage => 'Utilisation ce Mois';

  @override
  String get assessments => 'Evaluations';

  @override
  String get contractGenerations => 'Generations de Contrats';

  @override
  String get aiChatMessages => 'Messages Chat IA';

  @override
  String get documentStorage => 'Stockage de Documents';

  @override
  String get availablePlans => 'Plans Disponibles';

  @override
  String get basic => 'Basique';

  @override
  String get enterprise => 'Entreprise';

  @override
  String get popular => 'POPULAIRE';

  @override
  String get current => 'ACTUEL';

  @override
  String get perMonth => '/mois';

  @override
  String assessmentsPerMonth(String count) {
    return '$count evaluations/mois';
  }

  @override
  String contractGenerationsCount(String count) {
    return '$count generations de contrats';
  }

  @override
  String aiChatMessagesCount(String count) {
    return '$count messages chat IA';
  }

  @override
  String documentStorageAmount(String amount) {
    return '$amount stockage de documents';
  }

  @override
  String get emailSupport => 'Support par email';

  @override
  String get prioritySupport => 'Support prioritaire';

  @override
  String get advancedAnalytics => 'Analyses avancees';

  @override
  String get dedicatedSupport => 'Support dedie 24/7';

  @override
  String get customIntegrations => 'Integrations personnalisees';

  @override
  String get whiteLabelOptions => 'Options marque blanche';

  @override
  String get unlimited => 'Illimite';

  @override
  String get upgrade => 'Ameliorer';

  @override
  String get downgrade => 'Retrograder';

  @override
  String get billingHistory => 'Historique de Facturation';

  @override
  String visaEndingIn(String last4) {
    return 'Visa se terminant par $last4';
  }

  @override
  String expires(String date) {
    return 'Expire le $date';
  }

  @override
  String get update => 'Mettre a jour';

  @override
  String get enterpriseEdition => 'EDITION ENTREPRISE';

  @override
  String get goNoGoAnalysis => 'Analyse Go/No-Go';

  @override
  String get approved => 'Approuve';

  @override
  String get declined => 'Refuse';

  @override
  String get refer => 'A referer';

  @override
  String get confidence => 'Confiance';

  @override
  String completedIn(String time) {
    return 'Termine en $time';
  }

  @override
  String estimatedRemaining(String time) {
    return 'Estime: $time restant';
  }

  @override
  String get agentsLabel => 'AGENTS';

  @override
  String get findingsLabel => 'RESULTATS';

  @override
  String get doneStatus => 'Termine';

  @override
  String get runningStatus => 'En cours';

  @override
  String get pendingStatus => 'En attente';

  @override
  String get identifyDocumentType => 'Identifier le type de document';

  @override
  String get extractInsuranceData => 'Extraire les donnees d\'assurance';

  @override
  String get analyzeRiskFactors => 'Analyser les facteurs de risque';

  @override
  String get makeDecision => 'Prendre une decision';

  @override
  String get underwriter => 'Souscripteur';

  @override
  String get analysisRunningMessage => 'L\'analyse est en cours. Vous pouvez:\n\n• Executer en arriere-plan - l\'analyse continue, verifier les resultats plus tard dans Rapports\n• Rester ici - attendre la fin';

  @override
  String get unexpectedError => 'Une erreur inattendue s\'est produite';

  @override
  String get clauses => 'Clauses';

  @override
  String get knowledge => 'Connaissance';

  @override
  String get languages => 'Langues';

  @override
  String get searchDocumentsClausesPolicies => 'Rechercher documents, clauses, polices...';

  @override
  String get docs => 'docs';

  @override
  String get tapStarToFavorite => 'Appuyez sur l\'icone etoile d\'une categorie pour l\'ajouter aux favoris';

  @override
  String get tryAdjustingSearch => 'Essayez d\'ajuster votre recherche ou filtre';

  @override
  String get searchInThisCategory => 'Rechercher dans cette categorie...';

  @override
  String get noDocumentsMatchSearch => 'Aucun document ne correspond a votre recherche';

  @override
  String get noDocumentsInCategory => 'Aucun document dans cette categorie';

  @override
  String get contentCopied => 'Contenu copie';

  @override
  String get pathCopiedToClipboard => 'Chemin copie dans le presse-papiers';

  @override
  String get resetPassword => 'Reinitialiser le Mot de Passe';

  @override
  String get resetPasswordInstructions => 'Entrez votre adresse email et nous vous enverrons des instructions pour reinitialiser votre mot de passe.';

  @override
  String get enterYourEmail => 'Entrez votre email';

  @override
  String get pleaseEnterYourEmail => 'Veuillez entrer votre email';

  @override
  String get pleaseEnterValidEmail => 'Veuillez entrer un email valide';

  @override
  String get sendResetLink => 'Envoyer le Lien';

  @override
  String get backToSignIn => 'Retour a la Connexion';

  @override
  String get checkYourEmail => 'Verifiez Votre Email';

  @override
  String get passwordResetSentTo => 'Nous avons envoye les instructions de reinitialisation a';

  @override
  String get didntReceiveEmailResend => 'Email non recu? Renvoyer';

  @override
  String get startRiskAssessmentJourney => 'Commencez votre parcours d\'evaluation des risques';

  @override
  String get enterYourFullName => 'Entrez votre nom complet';

  @override
  String get pleaseEnterYourName => 'Veuillez entrer votre nom';

  @override
  String get companyOptional => 'Entreprise (Optionnel)';

  @override
  String get enterYourCompanyName => 'Entrez le nom de votre entreprise';

  @override
  String get createPassword => 'Creer un mot de passe';

  @override
  String get pleaseEnterPassword => 'Veuillez entrer un mot de passe';

  @override
  String get passwordMinLength => 'Le mot de passe doit contenir au moins 8 caracteres';

  @override
  String get confirmYourPassword => 'Confirmez votre mot de passe';

  @override
  String get pleaseConfirmPassword => 'Veuillez confirmer votre mot de passe';

  @override
  String get passwordsDoNotMatch => 'Les mots de passe ne correspondent pas';

  @override
  String get iAgreeToThe => 'J\'accepte les';

  @override
  String get and => 'et';

  @override
  String get alreadyHaveAccount => 'Deja un compte?';

  @override
  String get signIn => 'Se Connecter';

  @override
  String get pleaseAcceptTerms => 'Veuillez accepter les conditions d\'utilisation';

  @override
  String get onboardingTitle1 => 'Évaluation des risques par IA';

  @override
  String get onboardingDesc1 => 'Téléchargez des documents d\'assurance et obtenez une analyse des risques instantanée avec des recommandations GO/NO-GO';

  @override
  String get onboardingTitle2 => 'Génération intelligente de documents';

  @override
  String get onboardingDesc2 => 'Générez des documents d\'assurance professionnels, des contrats et des clauses adaptés aux normes du marché Lloyd\'s';

  @override
  String get onboardingTitle3 => 'Assistant IA assurance 24/7';

  @override
  String get onboardingDesc3 => 'Obtenez des réponses instantanées à vos questions d\'assurance grâce à notre IA formée sur plus de 20 Go de connaissances Lloyd\'s';

  @override
  String get skip => 'Passer';

  @override
  String get getStartedNow => 'Commencer';
}
