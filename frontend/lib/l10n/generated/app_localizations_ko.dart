// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Korean (`ko`).
class AppLocalizationsKo extends AppLocalizations {
  AppLocalizationsKo([String locale = 'ko']) : super(locale);

  @override
  String get appName => 'InstantRisk';

  @override
  String get settings => '설정';

  @override
  String get language => '언어';

  @override
  String get languageSubtitle => '선호하는 언어를 선택하세요';

  @override
  String get languageChangeInfo => '선호하는 언어를 선택하세요. 저장하면 앱이 즉시 업데이트됩니다.';

  @override
  String get save => '저장';

  @override
  String get cancel => '취소';

  @override
  String get change => '변경';

  @override
  String get languageChanged => '언어가 성공적으로 변경되었습니다';

  @override
  String get home => '홈';

  @override
  String get reports => '보고서';

  @override
  String get chat => '채팅';

  @override
  String get analytics => '분석';

  @override
  String get documents => '문서';

  @override
  String get templates => '템플릿';

  @override
  String get profile => '프로필';

  @override
  String get profileSubtitle => '개인 정보 관리';

  @override
  String get subscription => '구독';

  @override
  String get subscriptionPlan => '프로페셔널 플랜';

  @override
  String get security => '보안';

  @override
  String get securitySubtitle => '비밀번호, 2FA, 세션';

  @override
  String get account => '계정';

  @override
  String get teamAdmin => '팀 및 관리';

  @override
  String get teamManagement => '팀 관리';

  @override
  String get teamManagementSubtitle => '팀, 구성원 및 역할 관리';

  @override
  String get rolesPermissions => '역할 및 권한';

  @override
  String get rolesPermissionsSubtitle => '접근 제어 구성';

  @override
  String get lloydsAdminDashboard => 'Lloyd\'s 관리자 대시보드';

  @override
  String get lloydsAdminSubtitle => '모든 신디케이트 및 시장 데이터 보기';

  @override
  String get lloydsMarket => 'Lloyd\'s 시장';

  @override
  String get syndicateDashboard => '신디케이트 대시보드';

  @override
  String get syndicateDashboardSubtitle => '신디케이트 지표 개요';

  @override
  String get placementBoard => '배치 보드';

  @override
  String get placementBoardSubtitle => '활성 배치 및 파이프라인';

  @override
  String get exposureDashboard => '익스포저 대시보드';

  @override
  String get exposureDashboardSubtitle => '위험 익스포저 분석';

  @override
  String get regulatoryCompliance => '규제 준수';

  @override
  String get regulatoryComplianceSubtitle => '보고서 및 준수 보고서';

  @override
  String get pricingEngine => '가격 책정 엔진';

  @override
  String get pricingEngineSubtitle => 'AI 기반 가격 책정 모델';

  @override
  String get dataQuality => '데이터 품질';

  @override
  String get dataQualitySubtitle => '데이터 검증 및 품질 지표';

  @override
  String get umrManagement => 'UMR 관리';

  @override
  String get umrManagementSubtitle => '고유 시장 참조 추적';

  @override
  String get appSettings => '앱 설정';

  @override
  String get documentRepository => '문서 저장소';

  @override
  String get documentRepositorySubtitle => '저장된 문서 관리';

  @override
  String get notifications => '알림';

  @override
  String get notificationsSubtitle => '푸시, 이메일, SMS 알림';

  @override
  String get appearance => '모양';

  @override
  String get appearanceSubtitle => '라이트 모드';

  @override
  String get support => '지원';

  @override
  String get helpCenter => '도움말 센터';

  @override
  String get helpCenterSubtitle => 'FAQ 및 가이드';

  @override
  String get contactSupport => '지원 문의';

  @override
  String get contactSupportSubtitle => '팀에서 도움 받기';

  @override
  String get reportBug => '버그 신고';

  @override
  String get reportBugSubtitle => '개선에 도움주기';

  @override
  String get about => '정보';

  @override
  String get aboutInstantRisk => 'InstantRisk 정보';

  @override
  String version(String version) {
    return '버전 $version';
  }

  @override
  String get termsOfService => '서비스 약관';

  @override
  String get privacyPolicy => '개인정보 보호정책';

  @override
  String get logOut => '로그아웃';

  @override
  String get logOutConfirmation => 'InstantRisk에서 로그아웃하시겠습니까?';

  @override
  String get login => '로그인';

  @override
  String get register => '등록';

  @override
  String get email => '이메일';

  @override
  String get password => '비밀번호';

  @override
  String get forgotPassword => '비밀번호를 잊으셨나요?';

  @override
  String get welcomeBack => '다시 오신 것을 환영합니다';

  @override
  String get createAccount => '계정 만들기';

  @override
  String get fullName => '전체 이름';

  @override
  String get confirmPassword => '비밀번호 확인';

  @override
  String get dashboard => '대시보드';

  @override
  String get uploadDocument => '문서 업로드';

  @override
  String get recentAssessments => '최근 평가';

  @override
  String get viewAll => '전체 보기';

  @override
  String get processing => '처리 중';

  @override
  String get completed => '완료됨';

  @override
  String get failed => '실패';

  @override
  String get goDecision => '승인';

  @override
  String get noGoDecision => '거절';

  @override
  String get referDecision => '검토';

  @override
  String get riskScore => '위험 점수';

  @override
  String get overallRisk => '전체 위험';

  @override
  String get lowRisk => '낮은 위험';

  @override
  String get mediumRisk => '중간 위험';

  @override
  String get highRisk => '높은 위험';

  @override
  String get sanctions => '제재';

  @override
  String get sanctionsScreening => '제재 심사';

  @override
  String get noMatches => '일치 항목 없음';

  @override
  String potentialMatches(int count) {
    return '$count개의 잠재적 일치';
  }

  @override
  String get analysis => '분석';

  @override
  String get quickAnalysis => '빠른 분석';

  @override
  String get deepAnalysis => '심층 분석';

  @override
  String get startAnalysis => '분석 시작';

  @override
  String get analysisInProgress => '분석 진행 중';

  @override
  String get analysisComplete => '분석 완료';

  @override
  String get viewResults => '결과 보기';

  @override
  String get generateReport => '보고서 생성';

  @override
  String get downloadPdf => 'PDF 다운로드';

  @override
  String get share => '공유';

  @override
  String get error => '오류';

  @override
  String get tryAgain => '다시 시도';

  @override
  String get loading => '로딩 중...';

  @override
  String get noData => '데이터 없음';

  @override
  String get search => '검색';

  @override
  String get filter => '필터';

  @override
  String get sortBy => '정렬 기준';

  @override
  String get date => '날짜';

  @override
  String get name => '이름';

  @override
  String get status => '상태';

  @override
  String get type => '유형';

  @override
  String get actions => '작업';

  @override
  String get delete => '삭제';

  @override
  String get edit => '편집';

  @override
  String get view => '보기';

  @override
  String get confirm => '확인';

  @override
  String get yes => '예';

  @override
  String get no => '아니오';

  @override
  String get ok => '확인';

  @override
  String get close => '닫기';

  @override
  String get back => '뒤로';

  @override
  String get next => '다음';

  @override
  String get previous => '이전';

  @override
  String get submit => '제출';

  @override
  String get done => '완료';

  @override
  String get refresh => '새로고침';

  @override
  String get retry => '재시도';

  @override
  String get unsavedChanges => '저장되지 않은 변경 사항이 있습니다';

  @override
  String get discardChanges => '변경 사항 취소';

  @override
  String get saveChanges => '변경 사항 저장';

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
  String get backToDashboard => '대시보드로 돌아가기';

  @override
  String get noAiAnalysisYet => 'No AI analysis available yet.\nClick \"Analyze\" to generate risk insights.';

  @override
  String get clickCalculatePricing => 'Click \"Calculate\" to generate a technical premium for this risk.';

  @override
  String get pricingNotAvailableDeclined => 'Pricing not available for declined risks.';

  @override
  String get leaveAnalysis => '분석을 종료하시겠습니까?';

  @override
  String get stayHere => '여기에 머무르기';

  @override
  String get runInBackground => '백그라운드에서 실행';

  @override
  String get askAiAboutCategory => '이 카테고리에 대해 AI에게 질문';

  @override
  String get copy => '복사';

  @override
  String get analysisMode => '분석 모드';

  @override
  String get recommended => '추천';

  @override
  String get agents => '에이전트';

  @override
  String documentsToAnalyze(int count) {
    return '$count개 문서 분석 예정';
  }

  @override
  String get characters => '문자';

  @override
  String get analysisFailed => '분석 실패';

  @override
  String get goBack => '돌아가기';

  @override
  String get documentCenter => '문서 센터';

  @override
  String get createNewDocument => '새 문서 만들기';

  @override
  String get newDocument => '새 문서';

  @override
  String get recentDocuments => '최근 문서';

  @override
  String get templatesLibrary => '템플릿 라이브러리';

  @override
  String get browseByLineOfBusiness => '사업 분야별 찾아보기';

  @override
  String get assessmentDocuments => '평가 문서';

  @override
  String get noAssessmentsYet => '아직 평가 없음';

  @override
  String get uploadDocuments => '문서 업로드';

  @override
  String get searchDocuments => '문서 검색';

  @override
  String get getStarted => '시작하기';

  @override
  String get generate => '생성';

  @override
  String get uploaded => '업로드됨';

  @override
  String get generated => '생성됨';

  @override
  String get generateDocuments => '문서 생성';

  @override
  String get aiRecommendedDocuments => 'AI 추천 문서';

  @override
  String get selectDocumentsToGenerate => '생성할 문서 선택';

  @override
  String get lmaClauses => 'LMA 조항';

  @override
  String get selected => '선택됨';

  @override
  String get required => '필수';

  @override
  String get generatingDocuments => '문서 생성 중';

  @override
  String get aiAgentsWorking => 'AI 에이전트가 문서를 작업 중입니다';

  @override
  String get complete => '완료';

  @override
  String get liveActivity => '실시간 활동';

  @override
  String get initializing => '초기화 중...';

  @override
  String get documentsGeneratedSuccessfully => '문서가 성공적으로 생성되었습니다';

  @override
  String documentsReadyForReview(int count) {
    return '$count개 문서 검토 준비됨';
  }

  @override
  String get preview => '미리보기';

  @override
  String get finalize => '완료';

  @override
  String get generateMore => '더 생성';

  @override
  String get selectLineOfBusiness => '사업 분야 선택';

  @override
  String continueWith(String name) {
    return '$name으로 계속';
  }

  @override
  String get selectALineOfBusiness => '사업 분야를 선택하세요';

  @override
  String get documentLibrary => '문서 라이브러리';

  @override
  String get insuranceKnowledgeBase => '보험 지식 베이스';

  @override
  String get data => '데이터';

  @override
  String get categories => '카테고리';

  @override
  String get all => '전체';

  @override
  String get insurance => '보험';

  @override
  String get training => '교육';

  @override
  String get favorites => '즐겨찾기';

  @override
  String get noFavoritesYet => '아직 즐겨찾기 없음';

  @override
  String get noDocumentsFound => '문서를 찾을 수 없음';

  @override
  String get newChat => '새 채팅';

  @override
  String get aiAssistant => 'AI 어시스턴트';

  @override
  String get knowledgeSources => '지식 소스';

  @override
  String get copiedToClipboard => '클립보드에 복사됨';

  @override
  String get screeningLevels => '심사 레벨';

  @override
  String get screeningHistory => '심사 이력';

  @override
  String get run => '실행';

  @override
  String get liveFindings => '실시간 발견';

  @override
  String get analysisCanContinueInBackground => 'You can close this window. Analysis will continue in background and results will be available in Reports.';

  @override
  String get minimizeLiveResults => 'Minimize';

  @override
  String get expandLiveResults => 'Show Live Results';

  @override
  String get checks => '검사';

  @override
  String get pending => '대기 중';

  @override
  String get checking => '확인 중...';

  @override
  String get clear => '클리어';

  @override
  String get reviewRequired => '검토 필요';

  @override
  String get matchFound => '일치 발견';

  @override
  String get noEntitiesFound => '엔티티 없음';

  @override
  String get screeningResults => '심사 결과';

  @override
  String get viewFullResults => '전체 결과 보기';

  @override
  String get sections => '섹션';

  @override
  String get details => '세부 정보';

  @override
  String get coreSections => '핵심 섹션';

  @override
  String get exclusions => '면책 조항';

  @override
  String get conditions => '조건';

  @override
  String get insuredInformation => '피보험자 정보';

  @override
  String get coverageLimits => '보장 한도';

  @override
  String get premium => '보험료';

  @override
  String get generateDocument => '문서 생성';

  @override
  String get generatingYourDocument => '문서 생성 중';

  @override
  String get umrGenerate => '생성';

  @override
  String get umrRegistry => '레지스트리';

  @override
  String get umrValidation => '검증';

  @override
  String get multiAgentAnalysis => '다중 에이전트 분석';

  @override
  String get agentPipeline => '5-에이전트 파이프라인';

  @override
  String get overallProgress => '전체 진행률';

  @override
  String get documentClassifier => '문서 분류기';

  @override
  String get classifyingDocument => '문서 분류 중';

  @override
  String get identifyingDocumentType => '문서 유형 식별 및 보험 관련성 검증';

  @override
  String get dataExtractor => '데이터 추출기';

  @override
  String get extractingData => '데이터 추출 중';

  @override
  String get pullingInsuranceFields => '문서에서 모든 보험 필드 추출 중';

  @override
  String get riskAnalyst => '위험 분석가';

  @override
  String get analyzingRisks => '위험 분석 중';

  @override
  String get identifyingRiskFactors => '위험 요소 및 익스포저 식별';

  @override
  String get seniorUnderwriter => '시니어 언더라이터';

  @override
  String get underwritingDecision => '언더라이팅 결정';

  @override
  String get makingGoNoGoDecision => 'GO/NO-GO/REFER 권고 결정';

  @override
  String get qualityAssurance => '품질 보증';

  @override
  String get finalValidation => '최종 검증';

  @override
  String get ensuringAccuracy => '정확성 및 완전성 보장';

  @override
  String get newAssessment => '새 평가';

  @override
  String get aiPoweredAnalysis => 'AI 기반 분석';

  @override
  String get riskTypeAutoDetected => '위험 유형은 OCR 및 AI를 사용하여 문서에서 자동 감지됩니다';

  @override
  String get addDocuments => '문서 추가';

  @override
  String get uploadFromPhone => '휴대폰에서 업로드';

  @override
  String get scanQrWithPhone => '휴대폰으로 QR 스캔';

  @override
  String get usePhoneCamera => '휴대폰 카메라로 문서 촬영';

  @override
  String get takePhoto => '사진 촬영';

  @override
  String get captureWithCamera => '카메라로 문서 촬영';

  @override
  String get photoGallery => '사진 갤러리';

  @override
  String get selectFromPhotos => '사진에서 선택';

  @override
  String get browseFiles => '파일 찾아보기';

  @override
  String get pdfDocXlsAndMore => 'PDF, DOC, XLS 등';

  @override
  String get tapToAddDocuments => '문서를 추가하려면 탭하세요';

  @override
  String get takePhotoBrowseOrGallery => '사진 촬영, 파일 찾아보기 또는 갤러리에서 선택';

  @override
  String get uploadedDocuments => '업로드된 문서';

  @override
  String filesCount(int count) {
    return '$count개 파일';
  }

  @override
  String get recommendedDocuments => '추천 문서';

  @override
  String get applicationFormLossHistory => '신청서, 손실 이력, 재무제표, 이전 보험증권';

  @override
  String get startRiskAssessment => '위험 평가 시작';

  @override
  String get failedToCreateSession => '업로드 세션 생성 실패';

  @override
  String documentsReceived(int count) {
    return '$count개 문서 수신됨';
  }

  @override
  String get scanWithPhoneCamera => '휴대폰 카메라로 스캔하여\n문서를 촬영하고 업로드하세요';

  @override
  String documentsAddedFromPhone(int count) {
    return '휴대폰에서 $count개 문서 추가됨';
  }

  @override
  String get personalInformation => '개인 정보';

  @override
  String get professionalInformation => '직업 정보';

  @override
  String get company => '회사';

  @override
  String get role => '역할';

  @override
  String get phone => '전화';

  @override
  String get accountStatistics => '계정 통계';

  @override
  String get memberSince => '가입일';

  @override
  String get totalAssessments => '총 평가';

  @override
  String get contractsGenerated => '생성된 계약';

  @override
  String get lastLogin => '마지막 로그인';

  @override
  String get dangerZone => '위험 영역';

  @override
  String get deleteAccountWarning => '계정을 삭제하면 되돌릴 수 없습니다. 신중하게 결정하세요.';

  @override
  String get deleteAccount => '계정 삭제';

  @override
  String get profileUpdatedSuccessfully => '프로필이 성공적으로 업데이트되었습니다';

  @override
  String get thisFieldRequired => '이 필드는 필수입니다';

  @override
  String get deleteAccountConfirmation => '계정을 삭제하시겠습니까? 이 작업은 취소할 수 없으며 모든 데이터가 영구적으로 손실됩니다.';

  @override
  String get professionalPlan => '프로페셔널 플랜';

  @override
  String activeUntil(String date) {
    return '$date까지 활성';
  }

  @override
  String get active => '활성';

  @override
  String get thisMonthsUsage => '이번 달 사용량';

  @override
  String get assessments => '평가';

  @override
  String get contractGenerations => '계약 생성';

  @override
  String get aiChatMessages => 'AI 채팅 메시지';

  @override
  String get documentStorage => '문서 저장소';

  @override
  String get availablePlans => '이용 가능한 플랜';

  @override
  String get basic => '기본';

  @override
  String get enterprise => '기업';

  @override
  String get popular => '인기';

  @override
  String get current => '현재';

  @override
  String get perMonth => '/월';

  @override
  String assessmentsPerMonth(String count) {
    return '$count 평가/월';
  }

  @override
  String contractGenerationsCount(String count) {
    return '$count 계약 생성';
  }

  @override
  String aiChatMessagesCount(String count) {
    return '$count AI 채팅 메시지';
  }

  @override
  String documentStorageAmount(String amount) {
    return '$amount 문서 저장소';
  }

  @override
  String get emailSupport => '이메일 지원';

  @override
  String get prioritySupport => '우선 지원';

  @override
  String get advancedAnalytics => '고급 분석';

  @override
  String get dedicatedSupport => '24/7 전담 지원';

  @override
  String get customIntegrations => '맞춤 통합';

  @override
  String get whiteLabelOptions => '화이트 라벨 옵션';

  @override
  String get unlimited => '무제한';

  @override
  String get upgrade => '업그레이드';

  @override
  String get downgrade => '다운그레이드';

  @override
  String get billingHistory => '결제 이력';

  @override
  String visaEndingIn(String last4) {
    return '$last4로 끝나는 Visa';
  }

  @override
  String expires(String date) {
    return '만료 $date';
  }

  @override
  String get update => '업데이트';

  @override
  String get enterpriseEdition => '기업 에디션';

  @override
  String get goNoGoAnalysis => 'Go/No-Go 분석';

  @override
  String get approved => '승인됨';

  @override
  String get declined => '거절됨';

  @override
  String get refer => '검토';

  @override
  String get confidence => '신뢰도';

  @override
  String completedIn(String time) {
    return '$time에 완료';
  }

  @override
  String estimatedRemaining(String time) {
    return '예상: $time 남음';
  }

  @override
  String get agentsLabel => '에이전트';

  @override
  String get findingsLabel => '발견';

  @override
  String get doneStatus => '완료';

  @override
  String get runningStatus => '실행 중';

  @override
  String get pendingStatus => '대기 중';

  @override
  String get identifyDocumentType => '문서 유형 식별';

  @override
  String get extractInsuranceData => '보험 데이터 추출';

  @override
  String get analyzeRiskFactors => '위험 요소 분석';

  @override
  String get makeDecision => '결정 내리기';

  @override
  String get underwriter => '언더라이터';

  @override
  String get analysisRunningMessage => '분석이 진행 중입니다. 선택 가능:\n\n• 백그라운드 실행 - 분석 계속, 나중에 보고서에서 결과 확인\n• 여기에 머무르기 - 완료 대기';

  @override
  String get unexpectedError => '예상치 못한 오류가 발생했습니다';

  @override
  String get clauses => '조항';

  @override
  String get knowledge => '지식';

  @override
  String get languages => '언어';

  @override
  String get searchDocumentsClausesPolicies => '문서, 조항, 정책 검색...';

  @override
  String get docs => '문서';

  @override
  String get tapStarToFavorite => '즐겨찾기에 추가하려면 별 아이콘을 탭하세요';

  @override
  String get tryAdjustingSearch => '검색 또는 필터를 조정해 보세요';

  @override
  String get searchInThisCategory => '이 카테고리에서 검색...';

  @override
  String get noDocumentsMatchSearch => '검색과 일치하는 문서 없음';

  @override
  String get noDocumentsInCategory => '이 카테고리에 문서 없음';

  @override
  String get contentCopied => '내용 복사됨';

  @override
  String get pathCopiedToClipboard => '경로가 클립보드에 복사됨';

  @override
  String get resetPassword => '비밀번호 재설정';

  @override
  String get resetPasswordInstructions => '이메일 주소를 입력하시면 비밀번호 재설정 안내를 보내드립니다.';

  @override
  String get enterYourEmail => '이메일 입력';

  @override
  String get pleaseEnterYourEmail => '이메일을 입력해 주세요';

  @override
  String get pleaseEnterValidEmail => '유효한 이메일을 입력해 주세요';

  @override
  String get sendResetLink => '재설정 링크 보내기';

  @override
  String get backToSignIn => '로그인으로 돌아가기';

  @override
  String get checkYourEmail => '이메일을 확인하세요';

  @override
  String get passwordResetSentTo => '비밀번호 재설정 안내를 보냈습니다';

  @override
  String get didntReceiveEmailResend => '이메일을 받지 못하셨나요? 재발송';

  @override
  String get startRiskAssessmentJourney => '위험 평가 여정을 시작하세요';

  @override
  String get enterYourFullName => '전체 이름 입력';

  @override
  String get pleaseEnterYourName => '이름을 입력해 주세요';

  @override
  String get companyOptional => '회사 (선택 사항)';

  @override
  String get enterYourCompanyName => '회사명 입력';

  @override
  String get createPassword => '비밀번호 만들기';

  @override
  String get pleaseEnterPassword => '비밀번호를 입력해 주세요';

  @override
  String get passwordMinLength => '비밀번호는 최소 8자 이상이어야 합니다';

  @override
  String get confirmYourPassword => '비밀번호 확인';

  @override
  String get pleaseConfirmPassword => '비밀번호를 확인해 주세요';

  @override
  String get passwordsDoNotMatch => '비밀번호가 일치하지 않습니다';

  @override
  String get iAgreeToThe => '동의합니다';

  @override
  String get and => '및';

  @override
  String get alreadyHaveAccount => '이미 계정이 있으신가요?';

  @override
  String get signIn => '로그인';

  @override
  String get pleaseAcceptTerms => '이용약관에 동의해 주세요';

  @override
  String get onboardingTitle1 => 'AI 기반 위험 평가';

  @override
  String get onboardingDesc1 => '보험 문서를 업로드하고 GO/NO-GO 권장 사항과 함께 즉각적인 AI 기반 위험 분석을 받으세요';

  @override
  String get onboardingTitle2 => '스마트 문서 생성';

  @override
  String get onboardingDesc2 => 'Lloyd\'s 시장 표준에 맞춘 전문 보험 문서, 계약서 및 조항을 생성하세요';

  @override
  String get onboardingTitle3 => '24/7 보험 AI 어시스턴트';

  @override
  String get onboardingDesc3 => '20GB 이상의 Lloyd\'s 시장 지식으로 훈련된 AI로부터 보험 질문에 대한 즉각적인 답변을 받으세요';

  @override
  String get skip => '건너뛰기';

  @override
  String get getStartedNow => '시작하기';
}
