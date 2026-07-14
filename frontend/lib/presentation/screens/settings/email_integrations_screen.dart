import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import 'dart:convert';

import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';

/// Email & File Integrations Screen
/// Connect Gmail/Outlook accounts via OAuth or app password (IMAP) and manage existing connections.
class EmailIntegrationsScreen extends StatefulWidget {
  const EmailIntegrationsScreen({super.key});

  @override
  State<EmailIntegrationsScreen> createState() => _EmailIntegrationsScreenState();
}

class _EmailIntegrationsScreenState extends State<EmailIntegrationsScreen> {
  bool _loadingConnections = true;
  bool _loadingProviders = true;
  List<Map<String, dynamic>> _connections = [];
  List<Map<String, dynamic>> _providersList = [];
  String? _connectionsError;
  String? _providersError;
  final Set<String> _syncingConnections = {};
  final Set<String> _connectingProviders = {};

  @override
  void initState() {
    super.initState();
    _loadData();
    _checkCallbackStatus();
  }

  Future<void> _loadData() async {
    await Future.wait([
      _loadConnections(),
      _loadProviders(),
    ]);
  }

  Future<void> _loadConnections() async {
    setState(() {
      _loadingConnections = true;
      _connectionsError = null;
    });
    try {
      final resp = await authService.get('/integrations/email');
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body);
        setState(() {
          _connections = List<Map<String, dynamic>>.from(data['connections'] ?? []);
          _loadingConnections = false;
        });
      } else {
        setState(() {
          _connectionsError = _parseError(resp.body);
          _loadingConnections = false;
        });
      }
    } catch (e) {
      setState(() {
        _connectionsError = 'Failed to load connections: $e';
        _loadingConnections = false;
      });
    }
  }

  Future<void> _loadProviders() async {
    setState(() {
      _loadingProviders = true;
      _providersError = null;
    });
    try {
      final resp = await authService.get('/integrations/email/providers');
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body);
        final raw = data['providers'];
        List<Map<String, dynamic>> list = [];
        if (raw is List) {
          list = List<Map<String, dynamic>>.from(raw);
        } else if (raw is Map) {
          (raw as Map<String, dynamic>).forEach((k, v) {
            list.add({'provider': k, ...Map<String, dynamic>.from(v as Map)});
          });
        }
        setState(() {
          _providersList = list;
          _loadingProviders = false;
        });
      } else {
        setState(() {
          _providersError = _parseError(resp.body);
          _loadingProviders = false;
        });
      }
    } catch (e) {
      setState(() {
        _providersError = 'Failed to load providers: $e';
        _loadingProviders = false;
      });
    }
  }

  void _checkCallbackStatus() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final uri = GoRouterState.of(context).uri;
      final connected = uri.queryParameters['connected'];
      if (connected != null) {
        final name = connected == 'gmail'
            ? 'Gmail'
            : connected == 'outlook'
                ? 'Outlook'
                : connected;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('$name connected successfully'),
            backgroundColor: AppTheme.success,
          ),
        );
        context.go('/settings/integrations');
        _loadConnections();
      }
    });
  }

  Map<String, dynamic> _providerConfig(String provider) {
    try {
      return _providersList.firstWhere(
        (p) => p['provider']?.toString().toLowerCase() == provider.toLowerCase(),
      );
    } catch (_) {
      return {};
    }
  }

  bool _isProviderOAuthConfigured(String provider) {
    return _providerConfig(provider)['oauth_configured'] == true;
  }

  bool _isProviderImapSupported(String provider) {
    return _providerConfig(provider)['imap_app_password_supported'] == true;
  }

  bool _isProviderError(String provider) {
    final err = _providerConfig(provider)['error'];
    return err != null && err.toString().isNotEmpty;
  }

  String? _providerErrorMessage(String provider) {
    return _providerConfig(provider)['error']?.toString();
  }

  bool _isProviderConnected(String provider) {
    return _connections.any(
      (c) => c['provider']?.toString().toLowerCase() == provider.toLowerCase(),
    );
  }

  Future<void> _connectProvider(String provider) async {
    if (_isProviderOAuthConfigured(provider)) {
      await _connectViaOAuth(provider);
    } else if (_isProviderImapSupported(provider)) {
      _showAppPasswordDialog(provider);
    } else {
      _showErrorSnackBar('${provider[0].toUpperCase()}${provider.substring(1)} is not available for connection');
    }
  }

  Future<void> _connectViaOAuth(String provider) async {
    setState(() => _connectingProviders.add(provider));
    try {
      final resp = await authService.post('/integrations/email/$provider/authorize');
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body);
        final authUrl = data['authorization_url'] as String?;
        if (authUrl != null) {
          await launchUrl(Uri.parse(authUrl), mode: LaunchMode.externalApplication);
        } else {
          _showErrorSnackBar('Invalid authorization response from server');
        }
      } else {
        _showErrorSnackBar(_parseError(resp.body));
      }
    } catch (e) {
      _showErrorSnackBar('Failed to initiate OAuth: $e');
    } finally {
      if (mounted) {
        setState(() => _connectingProviders.remove(provider));
      }
    }
  }

  void _showAppPasswordDialog(String provider) {
    final emailController = TextEditingController();
    final passwordController = TextEditingController();
    bool obscurePassword = true;
    bool isSubmitting = false;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: Row(
            children: [
              Icon(
                provider == 'gmail' ? Icons.mail_outlined : Icons.email,
                color: provider == 'gmail'
                    ? const Color(0xFFEA4335)
                    : const Color(0xFF0078D4),
                size: 24,
              ),
              const SizedBox(width: 10),
              Text('Connect ${provider[0].toUpperCase()}${provider.substring(1)}'),
            ],
          ),
          content: SizedBox(
            width: MediaQuery.of(context).size.width * 0.85,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFFF3E0),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.orange.shade200),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(Icons.info_outline, color: Colors.orange.shade700, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            provider == 'gmail'
                                ? 'Gmail requires an App Password. '
                                    'Enable 2-Step Verification in your Google Account → Security, '
                                    'then generate an App Password at app passwords.google.com.'
                                : 'Use an Outlook App Password or your account password '
                                    'if 2FA is enabled on your Microsoft account.',
                            style: TextStyle(fontSize: 12, color: Colors.orange.shade900),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: emailController,
                    decoration: const InputDecoration(
                      labelText: 'Email address',
                      hintText: 'your@email.com',
                      prefixIcon: Icon(Icons.email_outlined),
                      border: OutlineInputBorder(),
                    ),
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.next,
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: passwordController,
                    obscureText: obscurePassword,
                    decoration: InputDecoration(
                      labelText: 'App password',
                      hintText: 'xxxx xxxx xxxx xxxx',
                      prefixIcon: const Icon(Icons.lock_outline),
                      border: const OutlineInputBorder(),
                      suffixIcon: IconButton(
                        icon: Icon(obscurePassword ? Icons.visibility_off : Icons.visibility),
                        onPressed: () => setDialogState(() => obscurePassword = !obscurePassword),
                      ),
                    ),
                    textInputAction: TextInputAction.done,
                    onSubmitted: (_) => _submitAppPassword(
                      ctx,
                      provider,
                      emailController,
                      passwordController,
                      () => setDialogState(() {}),
                      () => setDialogState(() => isSubmitting = true),
                      () => setDialogState(() => isSubmitting = false),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Your password is sent over HTTPS and never stored in plain text.',
                    style: TextStyle(fontSize: 11, color: AppTheme.textHint),
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: isSubmitting ? null : () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: isSubmitting
                  ? null
                  : () => _submitAppPassword(
                        ctx,
                        provider,
                        emailController,
                        passwordController,
                        () => setDialogState(() {}),
                        () => setDialogState(() => isSubmitting = true),
                        () => setDialogState(() => isSubmitting = false),
                      ),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryDark,
                foregroundColor: Colors.white,
              ),
              child: isSubmitting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Text('Connect'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _submitAppPassword(
    BuildContext dialogCtx,
    String provider,
    TextEditingController emailCtrl,
    TextEditingController passwordCtrl,
    VoidCallback rebind,
    VoidCallback setLoading,
    VoidCallback clearLoading,
  ) async {
    final email = emailCtrl.text.trim();
    final password = passwordCtrl.text;

    if (email.isEmpty || !email.contains('@')) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please enter a valid email address'), backgroundColor: Colors.orange),
        );
      }
      return;
    }
    if (password.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please enter your app password'), backgroundColor: Colors.orange),
        );
      }
      return;
    }

    setLoading();
    Navigator.pop(dialogCtx);
    await _connectViaImap(provider, email, password);
    clearLoading();
  }

  Future<void> _connectViaImap(String provider, String email, String password) async {
    setState(() => _connectingProviders.add(provider));
    try {
      final resp = await authService.post(
        '/integrations/email/imap',
        body: {
          'provider': provider,
          'email_address': email,
          'app_password': password,
        },
      );
      if (resp.statusCode == 200 || resp.statusCode == 201) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('${email.split('@').first}@*** connected successfully'),
            backgroundColor: AppTheme.success,
          ),
        );
        await Future.wait([_loadConnections(), _loadProviders()]);
      } else {
        _showErrorSnackBar(_parseError(resp.body));
      }
    } catch (e) {
      _showErrorSnackBar('Connection failed: $e');
    } finally {
      if (mounted) {
        setState(() => _connectingProviders.remove(provider));
      }
    }
  }

  Future<void> _disconnectProvider(String provider) async {
    final conn = _connections.cast<Map<String, dynamic>?>().firstWhere(
      (c) => c?['provider']?.toString().toLowerCase() == provider.toLowerCase(),
      orElse: () => null,
    );
    if (conn != null) {
      await _disconnectConnection(conn['id']?.toString() ?? '');
    } else {
      _showErrorSnackBar('No active connection found for $provider');
    }
  }

  Future<void> _syncConnection(String connectionId) async {
    setState(() => _syncingConnections.add(connectionId));
    try {
      final resp = await authService.post('/integrations/email/$connectionId/sync');
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body);
        final messages = data['messages_fetched'] ?? 0;
        final assessments = data['new_assessments_created'] ?? 0;
        final documents = data['new_documents_ingested'] ?? 0;
        final skipped = data['skipped_duplicates'] ?? 0;
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Sync complete — $messages messages, $assessments assessments, '
              '$documents documents, $skipped already imported',
            ),
            backgroundColor: AppTheme.success,
          ),
        );
        await _loadConnections();
      } else {
        _showErrorSnackBar(_parseError(resp.body));
      }
    } catch (e) {
      _showErrorSnackBar('Sync failed: $e');
    } finally {
      if (mounted) {
        setState(() => _syncingConnections.remove(connectionId));
      }
    }
  }

  Future<void> _disconnectConnection(String connectionId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Remove Connection'),
        content: const Text(
          'This will remove the connected account and stop syncing. '
          'Documents already imported will not be deleted.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Remove', style: TextStyle(color: AppTheme.danger)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    try {
      final resp = await authService.delete('/integrations/email/$connectionId');
      if (resp.statusCode == 200 || resp.statusCode == 204) {
        setState(() {
          _connections.removeWhere((c) => c['id']?.toString() == connectionId);
        });
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Connection removed'),
            backgroundColor: AppTheme.textSecondary,
          ),
        );
        await _loadProviders();
      } else {
        _showErrorSnackBar(_parseError(resp.body));
      }
    } catch (e) {
      _showErrorSnackBar('Failed to remove connection: $e');
    }
  }

  void _showErrorSnackBar(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: AppTheme.danger),
    );
  }

  String _parseError(String body) {
    try {
      final data = jsonDecode(body);
      return data['detail'] ?? data['message'] ?? data['error'] ?? body;
    } catch (_) {
      return body;
    }
  }

  String _formatRelativeTime(String? isoDate) {
    if (isoDate == null || isoDate.isEmpty) return 'Never';
    try {
      final date = DateTime.parse(isoDate);
      final diff = DateTime.now().difference(date);
      if (diff.inMinutes < 1) return 'Just now';
      if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
      if (diff.inHours < 24) return '${diff.inHours}h ago';
      if (diff.inDays < 7) return '${diff.inDays}d ago';
      return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
    } catch (_) {
      return isoDate;
    }
  }

  bool _isConnectionActive(Map<String, dynamic> conn) {
    return conn['status']?.toString().toLowerCase() == 'connected';
  }

  @override
  Widget build(BuildContext context) {
    final isLoading = _loadingConnections && _loadingProviders;
    final hasAnyData =
        _connections.isNotEmpty || _providersList.isNotEmpty || (!_loadingConnections && !_loadingProviders);

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: AppTheme.surface,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppTheme.textPrimary),
          onPressed: () => context.go('/settings'),
        ),
        title: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.email_outlined, color: AppTheme.primaryDark, size: 22),
            SizedBox(width: 8),
            Text(
              'Email & file integrations',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
            ),
          ],
        ),
        centerTitle: true,
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : !hasAnyData && _connectionsError == null && _providersError == null
              ? _buildEmptyState()
              : RefreshIndicator(
                  onRefresh: _loadData,
                  child: SingleChildScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildProvidersSection(),
                        if (_connections.isNotEmpty) ...[
                          const SizedBox(height: 28),
                          _buildConnectionsSection(),
                        ],
                        if (_connections.isEmpty && !_loadingConnections && _connectionsError == null) ...[
                          const SizedBox(height: 28),
                          _buildNoConnectionsHint(),
                        ],
                        const SizedBox(height: 40),
                      ],
                    ),
                  ),
                ),
    );
  }

  Widget _buildProvidersSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'CONFIGURE PROVIDERS',
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: AppTheme.textSecondary,
            letterSpacing: 1,
          ),
        ),
        const SizedBox(height: 12),
        if (_providersError != null)
          _buildInlineError(_providersError!, onRetry: _loadProviders),
        _buildProviderCard('gmail', 'Gmail', Icons.mail_outlined, const Color(0xFFEA4335)),
        const SizedBox(height: 12),
        _buildProviderCard('outlook', 'Outlook', Icons.email, const Color(0xFF0078D4)),
      ],
    );
  }

  Widget _buildProviderCard(
    String provider,
    String label,
    IconData icon,
    Color iconColor,
  ) {
    final oauthConfigured = _isProviderOAuthConfigured(provider);
    final imapSupported = _isProviderImapSupported(provider);
    final hasError = _isProviderError(provider);
    final isConnected = _isProviderConnected(provider);
    final isConnecting = _connectingProviders.contains(provider);
    final errMsg = _providerErrorMessage(provider);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: hasError
              ? AppTheme.danger.withValues(alpha: 0.4)
              : isConnected
                  ? AppTheme.success.withValues(alpha: 0.3)
                  : AppTheme.border,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: iconColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: iconColor, size: 24),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      label,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    _buildStatusBadge(
                      hasError
                          ? 'Error'
                          : isConnected
                              ? 'Connected'
                              : !oauthConfigured && !imapSupported
                                  ? 'Unavailable'
                                  : 'Available',
                      hasError
                          ? AppTheme.danger
                          : isConnected
                              ? AppTheme.success
                              : AppTheme.textHint,
                    ),
                  ],
                ),
              ),
              if (isConnected)
                OutlinedButton(
                  onPressed: () => _disconnectProvider(provider),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.danger,
                    side: const BorderSide(color: AppTheme.danger),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  child: const Text('Disconnect', style: TextStyle(fontSize: 13)),
                )
              else if (oauthConfigured || imapSupported)
                ElevatedButton(
                  onPressed: isConnecting ? null : () => _connectProvider(provider),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryDark,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    elevation: 0,
                  ),
                  child: isConnecting
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Text('Connect', style: TextStyle(fontSize: 13)),
                ),
            ],
          ),
          if (hasError && errMsg != null) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppTheme.errorLight,
                borderRadius: BorderRadius.circular(6),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error_outline, color: AppTheme.error, size: 14),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      errMsg,
                      style: const TextStyle(fontSize: 12, color: AppTheme.error),
                    ),
                  ),
                ],
              ),
            ),
          ],
          if (!oauthConfigured && imapSupported && !isConnected) ...[
            const SizedBox(height: 8),
            Text(
              'OAuth not configured — use app password',
              style: TextStyle(fontSize: 11, color: AppTheme.textHint, fontStyle: FontStyle.italic),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildConnectionsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'CONNECTED ACCOUNTS',
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: AppTheme.textSecondary,
            letterSpacing: 1,
          ),
        ),
        const SizedBox(height: 12),
        if (_connectionsError != null)
          _buildInlineError(_connectionsError!, onRetry: _loadConnections),
        ...List.generate(_connections.length, (i) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: _buildConnectionCard(_connections[i]),
          );
        }),
      ],
    );
  }

  Widget _buildConnectionCard(Map<String, dynamic> conn) {
    final id = conn['id']?.toString() ?? '';
    final email = conn['email'] ?? conn['email_address'] ?? 'Unknown';
    final provider = conn['provider']?.toString() ?? 'unknown';
    final lastSync = conn['last_sync_at']?.toString() ?? conn['last_sync']?.toString();
    final authMethod = conn['auth_method']?.toString();
    final isActive = _isConnectionActive(conn);
    final isSyncing = _syncingConnections.contains(id);

    final providerIcon = provider == 'gmail'
        ? Icons.mail_outlined
        : provider == 'outlook'
            ? Icons.email
            : Icons.email_outlined;
    final providerColor = provider == 'gmail'
        ? const Color(0xFFEA4335)
        : provider == 'outlook'
            ? const Color(0xFF0078D4)
            : AppTheme.textHint;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isActive ? AppTheme.success.withValues(alpha: 0.3) : AppTheme.border,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: providerColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(providerIcon, color: providerColor, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      email.toString(),
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Row(
                      children: [
                        Text(
                          provider[0].toUpperCase() + provider.substring(1),
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                        if (authMethod != null) ...[
                          const SizedBox(width: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                            decoration: BoxDecoration(
                              color: AppTheme.primaryDark.withValues(alpha: 0.08),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              authMethod == 'oauth' ? 'OAuth' : 'IMAP',
                              style: TextStyle(fontSize: 10, color: AppTheme.primaryDark),
                            ),
                          ),
                        ],
                        const SizedBox(width: 8),
                        _buildStatusBadge(
                          isActive ? 'Connected' : 'Error',
                          isActive ? AppTheme.success : AppTheme.danger,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              const Icon(Icons.sync, size: 14, color: AppTheme.textHint),
              const SizedBox(width: 4),
              Text(
                'Last sync: ${_formatRelativeTime(lastSync)}',
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
              const Spacer(),
              if (isActive)
                OutlinedButton(
                  onPressed: isSyncing ? null : () => _syncConnection(id),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.primaryDark,
                    side: const BorderSide(color: AppTheme.primaryDark),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    minimumSize: Size.zero,
                  ),
                  child: isSyncing
                      ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Sync Now', style: TextStyle(fontSize: 12)),
                ),
              const SizedBox(width: 8),
              OutlinedButton(
                onPressed: () => _disconnectConnection(id),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.danger,
                  side: const BorderSide(color: AppTheme.danger),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  minimumSize: Size.zero,
                ),
                child: const Text('Disconnect', style: TextStyle(fontSize: 12)),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatusBadge(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: color,
        ),
      ),
    );
  }

  Widget _buildInlineError(String message, {required VoidCallback onRetry}) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.errorLight,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.error.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: AppTheme.error, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(message, style: const TextStyle(fontSize: 13, color: AppTheme.error)),
          ),
          TextButton(
            onPressed: onRetry,
            child: const Text('Retry', style: TextStyle(fontSize: 12, color: AppTheme.error)),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.email_outlined,
            size: 64,
            color: AppTheme.textHint.withValues(alpha: 0.5),
          ),
          const SizedBox(height: 16),
          const Text(
            'No integrations configured',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: AppTheme.textPrimary),
          ),
          const SizedBox(height: 8),
          const Text(
            'Connect Gmail or Outlook to start\nimporting emails and attachments.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppTheme.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _buildNoConnectionsHint() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.infoLight,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.info.withValues(alpha: 0.2)),
      ),
      child: const Row(
        children: [
          Icon(Icons.info_outline, color: AppTheme.info, size: 20),
          SizedBox(width: 12),
          Expanded(
            child: Text(
              'No connected accounts yet. Tap Connect on a provider above to link your email.',
              style: TextStyle(fontSize: 13, color: AppTheme.info),
            ),
          ),
        ],
      ),
    );
  }
}
