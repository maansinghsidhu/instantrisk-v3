import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_typeahead/flutter_typeahead.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

class ShareSubmissionScreen extends StatefulWidget {
  final String assessmentId;

  const ShareSubmissionScreen({super.key, required this.assessmentId});

  @override
  State<ShareSubmissionScreen> createState() => _ShareSubmissionScreenState();
}

class _ShareSubmissionScreenState extends State<ShareSubmissionScreen> {
  final TextEditingController _userSearchController = TextEditingController();
  final TextEditingController _messageController = TextEditingController();
  
  bool _isLoading = false;
  bool _isSharing = false;
  String? _errorMessage;
  List<UserSearchResult> _searchResults = [];
  UserSearchResult? _selectedUser;
  String _shareType = 'analysis';
  bool _includeDocuments = true;

  Future<Map<String, dynamic>> _fetchAssessment() async {
    final response = await authService.get('/api/v1/assessments/${widget.assessmentId}');
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception('Failed to fetch assessment');
  }

  Future<List<UserSearchResult>> _searchUsers(String query) async {
    if (query.isEmpty) return [];
    try {
      final response = await authService.get('/api/v1/shares/users/search?q=${Uri.encodeComponent(query)}');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as List<dynamic>;
        return data.map((e) => UserSearchResult.fromJson(e as Map<String, dynamic>)).toList();
      }
    } catch (_) {}
    return [];
  }

  Future<void> _share() async {
    if (_selectedUser == null) {
      setState(() => _errorMessage = 'Please select a user to share with');
      return;
    }

    setState(() {
      _isSharing = true;
      _errorMessage = null;
    });

    try {
      final body = {
        'assessment_id': widget.assessmentId,
        'shared_with_user_id': _selectedUser!.id,
        'share_type': _shareType,
        'include_documents': _includeDocuments,
        if (_messageController.text.isNotEmpty) 'message': _messageController.text,
      };

      final response = await http.post(
        Uri.parse('${authService.baseUrl}/api/v1/shares'),
        headers: {
          'Authorization': 'Bearer ${authService.token}',
          'Content-Type': 'application/json',
        },
        body: jsonEncode(body),
      );

      if (response.statusCode == 201) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Submission shared with ${_selectedUser!.fullName}'),
              backgroundColor: AppTheme.primaryDark,
            ),
          );
          context.pop();
        }
      } else {
        setState(() => _errorMessage = 'Failed to share submission');
      }
    } catch (e) {
      setState(() => _errorMessage = 'Error sharing submission: $e');
    } finally {
      setState(() => _isSharing = false);
    }
  }

  @override
  void dispose() {
    _userSearchController.dispose();
    _messageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Scaffold(
      backgroundColor: AppTheme.surfaceOf(context),
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceOf(context),
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.close_rounded, color: AppTheme.text2(context)),
          onPressed: () => context.pop(),
        ),
        title: Text(
          l10n?.share ?? 'Share',
          style: TextStyle(
            color: AppTheme.text1(context),
            fontSize: 18,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildShareTypeSection(),
                  const SizedBox(height: 24),
                  _buildUserSearchSection(),
                  const SizedBox(height: 24),
                  if (_selectedUser != null) _buildSelectedUserCard(),
                  const SizedBox(height: 24),
                  _buildOptionsSection(),
                  const SizedBox(height: 24),
                  _buildMessageSection(),
                  if (_errorMessage != null) ...[
                    const SizedBox(height: 16),
                    _buildErrorMessage(),
                  ],
                ],
              ),
            ),
          ),
          _buildShareButton(),
        ],
      ),
    );
  }

  Widget _buildShareTypeSection() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceVariantOf(context),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'What to share',
            style: TextStyle(
              color: AppTheme.text1(context),
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: GestureDetector(
                  onTap: () => setState(() => _shareType = 'analysis'),
                  child: Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: _shareType == 'analysis' 
                          ? AppTheme.primaryDark.withOpacity(0.15)
                          : Colors.transparent,
                      border: Border.all(
                        color: _shareType == 'analysis'
                            ? AppTheme.primaryDark
                            : AppTheme.borderOf(context),
                      ),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Column(
                      children: [
                        Icon(
                          Icons.analytics_outlined,
                          color: _shareType == 'analysis'
                              ? AppTheme.primaryDark
                              : AppTheme.text2(context),
                          size: 28,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Analysis',
                          style: TextStyle(
                            color: _shareType == 'analysis'
                                ? AppTheme.primaryDark
                                : AppTheme.text1(context),
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        Text(
                          'AI results & decisions',
                          style: TextStyle(
                            color: AppTheme.textH(context),
                            fontSize: 11,
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: GestureDetector(
                  onTap: () => setState(() => _shareType = 'originals'),
                  child: Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: _shareType == 'originals'
                          ? AppTheme.primaryDark.withOpacity(0.15)
                          : Colors.transparent,
                      border: Border.all(
                        color: _shareType == 'originals'
                            ? AppTheme.primaryDark
                            : AppTheme.borderOf(context),
                      ),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Column(
                      children: [
                        Icon(
                          Icons.description_outlined,
                          color: _shareType == 'originals'
                              ? AppTheme.primaryDark
                              : AppTheme.text2(context),
                          size: 28,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Originals',
                          style: TextStyle(
                            color: _shareType == 'originals'
                                ? AppTheme.primaryDark
                                : AppTheme.text1(context),
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        Text(
                          'Source documents',
                          style: TextStyle(
                            color: AppTheme.textH(context),
                            fontSize: 11,
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildUserSearchSection() {
    final l10n = AppLocalizations.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Share with',
          style: TextStyle(
            color: AppTheme.text1(context),
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 12),
        TypeAheadField<UserSearchResult>(
          textFieldConfiguration: TextFieldConfiguration(
            controller: _userSearchController,
            decoration: InputDecoration(
              hintText: 'Search by name or email...',
              hintStyle: TextStyle(color: AppTheme.textH(context)),
              prefixIcon: Icon(Icons.search_rounded, color: AppTheme.textH(context)),
              filled: true,
              fillColor: AppTheme.surfaceVariantOf(context),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: BorderSide.none,
              ),
              contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            ),
            onChanged: (value) async {
              final results = await _searchUsers(value);
              setState(() => _searchResults = results);
            },
          ),
          suggestionsCallback: (pattern) async {
            return await _searchUsers(pattern);
          },
          itemBuilder: (context, suggestion) {
            return ListTile(
              leading: CircleAvatar(
                backgroundColor: AppTheme.primaryDark.withOpacity(0.1),
                child: Icon(Icons.person_outline_rounded, color: AppTheme.primaryDark),
              ),
              title: Text(suggestion.fullName.isEmpty ? suggestion.email : suggestion.fullName),
              subtitle: Text(suggestion.email),
              trailing: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: AppTheme.surfaceOf(context),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  suggestion.role,
                  style: TextStyle(
                    color: AppTheme.textH(context),
                    fontSize: 11,
                  ),
                ),
              ),
            );
          },
          onSuggestionSelected: (suggestion) {
            setState(() {
              _selectedUser = suggestion;
              _userSearchController.text = suggestion.fullName.isEmpty 
                  ? suggestion.email 
                  : '${suggestion.fullName} (${suggestion.email})';
              _searchResults = [];
            });
          },
        ),
      ],
    );
  }

  Widget _buildSelectedUserCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceVariantOf(context),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 24,
            backgroundColor: AppTheme.primaryDark.withOpacity(0.1),
            child: Icon(Icons.person_outline_rounded, color: AppTheme.primaryDark),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _selectedUser!.fullName.isEmpty 
                      ? _selectedUser!.email 
                      : _selectedUser!.fullName,
                  style: TextStyle(
                    color: AppTheme.text1(context),
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Text(
                  _selectedUser!.email,
                  style: TextStyle(
                    color: AppTheme.textH(context),
                    fontSize: 13,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            icon: Icon(Icons.close_rounded, color: AppTheme.textH(context)),
            onPressed: () => setState(() {
              _selectedUser = null;
              _userSearchController.clear();
            }),
          ),
        ],
      ),
    );
  }

  Widget _buildOptionsSection() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceVariantOf(context),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          SwitchListTile(
            value: _includeDocuments,
            onChanged: (value) => setState(() => _includeDocuments = value),
            title: Text(
              'Include documents',
              style: TextStyle(color: AppTheme.text1(context)),
            ),
            subtitle: Text(
              'Share uploaded source documents',
              style: TextStyle(color: AppTheme.textH(context), fontSize: 12),
            ),
            activeColor: AppTheme.primaryDark,
          ),
        ],
      ),
    );
  }

  Widget _buildMessageSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Message (optional)',
          style: TextStyle(
            color: AppTheme.text1(context),
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _messageController,
          maxLines: 3,
          decoration: InputDecoration(
            hintText: 'Add a note for the recipient...',
            hintStyle: TextStyle(color: AppTheme.textH(context)),
            filled: true,
            fillColor: AppTheme.surfaceVariantOf(context),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide.none,
            ),
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          ),
        ),
      ],
    );
  }

  Widget _buildErrorMessage() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.danger.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline_rounded, color: AppTheme.danger),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              _errorMessage!,
              style: TextStyle(color: AppTheme.danger, fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildShareButton() {
    final l10n = AppLocalizations.of(context);

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: SizedBox(
          width: double.infinity,
          height: 50,
          child: ElevatedButton(
            onPressed: _isSharing || _selectedUser == null ? null : _share,
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryDark,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
            child: _isSharing
                ? SizedBox(
                    width: 20,
                    height: 20,
                    child: const CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : Text(
                    l10n?.share ?? 'Share',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
          ),
        ),
      ),
    );
  }
}

class UserSearchResult {
  final String id;
  final String fullName;
  final String email;
  final String role;

  UserSearchResult({
    required this.id,
    required this.fullName,
    required this.email,
    required this.role,
  });

  factory UserSearchResult.fromJson(Map<String, dynamic> json) {
    return UserSearchResult(
      id: json['id'] as String,
      fullName: json['full_name'] as String? ?? '',
      email: json['email'] as String,
      role: json['role'] as String? ?? 'user',
    );
  }
}