// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Chinese (`zh`).
class AppLocalizationsZh extends AppLocalizations {
  AppLocalizationsZh([String locale = 'zh']) : super(locale);

  @override
  String get appName => 'InstantRisk';

  @override
  String get settings => '设置';

  @override
  String get language => '语言';

  @override
  String get languageSubtitle => '选择您的首选语言';

  @override
  String get languageChangeInfo => '选择您的首选语言。保存后应用将立即更新。';

  @override
  String get save => '保存';

  @override
  String get cancel => '取消';

  @override
  String get change => '更改';

  @override
  String get languageChanged => '语言更改成功';

  @override
  String get home => '首页';

  @override
  String get reports => '报告';

  @override
  String get chat => '聊天';

  @override
  String get analytics => '分析';

  @override
  String get documents => '文档';

  @override
  String get templates => '模板';

  @override
  String get profile => '个人资料';

  @override
  String get profileSubtitle => '管理您的个人信息';

  @override
  String get subscription => '订阅';

  @override
  String get subscriptionPlan => '专业计划';

  @override
  String get security => '安全';

  @override
  String get securitySubtitle => '密码、双因素认证、会话';

  @override
  String get account => '账户';

  @override
  String get teamAdmin => '团队与管理';

  @override
  String get teamManagement => '团队管理';

  @override
  String get teamManagementSubtitle => '管理团队、成员和角色';

  @override
  String get rolesPermissions => '角色与权限';

  @override
  String get rolesPermissionsSubtitle => '配置访问控制';

  @override
  String get lloydsAdminDashboard => '劳合社管理仪表板';

  @override
  String get lloydsAdminSubtitle => '查看所有辛迪加和市场数据';

  @override
  String get lloydsMarket => '劳合社市场';

  @override
  String get syndicateDashboard => '辛迪加仪表板';

  @override
  String get syndicateDashboardSubtitle => '辛迪加指标概览';

  @override
  String get placementBoard => '配置看板';

  @override
  String get placementBoardSubtitle => '活跃配置和管道';

  @override
  String get exposureDashboard => '风险敞口仪表板';

  @override
  String get exposureDashboardSubtitle => '风险敞口分析';

  @override
  String get regulatoryCompliance => '监管合规';

  @override
  String get regulatoryComplianceSubtitle => '申报和合规报告';

  @override
  String get pricingEngine => '定价引擎';

  @override
  String get pricingEngineSubtitle => 'AI驱动的定价模型';

  @override
  String get dataQuality => '数据质量';

  @override
  String get dataQualitySubtitle => '数据验证和质量指标';

  @override
  String get umrManagement => 'UMR管理';

  @override
  String get umrManagementSubtitle => '唯一市场参考跟踪';

  @override
  String get appSettings => '应用设置';

  @override
  String get documentRepository => '文档存储库';

  @override
  String get documentRepositorySubtitle => '管理已存储的文档';

  @override
  String get notifications => '通知';

  @override
  String get notificationsSubtitle => '推送、邮件、短信提醒';

  @override
  String get appearance => '外观';

  @override
  String get appearanceSubtitle => '浅色模式';

  @override
  String get support => '支持';

  @override
  String get helpCenter => '帮助中心';

  @override
  String get helpCenterSubtitle => '常见问题和指南';

  @override
  String get contactSupport => '联系支持';

  @override
  String get contactSupportSubtitle => '从我们的团队获得帮助';

  @override
  String get reportBug => '报告错误';

  @override
  String get reportBugSubtitle => '帮助我们改进';

  @override
  String get about => '关于';

  @override
  String get aboutInstantRisk => '关于InstantRisk';

  @override
  String version(String version) {
    return '版本 $version';
  }

  @override
  String get termsOfService => '服务条款';

  @override
  String get privacyPolicy => '隐私政策';

  @override
  String get logOut => '退出登录';

  @override
  String get logOutConfirmation => '您确定要退出InstantRisk吗？';

  @override
  String get login => '登录';

  @override
  String get register => '注册';

  @override
  String get email => '电子邮件';

  @override
  String get password => '密码';

  @override
  String get forgotPassword => '忘记密码？';

  @override
  String get welcomeBack => '欢迎回来';

  @override
  String get createAccount => '创建账户';

  @override
  String get fullName => '全名';

  @override
  String get confirmPassword => '确认密码';

  @override
  String get dashboard => '仪表板';

  @override
  String get uploadDocument => '上传文档';

  @override
  String get recentAssessments => '最近的评估';

  @override
  String get viewAll => '查看全部';

  @override
  String get processing => '处理中';

  @override
  String get completed => '已完成';

  @override
  String get failed => '失败';

  @override
  String get goDecision => '通过';

  @override
  String get noGoDecision => '拒绝';

  @override
  String get referDecision => '转介';

  @override
  String get riskScore => '风险评分';

  @override
  String get overallRisk => '整体风险';

  @override
  String get lowRisk => '低风险';

  @override
  String get mediumRisk => '中等风险';

  @override
  String get highRisk => '高风险';

  @override
  String get sanctions => '制裁';

  @override
  String get sanctionsScreening => '制裁筛查';

  @override
  String get noMatches => '无匹配';

  @override
  String potentialMatches(int count) {
    return '$count个潜在匹配';
  }

  @override
  String get analysis => '分析';

  @override
  String get quickAnalysis => '快速分析';

  @override
  String get deepAnalysis => '深度分析';

  @override
  String get startAnalysis => '开始分析';

  @override
  String get analysisInProgress => '分析进行中';

  @override
  String get analysisComplete => '分析完成';

  @override
  String get viewResults => '查看结果';

  @override
  String get generateReport => '生成报告';

  @override
  String get downloadPdf => '下载PDF';

  @override
  String get share => '分享';

  @override
  String get error => '错误';

  @override
  String get tryAgain => '重试';

  @override
  String get loading => '加载中...';

  @override
  String get noData => '暂无数据';

  @override
  String get search => '搜索';

  @override
  String get filter => '筛选';

  @override
  String get sortBy => '排序方式';

  @override
  String get date => '日期';

  @override
  String get name => '名称';

  @override
  String get status => '状态';

  @override
  String get type => '类型';

  @override
  String get actions => '操作';

  @override
  String get delete => '删除';

  @override
  String get edit => '编辑';

  @override
  String get view => '查看';

  @override
  String get confirm => '确认';

  @override
  String get yes => '是';

  @override
  String get no => '否';

  @override
  String get ok => '确定';

  @override
  String get close => '关闭';

  @override
  String get back => '返回';

  @override
  String get next => '下一步';

  @override
  String get previous => '上一步';

  @override
  String get submit => '提交';

  @override
  String get done => '完成';

  @override
  String get refresh => '刷新';

  @override
  String get retry => '重试';

  @override
  String get unsavedChanges => '您有未保存的更改';

  @override
  String get discardChanges => '放弃更改';

  @override
  String get saveChanges => '保存更改';

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
  String get backToDashboard => '返回仪表板';

  @override
  String get noAiAnalysisYet => 'No AI analysis available yet.\nClick \"Analyze\" to generate risk insights.';

  @override
  String get clickCalculatePricing => 'Click \"Calculate\" to generate a technical premium for this risk.';

  @override
  String get pricingNotAvailableDeclined => 'Pricing not available for declined risks.';

  @override
  String get leaveAnalysis => '离开分析？';

  @override
  String get stayHere => '留在这里';

  @override
  String get runInBackground => '后台运行';

  @override
  String get askAiAboutCategory => '询问AI关于此类别';

  @override
  String get copy => '复制';

  @override
  String get analysisMode => '分析模式';

  @override
  String get recommended => '推荐';

  @override
  String get agents => '代理';

  @override
  String documentsToAnalyze(int count) {
    return '$count个待分析文档';
  }

  @override
  String get characters => '字符';

  @override
  String get analysisFailed => '分析失败';

  @override
  String get goBack => '返回';

  @override
  String get documentCenter => '文档中心';

  @override
  String get createNewDocument => '创建新文档';

  @override
  String get newDocument => '新文档';

  @override
  String get recentDocuments => '最近的文档';

  @override
  String get templatesLibrary => '模板库';

  @override
  String get browseByLineOfBusiness => '按业务线浏览';

  @override
  String get assessmentDocuments => '评估文档';

  @override
  String get noAssessmentsYet => '暂无评估';

  @override
  String get uploadDocuments => '上传文档';

  @override
  String get searchDocuments => '搜索文档';

  @override
  String get getStarted => '开始';

  @override
  String get generate => '生成';

  @override
  String get uploaded => '已上传';

  @override
  String get generated => '已生成';

  @override
  String get generateDocuments => '生成文档';

  @override
  String get aiRecommendedDocuments => 'AI推荐的文档';

  @override
  String get selectDocumentsToGenerate => '选择要生成的文档';

  @override
  String get lmaClauses => 'LMA条款';

  @override
  String get selected => '已选择';

  @override
  String get required => '必填';

  @override
  String get generatingDocuments => '正在生成文档';

  @override
  String get aiAgentsWorking => 'AI代理正在处理您的文档';

  @override
  String get complete => '完成';

  @override
  String get liveActivity => '实时活动';

  @override
  String get initializing => '初始化中...';

  @override
  String get documentsGeneratedSuccessfully => '文档生成成功';

  @override
  String documentsReadyForReview(int count) {
    return '$count个文档已准备好审核';
  }

  @override
  String get preview => '预览';

  @override
  String get finalize => '完成';

  @override
  String get generateMore => '生成更多';

  @override
  String get selectLineOfBusiness => '选择业务线';

  @override
  String continueWith(String name) {
    return '继续使用$name';
  }

  @override
  String get selectALineOfBusiness => '选择一个业务线';

  @override
  String get documentLibrary => '文档库';

  @override
  String get insuranceKnowledgeBase => '保险知识库';

  @override
  String get data => '数据';

  @override
  String get categories => '类别';

  @override
  String get all => '全部';

  @override
  String get insurance => '保险';

  @override
  String get training => '培训';

  @override
  String get favorites => '收藏';

  @override
  String get noFavoritesYet => '暂无收藏';

  @override
  String get noDocumentsFound => '未找到文档';

  @override
  String get newChat => '新聊天';

  @override
  String get aiAssistant => 'AI助手';

  @override
  String get knowledgeSources => '知识来源';

  @override
  String get copiedToClipboard => '已复制到剪贴板';

  @override
  String get screeningLevels => '筛查级别';

  @override
  String get screeningHistory => '筛查历史';

  @override
  String get run => '运行';

  @override
  String get liveFindings => '实时结果';

  @override
  String get analysisCanContinueInBackground => 'You can close this window. Analysis will continue in background and results will be available in Reports.';

  @override
  String get minimizeLiveResults => 'Minimize';

  @override
  String get expandLiveResults => 'Show Live Results';

  @override
  String get checks => '检查';

  @override
  String get pending => '待处理';

  @override
  String get checking => '检查中...';

  @override
  String get clear => '清除';

  @override
  String get reviewRequired => '需要审核';

  @override
  String get matchFound => '找到匹配';

  @override
  String get noEntitiesFound => '未找到实体';

  @override
  String get screeningResults => '筛查结果';

  @override
  String get viewFullResults => '查看完整结果';

  @override
  String get sections => '部分';

  @override
  String get details => '详情';

  @override
  String get coreSections => '核心部分';

  @override
  String get exclusions => '除外责任';

  @override
  String get conditions => '条件';

  @override
  String get insuredInformation => '被保险人信息';

  @override
  String get coverageLimits => '保险限额';

  @override
  String get premium => '保费';

  @override
  String get generateDocument => '生成文档';

  @override
  String get generatingYourDocument => '正在生成您的文档';

  @override
  String get umrGenerate => '生成';

  @override
  String get umrRegistry => '注册表';

  @override
  String get umrValidation => '验证';

  @override
  String get multiAgentAnalysis => '多代理分析';

  @override
  String get agentPipeline => '5代理管道';

  @override
  String get overallProgress => '总体进度';

  @override
  String get documentClassifier => '文档分类器';

  @override
  String get classifyingDocument => '文档分类中';

  @override
  String get identifyingDocumentType => '识别文档类型并验证保险相关性';

  @override
  String get dataExtractor => '数据提取器';

  @override
  String get extractingData => '数据提取中';

  @override
  String get pullingInsuranceFields => '从文档中提取所有保险字段';

  @override
  String get riskAnalyst => '风险分析师';

  @override
  String get analyzingRisks => '风险分析中';

  @override
  String get identifyingRiskFactors => '识别风险因素和敞口';

  @override
  String get seniorUnderwriter => '高级核保人';

  @override
  String get underwritingDecision => '核保决定';

  @override
  String get makingGoNoGoDecision => '制定通过/拒绝/转介建议';

  @override
  String get qualityAssurance => '质量保证';

  @override
  String get finalValidation => '最终验证';

  @override
  String get ensuringAccuracy => '确保准确性和完整性';

  @override
  String get newAssessment => '新评估';

  @override
  String get aiPoweredAnalysis => 'AI分析';

  @override
  String get riskTypeAutoDetected => '风险类型将通过OCR和AI从您的文档中自动检测';

  @override
  String get addDocuments => '添加文档';

  @override
  String get uploadFromPhone => '从手机上传';

  @override
  String get scanQrWithPhone => '用手机扫描QR码';

  @override
  String get usePhoneCamera => '使用手机摄像头捕获文档';

  @override
  String get takePhoto => '拍照';

  @override
  String get captureWithCamera => '用摄像头捕获文档';

  @override
  String get photoGallery => '照片库';

  @override
  String get selectFromPhotos => '从您的照片中选择';

  @override
  String get browseFiles => '浏览文件';

  @override
  String get pdfDocXlsAndMore => 'PDF、DOC、XLS等';

  @override
  String get tapToAddDocuments => '点击添加文档';

  @override
  String get takePhotoBrowseOrGallery => '拍照、浏览文件或从相册选择';

  @override
  String get uploadedDocuments => '已上传的文档';

  @override
  String filesCount(int count) {
    return '$count个文件';
  }

  @override
  String get recommendedDocuments => '推荐文档';

  @override
  String get applicationFormLossHistory => '申请表、损失历史、财务报表、前保单';

  @override
  String get startRiskAssessment => '开始风险评估';

  @override
  String get failedToCreateSession => '创建上传会话失败';

  @override
  String documentsReceived(int count) {
    return '已接收$count个文档';
  }

  @override
  String get scanWithPhoneCamera => '用手机摄像头扫描\n以捕获和上传文档';

  @override
  String documentsAddedFromPhone(int count) {
    return '从手机添加了$count个文档';
  }

  @override
  String get personalInformation => '个人信息';

  @override
  String get professionalInformation => '职业信息';

  @override
  String get company => '公司';

  @override
  String get role => '职位';

  @override
  String get phone => '电话';

  @override
  String get accountStatistics => '账户统计';

  @override
  String get memberSince => '注册时间';

  @override
  String get totalAssessments => '总评估数';

  @override
  String get contractsGenerated => '已生成合同';

  @override
  String get lastLogin => '上次登录';

  @override
  String get dangerZone => '危险区域';

  @override
  String get deleteAccountWarning => '一旦删除您的账户，将无法撤销。请确认。';

  @override
  String get deleteAccount => '删除账户';

  @override
  String get profileUpdatedSuccessfully => '个人资料更新成功';

  @override
  String get thisFieldRequired => '此字段为必填项';

  @override
  String get deleteAccountConfirmation => '您确定要删除您的账户吗？此操作无法撤销，所有数据将永久丢失。';

  @override
  String get professionalPlan => '专业计划';

  @override
  String activeUntil(String date) {
    return '有效期至$date';
  }

  @override
  String get active => '活跃';

  @override
  String get thisMonthsUsage => '本月使用量';

  @override
  String get assessments => '评估';

  @override
  String get contractGenerations => '合同生成';

  @override
  String get aiChatMessages => 'AI聊天消息';

  @override
  String get documentStorage => '文档存储';

  @override
  String get availablePlans => '可用计划';

  @override
  String get basic => '基础版';

  @override
  String get enterprise => '企业版';

  @override
  String get popular => '热门';

  @override
  String get current => '当前';

  @override
  String get perMonth => '/月';

  @override
  String assessmentsPerMonth(String count) {
    return '$count次评估/月';
  }

  @override
  String contractGenerationsCount(String count) {
    return '$count次合同生成';
  }

  @override
  String aiChatMessagesCount(String count) {
    return '$count条AI聊天消息';
  }

  @override
  String documentStorageAmount(String amount) {
    return '$amount文档存储';
  }

  @override
  String get emailSupport => '邮件支持';

  @override
  String get prioritySupport => '优先支持';

  @override
  String get advancedAnalytics => '高级分析';

  @override
  String get dedicatedSupport => '24/7专属支持';

  @override
  String get customIntegrations => '自定义集成';

  @override
  String get whiteLabelOptions => '白标选项';

  @override
  String get unlimited => '无限制';

  @override
  String get upgrade => '升级';

  @override
  String get downgrade => '降级';

  @override
  String get billingHistory => '账单历史';

  @override
  String visaEndingIn(String last4) {
    return 'Visa尾号$last4';
  }

  @override
  String expires(String date) {
    return '$date到期';
  }

  @override
  String get update => '更新';

  @override
  String get enterpriseEdition => '企业版';

  @override
  String get goNoGoAnalysis => '通过/拒绝分析';

  @override
  String get approved => '已通过';

  @override
  String get declined => '已拒绝';

  @override
  String get refer => '转介';

  @override
  String get confidence => '置信度';

  @override
  String completedIn(String time) {
    return '$time内完成';
  }

  @override
  String estimatedRemaining(String time) {
    return '预计剩余：$time';
  }

  @override
  String get agentsLabel => '代理';

  @override
  String get findingsLabel => '结果';

  @override
  String get doneStatus => '完成';

  @override
  String get runningStatus => '运行中';

  @override
  String get pendingStatus => '待处理';

  @override
  String get identifyDocumentType => '识别文档类型';

  @override
  String get extractInsuranceData => '提取保险数据';

  @override
  String get analyzeRiskFactors => '分析风险因素';

  @override
  String get makeDecision => '做出决定';

  @override
  String get underwriter => '核保人';

  @override
  String get analysisRunningMessage => '分析正在运行。您可以：\n\n• 后台运行 - 分析继续，稍后在报告中查看结果\n• 留在这里 - 等待完成';

  @override
  String get unexpectedError => '发生意外错误';

  @override
  String get clauses => '条款';

  @override
  String get knowledge => '知识';

  @override
  String get languages => '语言';

  @override
  String get searchDocumentsClausesPolicies => '搜索文档、条款、保单...';

  @override
  String get docs => '文档';

  @override
  String get tapStarToFavorite => '点击任何类别的星标图标将其添加到收藏';

  @override
  String get tryAdjustingSearch => '尝试调整您的搜索或筛选';

  @override
  String get searchInThisCategory => '在此类别中搜索...';

  @override
  String get noDocumentsMatchSearch => '没有文档匹配您的搜索';

  @override
  String get noDocumentsInCategory => '此类别中没有文档';

  @override
  String get contentCopied => '内容已复制';

  @override
  String get pathCopiedToClipboard => '路径已复制到剪贴板';

  @override
  String get resetPassword => '重置密码';

  @override
  String get resetPasswordInstructions => '输入您的电子邮件地址，我们将向您发送重置密码的说明。';

  @override
  String get enterYourEmail => '输入您的邮箱';

  @override
  String get pleaseEnterYourEmail => '请输入您的邮箱';

  @override
  String get pleaseEnterValidEmail => '请输入有效的邮箱';

  @override
  String get sendResetLink => '发送重置链接';

  @override
  String get backToSignIn => '返回登录';

  @override
  String get checkYourEmail => '检查您的邮箱';

  @override
  String get passwordResetSentTo => '我们已将密码重置说明发送至';

  @override
  String get didntReceiveEmailResend => '没有收到邮件？重新发送';

  @override
  String get startRiskAssessmentJourney => '开始您的风险评估之旅';

  @override
  String get enterYourFullName => '输入您的全名';

  @override
  String get pleaseEnterYourName => '请输入您的姓名';

  @override
  String get companyOptional => '公司（可选）';

  @override
  String get enterYourCompanyName => '输入您的公司名称';

  @override
  String get createPassword => '创建密码';

  @override
  String get pleaseEnterPassword => '请输入密码';

  @override
  String get passwordMinLength => '密码必须至少8个字符';

  @override
  String get confirmYourPassword => '确认您的密码';

  @override
  String get pleaseConfirmPassword => '请确认您的密码';

  @override
  String get passwordsDoNotMatch => '密码不匹配';

  @override
  String get iAgreeToThe => '我同意';

  @override
  String get and => '和';

  @override
  String get alreadyHaveAccount => '已有账户？';

  @override
  String get signIn => '登录';

  @override
  String get pleaseAcceptTerms => '请接受条款和条件';

  @override
  String get onboardingTitle1 => 'AI驱动的风险评估';

  @override
  String get onboardingDesc1 => '上传保险文件，获得即时AI风险分析和GO/NO-GO建议';

  @override
  String get onboardingTitle2 => '智能文档生成';

  @override
  String get onboardingDesc2 => '生成符合Lloyd\'s市场标准的专业保险文件、合同和条款';

  @override
  String get onboardingTitle3 => '24/7保险AI助手';

  @override
  String get onboardingDesc3 => '从我们基于20GB+ Lloyd\'s市场知识训练的AI获取保险问题的即时解答';

  @override
  String get skip => '跳过';

  @override
  String get getStartedNow => '开始使用';
}
