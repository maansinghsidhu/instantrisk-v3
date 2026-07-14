import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Team Management Screen - Manage team members and roles
class TeamManagementScreen extends StatefulWidget {
  const TeamManagementScreen({super.key});

  @override
  State<TeamManagementScreen> createState() => _TeamManagementScreenState();
}

class _TeamManagementScreenState extends State<TeamManagementScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool _isLoading = true;
  List<dynamic> _teams = [];
  List<dynamic> _roles = [];
  List<dynamic> _users = [];
  String? _teamsError;
  String? _rolesError;
  String? _usersError;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    // Listen to tab changes to update FAB label
    _tabController.addListener(() {
      if (!_tabController.indexIsChanging) {
        setState(() {}); // Rebuild to update FAB label
      }
    });
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _teamsError = null;
      _rolesError = null;
      _usersError = null;
    });

    // Load each independently so one failure doesn't block the others
    await _loadTeams();
    await _loadRoles();
    await _loadUsers();

    setState(() {
      _isLoading = false;
    });
  }

  Future<void> _loadTeams() async {
    try {
      final response = await authService.get('/teams?limit=100');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _teams = data['teams'] ?? [];
          _teamsError = null;
        });
      } else {
        setState(() {
          _teamsError = _extractErrorMessage(response);
        });
      }
    } catch (e) {
      setState(() {
        _teamsError = e.toString();
      });
    }
  }

  Future<void> _loadRoles() async {
    try {
      final response = await authService.get('/teams/roles');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _roles = data['roles'] ?? [];
          _rolesError = null;
        });
      } else {
        setState(() {
          _rolesError = _extractErrorMessage(response);
        });
      }
    } catch (e) {
      setState(() {
        _rolesError = e.toString();
      });
    }
  }

  Future<void> _loadUsers() async {
    try {
      final response = await authService.get('/auth/users?limit=100');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _users = data['items'] ?? data['users'] ?? [];
          _usersError = null;
        });
      } else {
        setState(() {
          _usersError = _extractErrorMessage(response);
        });
      }
    } catch (e) {
      setState(() {
        _usersError = e.toString();
      });
    }
  }

  String _extractErrorMessage(dynamic response) {
    try {
      final error = jsonDecode(response.body);
      return error['detail'] ?? error['message'] ?? response.body;
    } catch (_) {
      return response.body;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: AppTheme.primaryDark,
        foregroundColor: Colors.white,
        title: Text(AppLocalizations.of(context).teamManagement),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios),
          onPressed: () => context.go('/settings'),
        ),
        bottom: TabBar(
          controller: _tabController,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white60,
          indicatorColor: Colors.white,
          tabs: const [
            Tab(icon: Icon(Icons.groups), text: 'Teams'),
            Tab(icon: Icon(Icons.people), text: 'Members'),
            Tab(icon: Icon(Icons.admin_panel_settings), text: 'Roles'),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadData,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showAddDialog(),
        backgroundColor: AppTheme.primaryDark,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add),
        label: Text(_getAddButtonLabel()),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildTeamsTab(),
                _buildMembersTab(),
                _buildRolesTab(),
              ],
            ),
    );
  }

  String _getAddButtonLabel() {
    switch (_tabController.index) {
      case 0:
        return 'New Team';
      case 1:
        return 'Add Member';
      case 2:
        return 'New Role';
      default:
        return 'Add';
    }
  }

  // ============== Teams Tab ==============
  Widget _buildTeamsTab() {
    final children = <Widget>[];

    if (_teamsError != null) {
      children.add(_buildSectionErrorBanner(
        message: 'Failed to load teams: $_teamsError',
        onRetry: _loadTeams,
      ));
    }

    if (_teams.isEmpty && _teamsError == null) {
      children.add(Expanded(
        child: _buildEmptyState(
          icon: Icons.groups_outlined,
          title: 'No Teams Yet',
          subtitle: 'Create your first team to organize members',
        ),
      ));
    } else if (_teams.isNotEmpty) {
      children.add(Expanded(
        child: ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: _teams.length,
          itemBuilder: (context, index) {
            final team = _teams[index];
            return _buildTeamCard(team);
          },
        ),
      ));
    }

    return Column(children: children);
  }

  Widget _buildSectionErrorBanner({
    required String message,
    required Future<void> Function() onRetry,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: AppTheme.danger.withValues(alpha: 0.08),
        border: Border.all(color: AppTheme.danger.withValues(alpha: 0.3)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline, color: AppTheme.danger, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: TextStyle(color: AppTheme.danger, fontSize: 13),
            ),
          ),
          TextButton(
            onPressed: onRetry,
            child: Text(
              'Retry',
              style: TextStyle(color: AppTheme.danger, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTeamCard(Map<String, dynamic> team) {
    final memberCount = team['member_count'] ?? 0;
    final teamType = team['team_type'] ?? 'general';

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: InkWell(
        onTap: () => _showTeamDetails(team),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: _getTeamTypeColor(teamType).withValues(alpha: 0.1),
                    ),
                    child: Icon(
                      _getTeamTypeIcon(teamType),
                      color: _getTeamTypeColor(teamType),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          team['name'] ?? 'Unnamed Team',
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        if (team['team_code'] != null)
                          Text(
                            team['team_code'],
                            style: TextStyle(
                              fontSize: 12,
                              color: AppTheme.textHint,
                            ),
                          ),
                      ],
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppTheme.primaryDark.withValues(alpha: 0.1),
                        ),
                        child: Text(
                          '$memberCount members',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.primaryDark,
                          ),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        teamType.toUpperCase(),
                        style: TextStyle(
                          fontSize: 10,
                          color: AppTheme.textHint,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              if (team['description'] != null) ...[
                const SizedBox(height: 8),
                Text(
                  team['description'],
                  style: TextStyle(
                    fontSize: 13,
                    color: AppTheme.textSecondary,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
              if (team['classes_of_business'] != null &&
                  (team['classes_of_business'] as List).isNotEmpty) ...[
                const SizedBox(height: 8),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: (team['classes_of_business'] as List)
                      .take(3)
                      .map<Widget>((cob) => Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: AppTheme.surface,
                              borderRadius: BorderRadius.circular(4),
                              border: Border.all(color: AppTheme.border),
                            ),
                            child: Text(
                              cob.toString(),
                              style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                            ),
                          ))
                      .toList(),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  IconData _getTeamTypeIcon(String type) {
    switch (type.toLowerCase()) {
      case 'underwriting':
        return Icons.edit_document;
      case 'claims':
        return Icons.assignment;
      case 'compliance':
        return Icons.verified_user;
      case 'executive':
        return Icons.business;
      default:
        return Icons.groups;
    }
  }

  Color _getTeamTypeColor(String type) {
    switch (type.toLowerCase()) {
      case 'underwriting':
        return Colors.blue;
      case 'claims':
        return Colors.orange;
      case 'compliance':
        return Colors.green;
      case 'executive':
        return Colors.purple;
      default:
        return AppTheme.primaryDark;
    }
  }
  // ============== Members Tab ==============
  Widget _buildMembersTab() {
    final children = <Widget>[];

    if (_usersError != null) {
      children.add(_buildSectionErrorBanner(
        message: 'Failed to load users: $_usersError',
        onRetry: _loadUsers,
      ));
    }

    // Flatten all team members
    List<Map<String, dynamic>> allMembers = [];
    for (var team in _teams) {
      if (team['members'] != null) {
        for (var member in team['members']) {
          allMembers.add({
            ...member,
            'team_name': team['name'],
            'team_id': team['id'],
          });
        }
      }
    }

    // Also show users not in any team
    if (_users.isNotEmpty) {
      for (var user in _users) {
        final isInTeam = allMembers.any((m) => m['user_id'] == user['id'] || m['email'] == user['email']);
        if (!isInTeam) {
          allMembers.add({
            'user_id': user['id'],
            'full_name': user['full_name'] ?? user['email'],
            'email': user['email'],
            'role_name': user['role'] ?? 'User',
            'team_name': 'No Team',
            'is_active': user['is_active'] ?? true,
          });
        }
      }
    }

    if (allMembers.isEmpty && _users.isEmpty) {
      children.add(Expanded(
        child: _buildEmptyState(
          icon: Icons.people_outline,
          title: 'No Members Yet',
          subtitle: 'Add members to your teams',
        ),
      ));
    } else {
      children.add(Expanded(
        child: ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: allMembers.isNotEmpty ? allMembers.length : _users.length,
          itemBuilder: (context, index) {
            if (allMembers.isNotEmpty) {
              return _buildMemberCard(allMembers[index]);
            }
            return _buildUserCard(_users[index]);
          },
        ),
      ));
    }

    return Column(children: children);
  }

  Widget _buildMemberCard(Map<String, dynamic> member) {
    final isActive = member['is_active'] ?? true;
    final isTeamLead = member['is_team_lead'] ?? false;

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: isActive ? AppTheme.primaryDark : AppTheme.textHint,
          child: Text(
            (member['full_name'] ?? member['email'] ?? 'U')[0].toUpperCase(),
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
          ),
        ),
        title: Row(
          children: [
            Expanded(
              child: Text(
                member['full_name'] ?? member['email'] ?? 'Unknown',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            ),
            if (isTeamLead)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: AppTheme.warning.withValues(alpha: 0.1),
                ),
                child: Text(
                  'Lead',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.warning,
                  ),
                ),
              ),
          ],
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(member['email'] ?? ''),
            Row(
              children: [
                Text(
                  member['role_name'] ?? 'No Role',
                  style: TextStyle(
                    fontSize: 12,
                    color: AppTheme.primaryDark,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const Text(' - ', style: TextStyle(fontSize: 12)),
                Text(
                  member['team_name'] ?? 'No Team',
                  style: TextStyle(fontSize: 12, color: AppTheme.textHint),
                ),
              ],
            ),
          ],
        ),
        trailing: PopupMenuButton<String>(
          onSelected: (value) => _handleMemberAction(value, member),
          itemBuilder: (context) => [
            const PopupMenuItem(value: 'edit', child: Text('Edit Role')),
            const PopupMenuItem(value: 'move', child: Text('Move to Team')),
            PopupMenuItem(
              value: 'toggle',
              child: Text(isActive ? 'Deactivate' : 'Activate'),
            ),
            const PopupMenuItem(
              value: 'remove',
              child: Text('Remove', style: TextStyle(color: Colors.red)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildUserCard(Map<String, dynamic> user) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: AppTheme.primaryDark,
          child: Text(
            (user['full_name'] ?? user['email'] ?? 'U')[0].toUpperCase(),
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
          ),
        ),
        title: Text(
          user['full_name'] ?? user['email'] ?? 'Unknown',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: Text(user['email'] ?? ''),
        trailing: ElevatedButton(
          onPressed: () => _showAddMemberToTeamDialog(user),
          style: ElevatedButton.styleFrom(
            backgroundColor: AppTheme.primaryDark,
            foregroundColor: Colors.white,
          ),
          child: const Text('Add to Team'),
        ),
      ),
    );
  }

  // ============== Roles Tab ==============
  Widget _buildRolesTab() {
    final children = <Widget>[];

    if (_rolesError != null) {
      children.add(_buildSectionErrorBanner(
        message: 'Failed to load roles: $_rolesError',
        onRetry: _loadRoles,
      ));
    }

    if (_roles.isEmpty && _rolesError == null) {
      children.add(Expanded(
        child: _buildEmptyState(
          icon: Icons.admin_panel_settings_outlined,
          title: 'No Roles Defined',
          subtitle: 'Create roles to define permissions',
        ),
      ));
    } else if (_roles.isNotEmpty) {
      children.add(Expanded(
        child: ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: _roles.length,
          itemBuilder: (context, index) {
            final role = _roles[index];
            return _buildRoleCard(role);
          },
        ),
      ));
    }

    return Column(children: children);
  }

  Widget _buildRoleCard(Map<String, dynamic> role) {
    final permissions = role['permissions'] as List? ?? [];
    final hierarchyLevel = role['hierarchy_level'] ?? 0;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ExpansionTile(
        leading: Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: _getRoleColor(hierarchyLevel).withValues(alpha: 0.1),
          ),
          child: Center(
            child: Text(
              '$hierarchyLevel',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: _getRoleColor(hierarchyLevel),
              ),
            ),
          ),
        ),
        title: Text(
          role['name'] ?? 'Unnamed Role',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: Text(
          role['description'] ?? '',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AppTheme.primaryDark.withValues(alpha: 0.1),
              ),
              child: Text(
                '${permissions.length} perms',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.primaryDark,
                ),
              ),
            ),
            const Icon(Icons.expand_more),
          ],
        ),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Divider(),
                const Text(
                  'Permissions',
                  style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: permissions.map<Widget>((perm) {
                    final permName = perm is String ? perm : (perm['name'] ?? '');
                    return Chip(
                      label: Text(
                        permName,
                        style: const TextStyle(fontSize: 11),
                      ),
                      backgroundColor: _getPermissionColor(permName).withValues(alpha: 0.1),
                      labelStyle: TextStyle(color: _getPermissionColor(permName)),
                      visualDensity: VisualDensity.compact,
                    );
                  }).toList(),
                ),
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    TextButton.icon(
                      onPressed: () => _editRole(role),
                      icon: const Icon(Icons.edit, size: 18),
                      label: const Text('Edit'),
                    ),
                    if (role['is_system_role'] != true)
                      TextButton.icon(
                        onPressed: () => _deleteRole(role),
                        icon: Icon(Icons.delete, size: 18, color: AppTheme.danger),
                        label: Text('Delete', style: TextStyle(color: AppTheme.danger)),
                      ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Color _getRoleColor(int level) {
    if (level >= 40) return Colors.purple;
    if (level >= 30) return Colors.blue;
    if (level >= 20) return Colors.teal;
    if (level >= 10) return Colors.green;
    return Colors.grey;
  }

  Color _getPermissionColor(String perm) {
    if (perm.contains('write') || perm.contains('manage')) return Colors.orange;
    if (perm.contains('approve')) return Colors.green;
    if (perm.contains('delete')) return Colors.red;
    return Colors.blue;
  }

  Widget _buildEmptyState({
    required IconData icon,
    required String title,
    required String subtitle,
  }) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: AppTheme.primaryDark.withValues(alpha: 0.1),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, size: 40, color: AppTheme.primaryDark),
          ),
          const SizedBox(height: 20),
          Text(
            title,
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            subtitle,
            style: TextStyle(color: AppTheme.textSecondary),
          ),
        ],
      ),
    );
  }

  // ============== Actions ==============
  void _showAddDialog() {
    switch (_tabController.index) {
      case 0:
        _showCreateTeamDialog();
        break;
      case 1:
        _showInviteMemberDialog();
        break;
      case 2:
        _showCreateRoleDialog();
        break;
    }
  }

  void _showCreateTeamDialog() {
    final nameController = TextEditingController();
    final descController = TextEditingController();
    final codeController = TextEditingController();
    String teamType = 'underwriting';

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Create Team'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameController,
                  decoration: const InputDecoration(
                    labelText: 'Team Name',
                    hintText: 'e.g., Marine Underwriting',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: codeController,
                  decoration: const InputDecoration(
                    labelText: 'Team Code',
                    hintText: 'e.g., UW-MARINE',
                  ),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: teamType,
                  decoration: const InputDecoration(labelText: 'Team Type'),
                  items: const [
                    DropdownMenuItem(value: 'underwriting', child: Text('Underwriting')),
                    DropdownMenuItem(value: 'claims', child: Text('Claims')),
                    DropdownMenuItem(value: 'compliance', child: Text('Compliance')),
                    DropdownMenuItem(value: 'executive', child: Text('Executive')),
                    DropdownMenuItem(value: 'general', child: Text('General')),
                  ],
                  onChanged: (v) => setDialogState(() => teamType = v!),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: descController,
                  decoration: const InputDecoration(
                    labelText: 'Description',
                    hintText: 'Team description',
                  ),
                  maxLines: 2,
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () async {
                Navigator.pop(context);
                await _createTeam(
                  nameController.text,
                  codeController.text,
                  teamType,
                  descController.text,
                );
              },
              child: const Text('Create'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _createTeam(String name, String code, String type, String desc) async {
    try {
      final response = await authService.post('/teams', body: {
        'name': name,
        'team_code': code,
        'team_type': type,
        'description': desc,
        'syndicate_id': 1, // Default syndicate
      });
      if (!mounted) return;

      if (response.statusCode == 200 || response.statusCode == 201) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Team created successfully')),
        );
        _loadData();
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${_extractErrorMessage(response)}'), backgroundColor: Colors.red),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }

  void _showInviteMemberDialog() {
    final emailController = TextEditingController();
    final nameController = TextEditingController();
    final passwordController = TextEditingController();
    Map<String, dynamic>? selectedRole;
    Map<String, dynamic>? selectedTeam;
    bool showPassword = false;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Add New Member'),
          content: SizedBox(
            width: MediaQuery.of(context).size.width * 0.8,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: nameController,
                    decoration: const InputDecoration(
                      labelText: 'Full Name *',
                      hintText: 'John Smith',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.person),
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: emailController,
                    decoration: const InputDecoration(
                      labelText: 'Email *',
                      hintText: 'member@company.com',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.email),
                    ),
                    keyboardType: TextInputType.emailAddress,
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: passwordController,
                    obscureText: !showPassword,
                    decoration: InputDecoration(
                      labelText: 'Password *',
                      hintText: 'Min 8 characters',
                      border: const OutlineInputBorder(),
                      prefixIcon: const Icon(Icons.lock),
                      suffixIcon: IconButton(
                        icon: Icon(showPassword ? Icons.visibility_off : Icons.visibility),
                        onPressed: () => setDialogState(() => showPassword = !showPassword),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  DropdownButtonFormField<Map<String, dynamic>>(
                    value: selectedRole,
                    decoration: const InputDecoration(
                      labelText: 'Role *',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.admin_panel_settings),
                    ),
                    hint: const Text('Select a role'),
                    items: _roles.map<DropdownMenuItem<Map<String, dynamic>>>((role) {
                      return DropdownMenuItem(
                        value: role,
                        child: Text(role['name'] ?? 'Unknown'),
                      );
                    }).toList(),
                    onChanged: (v) => setDialogState(() => selectedRole = v),
                  ),
                  const SizedBox(height: 16),
                  DropdownButtonFormField<Map<String, dynamic>>(
                    value: selectedTeam,
                    decoration: const InputDecoration(
                      labelText: 'Team (Optional)',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.groups),
                    ),
                    hint: const Text('Select a team'),
                    items: [
                      const DropdownMenuItem(
                        value: null,
                        child: Text('No Team'),
                      ),
                      ..._teams.map<DropdownMenuItem<Map<String, dynamic>>>((team) {
                        return DropdownMenuItem(
                          value: team,
                          child: Text(team['name'] ?? 'Unknown'),
                        );
                      }),
                    ],
                    onChanged: (v) => setDialogState(() => selectedTeam = v),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.blue.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.info_outline, color: Colors.blue, size: 20),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'User will be created and can log in immediately with these credentials.',
                            style: TextStyle(fontSize: 12, color: Colors.blue[800]),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () async {
                // Validate
                if (nameController.text.trim().isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Please enter a name'), backgroundColor: Colors.orange),
                  );
                  return;
                }
                if (emailController.text.trim().isEmpty || !emailController.text.contains('@')) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Please enter a valid email'), backgroundColor: Colors.orange),
                  );
                  return;
                }
                if (passwordController.text.length < 8) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Password must be at least 8 characters'), backgroundColor: Colors.orange),
                  );
                  return;
                }
                if (selectedRole == null) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Please select a role'), backgroundColor: Colors.orange),
                  );
                  return;
                }

                Navigator.pop(context);
                await _createMember(
                  nameController.text.trim(),
                  emailController.text.trim(),
                  passwordController.text,
                  selectedRole!['id'],
                  selectedTeam?['id'],
                );
              },
              style: ElevatedButton.styleFrom(backgroundColor: AppTheme.primaryDark),
              child: const Text('Create Member', style: TextStyle(color: Colors.white)),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _createMember(String name, String email, String password, int roleId, int? teamId) async {
    try {
      Map<String, dynamic>? selectedTeam;
      if (teamId != null) {
        for (final team in _teams) {
          if (team is Map<String, dynamic> && team['id'] == teamId) {
            selectedTeam = team;
            break;
          }
        }
      }
      final userBody = <String, dynamic>{
        'full_name': name,
        'email': email,
        'password': password,
        'is_active': true,
        'is_verified': true,
        'approval_status': 'approved',
      };
      if (selectedTeam?['syndicate_id'] != null) {
        userBody['syndicate_id'] = selectedTeam!['syndicate_id'];
      }

      final userResponse = await authService.post('/auth/users', body: userBody);
      if (userResponse.statusCode == 200 || userResponse.statusCode == 201) {
        final userData = jsonDecode(userResponse.body);
        final userId = userData['id'];

        if (teamId != null && userId != null) {
          final membershipResponse = await authService.post('/teams/$teamId/members', body: {
            'user_id': userId,
            'role_id': roleId,
          });
          if (membershipResponse.statusCode != 200 && membershipResponse.statusCode != 201) {
            if (!mounted) return;
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('User created, but team assignment failed: ${_extractErrorMessage(membershipResponse)}'),
                backgroundColor: Colors.orange,
              ),
            );
            await _loadData();
            return;
          }
        }

        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Member created successfully'), backgroundColor: Colors.green),
        );
        await _loadData();
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${_extractErrorMessage(userResponse)}'), backgroundColor: Colors.red),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
      );
    }
  }

  void _showCreateRoleDialog() {
    final nameController = TextEditingController();
    final descController = TextEditingController();
    int hierarchyLevel = 20;

    // All available permissions
    final allPermissions = [
      {'name': 'assessment:read', 'label': 'View Assessments', 'category': 'Assessments'},
      {'name': 'assessment:write', 'label': 'Create/Edit Assessments', 'category': 'Assessments'},
      {'name': 'assessment:approve', 'label': 'Approve Assessments', 'category': 'Assessments'},
      {'name': 'assessment:delete', 'label': 'Delete Assessments', 'category': 'Assessments'},
      {'name': 'document:read', 'label': 'View Documents', 'category': 'Documents'},
      {'name': 'document:write', 'label': 'Upload Documents', 'category': 'Documents'},
      {'name': 'document:delete', 'label': 'Delete Documents', 'category': 'Documents'},
      {'name': 'report:read', 'label': 'View Reports', 'category': 'Reports'},
      {'name': 'report:write', 'label': 'Generate Reports', 'category': 'Reports'},
      {'name': 'team:read', 'label': 'View Teams', 'category': 'Teams'},
      {'name': 'team:write', 'label': 'Manage Teams', 'category': 'Teams'},
      {'name': 'user:read', 'label': 'View Users', 'category': 'Users'},
      {'name': 'user:write', 'label': 'Manage Users', 'category': 'Users'},
      {'name': 'role:read', 'label': 'View Roles', 'category': 'Roles'},
      {'name': 'role:write', 'label': 'Manage Roles', 'category': 'Roles'},
      {'name': 'analysis:run', 'label': 'Run AI Analysis', 'category': 'Analysis'},
      {'name': 'pricing:read', 'label': 'View Pricing', 'category': 'Pricing'},
      {'name': 'pricing:write', 'label': 'Set Pricing', 'category': 'Pricing'},
    ];

    Set<String> selectedPermissions = {};

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Create New Role'),
          content: SizedBox(
            width: MediaQuery.of(context).size.width * 0.8,
            height: MediaQuery.of(context).size.height * 0.7,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: nameController,
                    decoration: const InputDecoration(
                      labelText: 'Role Name *',
                      hintText: 'e.g., Senior Analyst',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: descController,
                    decoration: const InputDecoration(
                      labelText: 'Description',
                      hintText: 'What can this role do?',
                      border: OutlineInputBorder(),
                    ),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 16),
                  DropdownButtonFormField<int>(
                    value: hierarchyLevel,
                    decoration: const InputDecoration(
                      labelText: 'Hierarchy Level',
                      border: OutlineInputBorder(),
                    ),
                    items: const [
                      DropdownMenuItem(value: 10, child: Text('10 - Entry Level')),
                      DropdownMenuItem(value: 20, child: Text('20 - Standard')),
                      DropdownMenuItem(value: 30, child: Text('30 - Senior')),
                      DropdownMenuItem(value: 40, child: Text('40 - Manager')),
                      DropdownMenuItem(value: 50, child: Text('50 - Admin')),
                    ],
                    onChanged: (v) => setDialogState(() => hierarchyLevel = v!),
                  ),
                  const SizedBox(height: 24),
                  const Text(
                    'PERMISSIONS',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: Colors.grey,
                      letterSpacing: 1,
                    ),
                  ),
                  const SizedBox(height: 12),
                  // Group permissions by category
                  ...['Assessments', 'Documents', 'Reports', 'Teams', 'Users', 'Roles', 'Analysis', 'Pricing'].map((category) {
                    final categoryPerms = allPermissions.where((p) => p['category'] == category).toList();
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Padding(
                          padding: const EdgeInsets.only(top: 8, bottom: 4),
                          child: Text(
                            category,
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.primaryDark,
                            ),
                          ),
                        ),
                        ...categoryPerms.map((perm) => CheckboxListTile(
                          title: Text(perm['label']!, style: const TextStyle(fontSize: 14)),
                          subtitle: Text(perm['name']!, style: const TextStyle(fontSize: 11, color: Colors.grey)),
                          value: selectedPermissions.contains(perm['name']),
                          dense: true,
                          controlAffinity: ListTileControlAffinity.leading,
                          onChanged: (checked) {
                            setDialogState(() {
                              if (checked == true) {
                                selectedPermissions.add(perm['name']!);
                              } else {
                                selectedPermissions.remove(perm['name']);
                              }
                            });
                          },
                        )),
                      ],
                    );
                  }),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () async {
                if (nameController.text.trim().isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Please enter a role name'), backgroundColor: Colors.orange),
                  );
                  return;
                }
                Navigator.pop(context);
                await _createRole(
                  nameController.text.trim(),
                  descController.text.trim(),
                  hierarchyLevel,
                  selectedPermissions.toList(),
                );
              },
              style: ElevatedButton.styleFrom(backgroundColor: AppTheme.primaryDark),
              child: const Text('Create Role', style: TextStyle(color: Colors.white)),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _createRole(String name, String description, int hierarchyLevel, List<String> permissions) async {
    try {
      final response = await authService.post('/teams/roles', body: {
        'name': name,
        'description': description,
        'hierarchy_level': hierarchyLevel,
        'permissions': permissions,
      });

      if (response.statusCode == 200 || response.statusCode == 201) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Role created successfully'), backgroundColor: Colors.green),
        );
        _loadData();
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${_extractErrorMessage(response)}'), backgroundColor: Colors.red),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
      );
    }
  }

  void _showTeamDetails(Map<String, dynamic> team) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        maxChildSize: 0.9,
        minChildSize: 0.5,
        expand: false,
        builder: (context, scrollController) => Padding(
          padding: const EdgeInsets.all(20),
          child: ListView(
            controller: scrollController,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  margin: const EdgeInsets.only(bottom: 20),
                  decoration: BoxDecoration(
                    color: Colors.grey[300],
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              Text(
                team['name'] ?? 'Team',
                style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Text(
                team['description'] ?? 'No description',
                style: TextStyle(color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 20),
              const Text('Team Members', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              const SizedBox(height: 12),
              if (team['members'] != null && (team['members'] as List).isNotEmpty)
                ...(team['members'] as List).map((m) => ListTile(
                      leading: CircleAvatar(
                        child: Text((m['full_name'] ?? 'U')[0].toUpperCase()),
                      ),
                      title: Text(m['full_name'] ?? m['email'] ?? 'Unknown'),
                      subtitle: Text(m['role_name'] ?? 'No Role'),
                      trailing: m['is_team_lead'] == true
                          ? const Chip(label: Text('Lead'))
                          : null,
                    ))
              else
                const Text('No members yet'),
            ],
          ),
        ),
      ),
    );
  }

  void _handleMemberAction(String action, Map<String, dynamic> member) {
    switch (action) {
      case 'edit':
        _showEditMemberRoleDialog(member);
        break;
      case 'move':
        _showMoveToTeamDialog(member);
        break;
      case 'toggle':
        _toggleMemberStatus(member);
        break;
      case 'remove':
        _removeMember(member);
        break;
    }
  }

  void _showEditMemberRoleDialog(Map<String, dynamic> member) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Edit ${member['full_name'] ?? 'Member'}'),
        content: const Text('Role editing coming soon'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  void _showMoveToTeamDialog(Map<String, dynamic> member) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Move to Team'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: _teams.map<Widget>((team) => ListTile(
            title: Text(team['name'] ?? 'Team'),
            onTap: () {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Moved to ${team['name']}')),
              );
            },
          )).toList(),
        ),
      ),
    );
  }

  void _toggleMemberStatus(Map<String, dynamic> member) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Status toggled')),
    );
  }

  void _removeMember(Map<String, dynamic> member) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove Member'),
        content: Text('Are you sure you want to remove ${member['full_name'] ?? 'this member'}?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Member removed')),
              );
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.danger),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
  }

  void _showAddMemberToTeamDialog(Map<String, dynamic> user) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Add ${user['full_name'] ?? user['email']} to Team'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: _teams.map<Widget>((team) => ListTile(
            leading: Icon(_getTeamTypeIcon(team['team_type'] ?? 'general')),
            title: Text(team['name'] ?? 'Team'),
            subtitle: Text('${team['member_count'] ?? 0} members'),
            onTap: () {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Added to ${team['name']}')),
              );
            },
          )).toList(),
        ),
      ),
    );
  }

  void _editRole(Map<String, dynamic> role) {
    final nameController = TextEditingController(text: role['name'] ?? '');
    final descController = TextEditingController(text: role['description'] ?? '');
    final currentPermissions = List<String>.from(
      (role['permissions'] as List?)?.map((p) => p is String ? p : p['name'] ?? '') ?? []
    );

    // All available permissions
    final allPermissions = [
      {'name': 'assessment:read', 'label': 'View Assessments', 'category': 'Assessments'},
      {'name': 'assessment:write', 'label': 'Create/Edit Assessments', 'category': 'Assessments'},
      {'name': 'assessment:approve', 'label': 'Approve Assessments', 'category': 'Assessments'},
      {'name': 'assessment:delete', 'label': 'Delete Assessments', 'category': 'Assessments'},
      {'name': 'document:read', 'label': 'View Documents', 'category': 'Documents'},
      {'name': 'document:write', 'label': 'Upload Documents', 'category': 'Documents'},
      {'name': 'document:delete', 'label': 'Delete Documents', 'category': 'Documents'},
      {'name': 'report:read', 'label': 'View Reports', 'category': 'Reports'},
      {'name': 'report:write', 'label': 'Generate Reports', 'category': 'Reports'},
      {'name': 'team:read', 'label': 'View Teams', 'category': 'Teams'},
      {'name': 'team:write', 'label': 'Manage Teams', 'category': 'Teams'},
      {'name': 'user:read', 'label': 'View Users', 'category': 'Users'},
      {'name': 'user:write', 'label': 'Manage Users', 'category': 'Users'},
      {'name': 'role:read', 'label': 'View Roles', 'category': 'Roles'},
      {'name': 'role:write', 'label': 'Manage Roles', 'category': 'Roles'},
      {'name': 'analysis:run', 'label': 'Run AI Analysis', 'category': 'Analysis'},
      {'name': 'pricing:read', 'label': 'View Pricing', 'category': 'Pricing'},
      {'name': 'pricing:write', 'label': 'Set Pricing', 'category': 'Pricing'},
    ];

    Set<String> selectedPermissions = Set.from(currentPermissions);

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text('Edit Role: ${role['name']}'),
          content: SizedBox(
            width: MediaQuery.of(context).size.width * 0.8,
            height: MediaQuery.of(context).size.height * 0.7,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: nameController,
                    decoration: const InputDecoration(
                      labelText: 'Role Name',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: descController,
                    decoration: const InputDecoration(
                      labelText: 'Description',
                      border: OutlineInputBorder(),
                    ),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 24),
                  const Text(
                    'PERMISSIONS',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: Colors.grey,
                      letterSpacing: 1,
                    ),
                  ),
                  const SizedBox(height: 12),
                  // Group permissions by category
                  ...['Assessments', 'Documents', 'Reports', 'Teams', 'Users', 'Roles', 'Analysis', 'Pricing'].map((category) {
                    final categoryPerms = allPermissions.where((p) => p['category'] == category).toList();
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Padding(
                          padding: const EdgeInsets.only(top: 8, bottom: 4),
                          child: Text(
                            category,
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.primaryDark,
                            ),
                          ),
                        ),
                        ...categoryPerms.map((perm) => CheckboxListTile(
                          title: Text(perm['label']!, style: const TextStyle(fontSize: 14)),
                          subtitle: Text(perm['name']!, style: const TextStyle(fontSize: 11, color: Colors.grey)),
                          value: selectedPermissions.contains(perm['name']),
                          dense: true,
                          controlAffinity: ListTileControlAffinity.leading,
                          onChanged: (checked) {
                            setDialogState(() {
                              if (checked == true) {
                                selectedPermissions.add(perm['name']!);
                              } else {
                                selectedPermissions.remove(perm['name']);
                              }
                            });
                          },
                        )),
                      ],
                    );
                  }),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () async {
                Navigator.pop(context);
                await _updateRole(
                  role['id'],
                  nameController.text,
                  descController.text,
                  selectedPermissions.toList(),
                );
              },
              style: ElevatedButton.styleFrom(backgroundColor: AppTheme.primaryDark),
              child: const Text('Save Changes', style: TextStyle(color: Colors.white)),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _updateRole(int roleId, String name, String description, List<String> permissions) async {
    try {
      final response = await authService.put('/teams/roles/$roleId', body: {
        'name': name,
        'description': description,
        'permissions': permissions,
      });

      if (response.statusCode == 200) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Role updated successfully'), backgroundColor: Colors.green),
        );
        _loadData();
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${_extractErrorMessage(response)}'), backgroundColor: Colors.red),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
      );
    }
  }

  void _deleteRole(Map<String, dynamic> role) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Role'),
        content: Text('Are you sure you want to delete "${role['name']}"?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Role deleted')),
              );
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.danger),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }
}
