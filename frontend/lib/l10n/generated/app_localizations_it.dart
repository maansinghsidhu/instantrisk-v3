// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Italian (`it`).
class AppLocalizationsIt extends AppLocalizations {
  AppLocalizationsIt([String locale = 'it']) : super(locale);

  @override
  String get appName => 'InstantRisk';

  @override
  String get settings => 'Impostazioni';

  @override
  String get language => 'Lingua';

  @override
  String get languageSubtitle => 'Scegli la tua lingua preferita';

  @override
  String get languageChangeInfo => 'Scegli la tua lingua preferita. L\'app si aggiornera immediatamente quando salvi.';

  @override
  String get save => 'Salva';

  @override
  String get cancel => 'Annulla';

  @override
  String get change => 'Cambia';

  @override
  String get languageChanged => 'Lingua cambiata con successo';

  @override
  String get home => 'Home';

  @override
  String get reports => 'Rapporti';

  @override
  String get chat => 'Chat';

  @override
  String get analytics => 'Analitica';

  @override
  String get documents => 'Documenti';

  @override
  String get templates => 'Modelli';

  @override
  String get profile => 'Profilo';

  @override
  String get profileSubtitle => 'Gestisci le tue informazioni personali';

  @override
  String get subscription => 'Abbonamento';

  @override
  String get subscriptionPlan => 'Piano Professionale';

  @override
  String get security => 'Sicurezza';

  @override
  String get securitySubtitle => 'Password, 2FA, sessioni';

  @override
  String get account => 'Account';

  @override
  String get teamAdmin => 'Team e Amministrazione';

  @override
  String get teamManagement => 'Gestione Team';

  @override
  String get teamManagementSubtitle => 'Gestisci team, membri e ruoli';

  @override
  String get rolesPermissions => 'Ruoli e Permessi';

  @override
  String get rolesPermissionsSubtitle => 'Configura il controllo degli accessi';

  @override
  String get lloydsAdminDashboard => 'Dashboard Admin Lloyd\'s';

  @override
  String get lloydsAdminSubtitle => 'Visualizza tutti i sindacati e i dati di mercato';

  @override
  String get lloydsMarket => 'Mercato Lloyd\'s';

  @override
  String get syndicateDashboard => 'Dashboard Sindacato';

  @override
  String get syndicateDashboardSubtitle => 'Panoramica delle metriche del sindacato';

  @override
  String get placementBoard => 'Bacheca Piazzamenti';

  @override
  String get placementBoardSubtitle => 'Piazzamenti attivi e pipeline';

  @override
  String get exposureDashboard => 'Dashboard Esposizione';

  @override
  String get exposureDashboardSubtitle => 'Analisi dell\'esposizione al rischio';

  @override
  String get regulatoryCompliance => 'Conformita Normativa';

  @override
  String get regulatoryComplianceSubtitle => 'Report di conformita';

  @override
  String get pricingEngine => 'Motore di Pricing';

  @override
  String get pricingEngineSubtitle => 'Modelli di pricing basati su IA';

  @override
  String get dataQuality => 'Qualita dei Dati';

  @override
  String get dataQualitySubtitle => 'Validazione e metriche di qualita dei dati';

  @override
  String get umrManagement => 'Gestione UMR';

  @override
  String get umrManagementSubtitle => 'Tracciamento Unique Market Reference';

  @override
  String get appSettings => 'Impostazioni App';

  @override
  String get documentRepository => 'Archivio Documenti';

  @override
  String get documentRepositorySubtitle => 'Gestisci i documenti archiviati';

  @override
  String get notifications => 'Notifiche';

  @override
  String get notificationsSubtitle => 'Avvisi push, email, SMS';

  @override
  String get appearance => 'Aspetto';

  @override
  String get appearanceSubtitle => 'Modalita chiara';

  @override
  String get support => 'Supporto';

  @override
  String get helpCenter => 'Centro Assistenza';

  @override
  String get helpCenterSubtitle => 'FAQ e guide';

  @override
  String get contactSupport => 'Contatta il Supporto';

  @override
  String get contactSupportSubtitle => 'Ottieni aiuto dal nostro team';

  @override
  String get reportBug => 'Segnala un Bug';

  @override
  String get reportBugSubtitle => 'Aiutaci a migliorare';

  @override
  String get about => 'Info';

  @override
  String get aboutInstantRisk => 'Info su InstantRisk';

  @override
  String version(String version) {
    return 'Versione $version';
  }

  @override
  String get termsOfService => 'Termini di Servizio';

  @override
  String get privacyPolicy => 'Informativa sulla Privacy';

  @override
  String get logOut => 'Esci';

  @override
  String get logOutConfirmation => 'Sei sicuro di voler uscire da InstantRisk?';

  @override
  String get login => 'Accedi';

  @override
  String get register => 'Registrati';

  @override
  String get email => 'Email';

  @override
  String get password => 'Password';

  @override
  String get forgotPassword => 'Password dimenticata?';

  @override
  String get welcomeBack => 'Bentornato';

  @override
  String get createAccount => 'Crea Account';

  @override
  String get fullName => 'Nome Completo';

  @override
  String get confirmPassword => 'Conferma Password';

  @override
  String get dashboard => 'Dashboard';

  @override
  String get uploadDocument => 'Carica Documento';

  @override
  String get recentAssessments => 'Valutazioni Recenti';

  @override
  String get viewAll => 'Vedi Tutto';

  @override
  String get processing => 'In Elaborazione';

  @override
  String get completed => 'Completato';

  @override
  String get failed => 'Fallito';

  @override
  String get goDecision => 'VIA';

  @override
  String get noGoDecision => 'STOP';

  @override
  String get referDecision => 'RIFERISCI';

  @override
  String get riskScore => 'Punteggio di Rischio';

  @override
  String get overallRisk => 'Rischio Complessivo';

  @override
  String get lowRisk => 'Rischio Basso';

  @override
  String get mediumRisk => 'Rischio Medio';

  @override
  String get highRisk => 'Rischio Alto';

  @override
  String get sanctions => 'Sanzioni';

  @override
  String get sanctionsScreening => 'Screening Sanzioni';

  @override
  String get noMatches => 'Nessuna Corrispondenza';

  @override
  String potentialMatches(int count) {
    return '$count Corrispondenze Potenziali';
  }

  @override
  String get analysis => 'Analisi';

  @override
  String get quickAnalysis => 'Analisi Rapida';

  @override
  String get deepAnalysis => 'Analisi Approfondita';

  @override
  String get startAnalysis => 'Avvia Analisi';

  @override
  String get analysisInProgress => 'Analisi in Corso';

  @override
  String get analysisComplete => 'Analisi Completata';

  @override
  String get viewResults => 'Vedi Risultati';

  @override
  String get generateReport => 'Genera Rapporto';

  @override
  String get downloadPdf => 'Scarica PDF';

  @override
  String get share => 'Condividi';

  @override
  String get error => 'Errore';

  @override
  String get tryAgain => 'Riprova';

  @override
  String get loading => 'Caricamento...';

  @override
  String get noData => 'Nessun dato disponibile';

  @override
  String get search => 'Cerca';

  @override
  String get filter => 'Filtra';

  @override
  String get sortBy => 'Ordina per';

  @override
  String get date => 'Data';

  @override
  String get name => 'Nome';

  @override
  String get status => 'Stato';

  @override
  String get type => 'Tipo';

  @override
  String get actions => 'Azioni';

  @override
  String get delete => 'Elimina';

  @override
  String get edit => 'Modifica';

  @override
  String get view => 'Visualizza';

  @override
  String get confirm => 'Conferma';

  @override
  String get yes => 'Si';

  @override
  String get no => 'No';

  @override
  String get ok => 'OK';

  @override
  String get close => 'Chiudi';

  @override
  String get back => 'Indietro';

  @override
  String get next => 'Avanti';

  @override
  String get previous => 'Precedente';

  @override
  String get submit => 'Invia';

  @override
  String get done => 'Fatto';

  @override
  String get refresh => 'Aggiorna';

  @override
  String get retry => 'Riprova';

  @override
  String get unsavedChanges => 'Hai modifiche non salvate';

  @override
  String get discardChanges => 'Scarta Modifiche';

  @override
  String get saveChanges => 'Salva Modifiche';

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
  String get backToDashboard => 'Torna alla Dashboard';

  @override
  String get noAiAnalysisYet => 'No AI analysis available yet.\nClick \"Analyze\" to generate risk insights.';

  @override
  String get clickCalculatePricing => 'Click \"Calculate\" to generate a technical premium for this risk.';

  @override
  String get pricingNotAvailableDeclined => 'Pricing not available for declined risks.';

  @override
  String get leaveAnalysis => 'Uscire dall\'analisi?';

  @override
  String get stayHere => 'Resta qui';

  @override
  String get runInBackground => 'Esegui in background';

  @override
  String get askAiAboutCategory => 'Chiedi all\'IA di questa categoria';

  @override
  String get copy => 'Copia';

  @override
  String get analysisMode => 'Modalita di analisi';

  @override
  String get recommended => 'CONSIGLIATO';

  @override
  String get agents => 'agenti';

  @override
  String documentsToAnalyze(int count) {
    return '$count documento(i) da analizzare';
  }

  @override
  String get characters => 'caratteri';

  @override
  String get analysisFailed => 'Analisi fallita';

  @override
  String get goBack => 'Torna indietro';

  @override
  String get documentCenter => 'Centro documenti';

  @override
  String get createNewDocument => 'Crea nuovo documento';

  @override
  String get newDocument => 'Nuovo documento';

  @override
  String get recentDocuments => 'Documenti recenti';

  @override
  String get templatesLibrary => 'Libreria modelli';

  @override
  String get browseByLineOfBusiness => 'Sfoglia per linea di business';

  @override
  String get assessmentDocuments => 'Documenti di valutazione';

  @override
  String get noAssessmentsYet => 'Nessuna valutazione ancora';

  @override
  String get uploadDocuments => 'Carica documenti';

  @override
  String get searchDocuments => 'Cerca documenti';

  @override
  String get getStarted => 'Inizia';

  @override
  String get generate => 'Genera';

  @override
  String get uploaded => 'Caricato';

  @override
  String get generated => 'Generato';

  @override
  String get generateDocuments => 'Genera documenti';

  @override
  String get aiRecommendedDocuments => 'Documenti raccomandati dall\'IA';

  @override
  String get selectDocumentsToGenerate => 'Seleziona i documenti da generare';

  @override
  String get lmaClauses => 'Clausole LMA';

  @override
  String get selected => 'selezionato';

  @override
  String get required => 'RICHIESTO';

  @override
  String get generatingDocuments => 'Generazione documenti';

  @override
  String get aiAgentsWorking => 'Gli agenti IA stanno lavorando sui tuoi documenti';

  @override
  String get complete => 'Completato';

  @override
  String get liveActivity => 'Attivita in diretta';

  @override
  String get initializing => 'Inizializzazione...';

  @override
  String get documentsGeneratedSuccessfully => 'Documenti generati con successo';

  @override
  String documentsReadyForReview(int count) {
    return '$count documento(i) pronto(i) per la revisione';
  }

  @override
  String get preview => 'Anteprima';

  @override
  String get finalize => 'Finalizza';

  @override
  String get generateMore => 'Genera altri';

  @override
  String get selectLineOfBusiness => 'Seleziona linea di business';

  @override
  String continueWith(String name) {
    return 'Continua con $name';
  }

  @override
  String get selectALineOfBusiness => 'Seleziona una linea di business';

  @override
  String get documentLibrary => 'Libreria documenti';

  @override
  String get insuranceKnowledgeBase => 'Base di conoscenza assicurativa';

  @override
  String get data => 'Dati';

  @override
  String get categories => 'Categorie';

  @override
  String get all => 'Tutto';

  @override
  String get insurance => 'Assicurazione';

  @override
  String get training => 'Formazione';

  @override
  String get favorites => 'Preferiti';

  @override
  String get noFavoritesYet => 'Nessun preferito ancora';

  @override
  String get noDocumentsFound => 'Nessun documento trovato';

  @override
  String get newChat => 'Nuova chat';

  @override
  String get aiAssistant => 'Assistente IA';

  @override
  String get knowledgeSources => 'Fonti di conoscenza';

  @override
  String get copiedToClipboard => 'Copiato negli appunti';

  @override
  String get screeningLevels => 'LIVELLI DI SCREENING';

  @override
  String get screeningHistory => 'CRONOLOGIA SCREENING';

  @override
  String get run => 'Esegui';

  @override
  String get liveFindings => 'RISULTATI IN DIRETTA';

  @override
  String get analysisCanContinueInBackground => 'You can close this window. Analysis will continue in background and results will be available in Reports.';

  @override
  String get minimizeLiveResults => 'Minimize';

  @override
  String get expandLiveResults => 'Show Live Results';

  @override
  String get checks => 'CONTROLLI';

  @override
  String get pending => 'In attesa';

  @override
  String get checking => 'Verifica...';

  @override
  String get clear => 'PULITO';

  @override
  String get reviewRequired => 'REVISIONE RICHIESTA';

  @override
  String get matchFound => 'CORRISPONDENZA TROVATA';

  @override
  String get noEntitiesFound => 'NESSUNA ENTITA TROVATA';

  @override
  String get screeningResults => 'RISULTATI SCREENING';

  @override
  String get viewFullResults => 'Vedi risultati completi';

  @override
  String get sections => 'Sezioni';

  @override
  String get details => 'Dettagli';

  @override
  String get coreSections => 'Sezioni principali';

  @override
  String get exclusions => 'Esclusioni';

  @override
  String get conditions => 'Condizioni';

  @override
  String get insuredInformation => 'Informazioni assicurato';

  @override
  String get coverageLimits => 'Limiti di copertura';

  @override
  String get premium => 'Premio';

  @override
  String get generateDocument => 'Genera documento';

  @override
  String get generatingYourDocument => 'Generazione del tuo documento';

  @override
  String get umrGenerate => 'Genera';

  @override
  String get umrRegistry => 'Registro';

  @override
  String get umrValidation => 'Validazione';

  @override
  String get multiAgentAnalysis => 'Analisi Multi-Agente';

  @override
  String get agentPipeline => 'Pipeline 5 Agenti';

  @override
  String get overallProgress => 'Progresso Generale';

  @override
  String get documentClassifier => 'Classificatore Documenti';

  @override
  String get classifyingDocument => 'Classificazione Documento';

  @override
  String get identifyingDocumentType => 'Identificazione tipo documento e validazione pertinenza assicurativa';

  @override
  String get dataExtractor => 'Estrattore Dati';

  @override
  String get extractingData => 'Estrazione Dati';

  @override
  String get pullingInsuranceFields => 'Estrazione di tutti i campi assicurativi dal documento';

  @override
  String get riskAnalyst => 'Analista Rischi';

  @override
  String get analyzingRisks => 'Analisi Rischi';

  @override
  String get identifyingRiskFactors => 'Identificazione fattori di rischio ed esposizioni';

  @override
  String get seniorUnderwriter => 'Sottoscrittore Senior';

  @override
  String get underwritingDecision => 'Decisione di Sottoscrizione';

  @override
  String get makingGoNoGoDecision => 'Elaborazione raccomandazione VIA/STOP/RIFERISCI';

  @override
  String get qualityAssurance => 'Garanzia Qualita';

  @override
  String get finalValidation => 'Validazione Finale';

  @override
  String get ensuringAccuracy => 'Garantire accuratezza e completezza';

  @override
  String get newAssessment => 'Nuova Valutazione';

  @override
  String get aiPoweredAnalysis => 'Analisi IA';

  @override
  String get riskTypeAutoDetected => 'Il tipo di rischio sara rilevato automaticamente dai tuoi documenti usando OCR e IA';

  @override
  String get addDocuments => 'Aggiungi Documenti';

  @override
  String get uploadFromPhone => 'Carica da telefono';

  @override
  String get scanQrWithPhone => 'Scansiona QR con telefono';

  @override
  String get usePhoneCamera => 'Usa la fotocamera del telefono per acquisire documenti';

  @override
  String get takePhoto => 'Scatta Foto';

  @override
  String get captureWithCamera => 'Acquisisci documento con fotocamera';

  @override
  String get photoGallery => 'Galleria Foto';

  @override
  String get selectFromPhotos => 'Seleziona dalle tue foto';

  @override
  String get browseFiles => 'Sfoglia File';

  @override
  String get pdfDocXlsAndMore => 'PDF, DOC, XLS e altro';

  @override
  String get tapToAddDocuments => 'Tocca per aggiungere documenti';

  @override
  String get takePhotoBrowseOrGallery => 'Scatta foto, sfoglia file o seleziona dalla galleria';

  @override
  String get uploadedDocuments => 'Documenti Caricati';

  @override
  String filesCount(int count) {
    return '$count file';
  }

  @override
  String get recommendedDocuments => 'Documenti Consigliati';

  @override
  String get applicationFormLossHistory => 'Modulo domanda, Storico sinistri, Bilanci, Polizza precedente';

  @override
  String get startRiskAssessment => 'Avvia Valutazione Rischio';

  @override
  String get failedToCreateSession => 'Impossibile creare sessione di caricamento';

  @override
  String documentsReceived(int count) {
    return '$count documento(i) ricevuto(i)';
  }

  @override
  String get scanWithPhoneCamera => 'Scansiona con la fotocamera del telefono\nper acquisire e caricare documenti';

  @override
  String documentsAddedFromPhone(int count) {
    return '$count documento(i) aggiunto(i) da telefono';
  }

  @override
  String get personalInformation => 'Informazioni Personali';

  @override
  String get professionalInformation => 'Informazioni Professionali';

  @override
  String get company => 'Azienda';

  @override
  String get role => 'Ruolo';

  @override
  String get phone => 'Telefono';

  @override
  String get accountStatistics => 'Statistiche Account';

  @override
  String get memberSince => 'Membro dal';

  @override
  String get totalAssessments => 'Valutazioni Totali';

  @override
  String get contractsGenerated => 'Contratti Generati';

  @override
  String get lastLogin => 'Ultimo Accesso';

  @override
  String get dangerZone => 'Zona Pericolosa';

  @override
  String get deleteAccountWarning => 'Una volta eliminato il tuo account, non si torna indietro. Per favore sii certo.';

  @override
  String get deleteAccount => 'Elimina Account';

  @override
  String get profileUpdatedSuccessfully => 'Profilo aggiornato con successo';

  @override
  String get thisFieldRequired => 'Questo campo e obbligatorio';

  @override
  String get deleteAccountConfirmation => 'Sei sicuro di voler eliminare il tuo account? Questa azione non puo essere annullata e tutti i tuoi dati saranno persi definitivamente.';

  @override
  String get professionalPlan => 'Piano Professionale';

  @override
  String activeUntil(String date) {
    return 'Attivo fino al $date';
  }

  @override
  String get active => 'ATTIVO';

  @override
  String get thisMonthsUsage => 'Utilizzo di Questo Mese';

  @override
  String get assessments => 'Valutazioni';

  @override
  String get contractGenerations => 'Generazioni Contratti';

  @override
  String get aiChatMessages => 'Messaggi Chat IA';

  @override
  String get documentStorage => 'Archiviazione Documenti';

  @override
  String get availablePlans => 'Piani Disponibili';

  @override
  String get basic => 'Base';

  @override
  String get enterprise => 'Enterprise';

  @override
  String get popular => 'POPOLARE';

  @override
  String get current => 'ATTUALE';

  @override
  String get perMonth => '/mese';

  @override
  String assessmentsPerMonth(String count) {
    return '$count valutazioni/mese';
  }

  @override
  String contractGenerationsCount(String count) {
    return '$count generazioni contratti';
  }

  @override
  String aiChatMessagesCount(String count) {
    return '$count messaggi chat IA';
  }

  @override
  String documentStorageAmount(String amount) {
    return '$amount archiviazione documenti';
  }

  @override
  String get emailSupport => 'Supporto email';

  @override
  String get prioritySupport => 'Supporto prioritario';

  @override
  String get advancedAnalytics => 'Analitiche avanzate';

  @override
  String get dedicatedSupport => 'Supporto dedicato 24/7';

  @override
  String get customIntegrations => 'Integrazioni personalizzate';

  @override
  String get whiteLabelOptions => 'Opzioni white-label';

  @override
  String get unlimited => 'Illimitato';

  @override
  String get upgrade => 'Aggiorna';

  @override
  String get downgrade => 'Declassa';

  @override
  String get billingHistory => 'Storico Fatturazione';

  @override
  String visaEndingIn(String last4) {
    return 'Visa che termina con $last4';
  }

  @override
  String expires(String date) {
    return 'Scade $date';
  }

  @override
  String get update => 'Aggiorna';

  @override
  String get enterpriseEdition => 'EDIZIONE ENTERPRISE';

  @override
  String get goNoGoAnalysis => 'Analisi Via/Stop';

  @override
  String get approved => 'Approvato';

  @override
  String get declined => 'Rifiutato';

  @override
  String get refer => 'Riferisci';

  @override
  String get confidence => 'Confidenza';

  @override
  String completedIn(String time) {
    return 'Completato in $time';
  }

  @override
  String estimatedRemaining(String time) {
    return 'Stimato: $time rimanente';
  }

  @override
  String get agentsLabel => 'AGENTI';

  @override
  String get findingsLabel => 'RISULTATI';

  @override
  String get doneStatus => 'Fatto';

  @override
  String get runningStatus => 'In esecuzione';

  @override
  String get pendingStatus => 'In attesa';

  @override
  String get identifyDocumentType => 'Identifica tipo documento';

  @override
  String get extractInsuranceData => 'Estrai dati assicurativi';

  @override
  String get analyzeRiskFactors => 'Analizza fattori di rischio';

  @override
  String get makeDecision => 'Prendi decisione';

  @override
  String get underwriter => 'Sottoscrittore';

  @override
  String get analysisRunningMessage => 'L\'analisi e in esecuzione. Puoi:\n\n• Eseguire in background - l\'analisi continua, controlla i risultati in Rapporti\n• Restare qui - attendi il completamento';

  @override
  String get unexpectedError => 'Si e verificato un errore imprevisto';

  @override
  String get clauses => 'Clausole';

  @override
  String get knowledge => 'Conoscenza';

  @override
  String get languages => 'Lingue';

  @override
  String get searchDocumentsClausesPolicies => 'Cerca documenti, clausole, polizze...';

  @override
  String get docs => 'doc';

  @override
  String get tapStarToFavorite => 'Tocca l\'icona stella su qualsiasi categoria per aggiungerla ai preferiti';

  @override
  String get tryAdjustingSearch => 'Prova a modificare la ricerca o il filtro';

  @override
  String get searchInThisCategory => 'Cerca in questa categoria...';

  @override
  String get noDocumentsMatchSearch => 'Nessun documento corrisponde alla tua ricerca';

  @override
  String get noDocumentsInCategory => 'Nessun documento in questa categoria';

  @override
  String get contentCopied => 'Contenuto copiato';

  @override
  String get pathCopiedToClipboard => 'Percorso copiato negli appunti';

  @override
  String get resetPassword => 'Reimposta Password';

  @override
  String get resetPasswordInstructions => 'Inserisci il tuo indirizzo email e ti invieremo le istruzioni per reimpostare la password.';

  @override
  String get enterYourEmail => 'Inserisci la tua email';

  @override
  String get pleaseEnterYourEmail => 'Inserisci la tua email';

  @override
  String get pleaseEnterValidEmail => 'Inserisci un email valida';

  @override
  String get sendResetLink => 'Invia Link';

  @override
  String get backToSignIn => 'Torna al Login';

  @override
  String get checkYourEmail => 'Controlla la Tua Email';

  @override
  String get passwordResetSentTo => 'Abbiamo inviato le istruzioni per reimpostare la password a';

  @override
  String get didntReceiveEmailResend => 'Non hai ricevuto l\'email? Reinvia';

  @override
  String get startRiskAssessmentJourney => 'Inizia il tuo percorso di valutazione del rischio';

  @override
  String get enterYourFullName => 'Inserisci il tuo nome completo';

  @override
  String get pleaseEnterYourName => 'Inserisci il tuo nome';

  @override
  String get companyOptional => 'Azienda (Opzionale)';

  @override
  String get enterYourCompanyName => 'Inserisci il nome della tua azienda';

  @override
  String get createPassword => 'Crea una password';

  @override
  String get pleaseEnterPassword => 'Inserisci una password';

  @override
  String get passwordMinLength => 'La password deve essere di almeno 8 caratteri';

  @override
  String get confirmYourPassword => 'Conferma la tua password';

  @override
  String get pleaseConfirmPassword => 'Conferma la tua password';

  @override
  String get passwordsDoNotMatch => 'Le password non corrispondono';

  @override
  String get iAgreeToThe => 'Accetto i';

  @override
  String get and => 'e';

  @override
  String get alreadyHaveAccount => 'Hai gia un account?';

  @override
  String get signIn => 'Accedi';

  @override
  String get pleaseAcceptTerms => 'Accetta i termini e condizioni';

  @override
  String get onboardingTitle1 => 'Valutazione del rischio con IA';

  @override
  String get onboardingDesc1 => 'Carica documenti assicurativi e ottieni analisi del rischio istantanea con raccomandazioni GO/NO-GO';

  @override
  String get onboardingTitle2 => 'Generazione intelligente di documenti';

  @override
  String get onboardingDesc2 => 'Genera documenti assicurativi professionali, contratti e clausole secondo gli standard Lloyd\'s';

  @override
  String get onboardingTitle3 => 'Assistente IA assicurativo 24/7';

  @override
  String get onboardingDesc3 => 'Ottieni risposte immediate alle domande assicurative dalla nostra IA addestrata su oltre 20GB di conoscenze Lloyd\'s';

  @override
  String get skip => 'Salta';

  @override
  String get getStartedNow => 'Inizia';
}
