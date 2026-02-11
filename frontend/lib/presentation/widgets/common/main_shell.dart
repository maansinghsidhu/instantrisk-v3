import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/services/documents_prefetch_service.dart';
import '../../../core/services/subscription_service.dart';
import '../../../l10n/generated/app_localizations.dart';

/// MainShell - Responsive navigation shell
/// - Desktop (>1000px): Permanent sidebar on left
/// - Tablet (600-1000px): Bottom nav with hamburger menu for overlay drawer
/// - Mobile (<600px): Bottom navigation bar only
class MainShell extends StatefulWidget {
  final Widget child;

  const MainShell({
    super.key,
    required this.child,
  });

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();

  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;

    // Desktop: Permanent sidebar (>1000px)
    if (screenWidth > 1000) {
      return Scaffold(
        body: Row(
          children: [
            _Sidebar(onNavigate: null),
            Expanded(child: widget.child),
          ],
        ),
      );
    }

    // Tablet/Medium: Bottom nav with hamburger menu for drawer (600-1000px)
    if (screenWidth > 600) {
      return Scaffold(
        key: _scaffoldKey,
        appBar: AppBar(
          backgroundColor: AppTheme.primaryDark,
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.menu, color: Colors.white),
            onPressed: () => _scaffoldKey.currentState?.openDrawer(),
          ),
          title: Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Center(
                  child: Text(
                    'IR',
                    style: TextStyle(
                      color: AppTheme.primaryDark,
                      fontWeight: FontWeight.w800,
                      fontSize: 12,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Text(
                AppLocalizations.of(context)?.appName ?? 'InstantRisk',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
        drawer: Drawer(
          child: _Sidebar(
            onNavigate: () => Navigator.of(context).pop(),
          ),
        ),
        body: widget.child,
        bottomNavigationBar: const _BottomNavBar(),
      );
    }

    // Mobile: Bottom navigation only (<600px)
    return Scaffold(
      body: widget.child,
      bottomNavigationBar: const _BottomNavBar(),
    );
  }
}

/// Sidebar for Web/Desktop
class _Sidebar extends StatelessWidget {
  final VoidCallback? onNavigate;

  const _Sidebar({this.onNavigate});

  int _calculateSelectedIndex(BuildContext context) {
    final String location = GoRouterState.of(context).uri.toString();
    if (location.startsWith('/home')) return 0;
    if (location.startsWith('/reports')) return 1;  // Assessments
    if (location.startsWith('/chat')) return 2;  // AI Chat
    if (location.startsWith('/training')) return 3;
    if (location.startsWith('/documents')) return 4;
    // Settings includes Lloyd's Market pages
    if (location.startsWith('/settings') || location.startsWith('/lloyds')) return 5;
    return 0;
  }

  void _onItemTapped(BuildContext context, int index) {
    onNavigate?.call();
    switch (index) {
      case 0:
        context.go('/home');
        break;
      case 1:
        context.go('/reports');  // Assessments
        break;
      case 2:
        context.go('/chat');
        break;
      case 3:
        context.go('/training');
        break;
      case 4:
        context.go('/documents');
        break;
      case 5:
        context.go('/settings');
        break;
    }
  }

  void _showSidebarUpgradeDialog(BuildContext context, String featureName) {
    onNavigate?.call();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Row(
          children: [
            Icon(Icons.lock, color: Colors.amber),
            const SizedBox(width: 8),
            const Text('Premium Feature'),
          ],
        ),
        content: Text(
          '$featureName is available for Premium users. Upgrade your subscription to access this feature.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              context.go('/settings/subscription');
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryDark,
            ),
            child: const Text('Upgrade'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final selectedIndex = _calculateSelectedIndex(context);

    return Container(
      width: 240,
      decoration: BoxDecoration(
        color: AppTheme.primaryDark,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 10,
            offset: const Offset(2, 0),
          ),
        ],
      ),
      child: Column(
        children: [
          // Logo Header (only shown when not in drawer)
          if (onNavigate == null)
            Container(
              padding: const EdgeInsets.all(24),
              child: Row(
                children: [
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Center(
                      child: Text(
                        'IR',
                        style: TextStyle(
                          color: AppTheme.primaryDark,
                          fontWeight: FontWeight.w800,
                          fontSize: 16,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      AppLocalizations.of(context).appName,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
            ),

          // Drawer header
          if (onNavigate != null)
            Container(
              padding: const EdgeInsets.fromLTRB(24, 48, 24, 24),
              child: Row(
                children: [
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Center(
                      child: Text(
                        'IR',
                        style: TextStyle(
                          color: AppTheme.primaryDark,
                          fontWeight: FontWeight.w800,
                          fontSize: 16,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      AppLocalizations.of(context).appName,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
            ),

          const Divider(color: Colors.white24, height: 1),
          const SizedBox(height: 16),

          // Navigation Items - Simplified (Lloyd's moved to Settings)
          Expanded(
            child: Builder(
              builder: (context) {
                final l10n = AppLocalizations.of(context)!;
                return ListView(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  children: [
                    _SidebarItem(
                      icon: Icons.dashboard_outlined,
                      activeIcon: Icons.dashboard,
                      label: l10n.dashboard,
                      isSelected: selectedIndex == 0,
                      onTap: () => _onItemTapped(context, 0),
                    ),
                    _SidebarItem(
                      icon: Icons.assessment_outlined,
                      activeIcon: Icons.assessment,
                      label: l10n.reports,
                      isSelected: selectedIndex == 1,
                      onTap: () => _onItemTapped(context, 1),
                    ),

                    const SizedBox(height: 24),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      child: Text(
                        l10n.analytics.toUpperCase(),
                        style: const TextStyle(
                          color: Colors.white38,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 1.2,
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),

                    _SidebarItem(
                      icon: Icons.chat_bubble_outline,
                      activeIcon: Icons.chat_bubble,
                      label: l10n.chat,
                      isSelected: selectedIndex == 2,
                      onTap: () => _onItemTapped(context, 2),
                      showBadge: false,
                      isPremium: false,
                    ),

                    const SizedBox(height: 24),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      child: Text(
                        l10n.documents.toUpperCase(),
                        style: const TextStyle(
                          color: Colors.white38,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 1.2,
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),

                    // Training - Upload docs to improve AI
                    _SidebarItem(
                      icon: Icons.model_training_outlined,
                      activeIcon: Icons.model_training,
                      label: 'Training',
                      isSelected: selectedIndex == 3,
                      onTap: subscriptionService.isPremium
                          ? () => _onItemTapped(context, 3)
                          : () => _showSidebarUpgradeDialog(context, 'Training'),
                      isPremium: !subscriptionService.isPremium,
                    ),
                    // Documents - Premium only (show with PRO badge for lower tiers)
                    _SidebarItem(
                      icon: Icons.folder_outlined,
                      activeIcon: Icons.folder,
                      label: l10n.documents,
                      isSelected: selectedIndex == 4,
                      onTap: subscriptionService.isPremium
                          ? () => _onItemTapped(context, 4)
                          : () => _showSidebarUpgradeDialog(context, 'Documents'),
                      isPremium: !subscriptionService.isPremium,
                    ),

                    const SizedBox(height: 24),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      child: Text(
                        l10n.settings.toUpperCase(),
                        style: const TextStyle(
                          color: Colors.white38,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 1.2,
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),

                    _SidebarItem(
                      icon: Icons.settings_outlined,
                      activeIcon: Icons.settings,
                      label: l10n.settings,
                      isSelected: selectedIndex == 5,
                      onTap: () => _onItemTapped(context, 5),
                    ),
                  ],
                );
              },
            ),
          ),

          // User Profile at bottom - with popup menu
          _UserProfileMenu(onNavigate: onNavigate),
        ],
      ),
    );
  }
}

class _SidebarItem extends StatelessWidget {
  final IconData icon;
  final IconData activeIcon;
  final String label;
  final bool isSelected;
  final VoidCallback onTap;
  final bool showBadge;
  final bool isPremium;

  const _SidebarItem({
    required this.icon,
    required this.activeIcon,
    required this.label,
    required this.isSelected,
    required this.onTap,
    this.showBadge = false,
    this.isPremium = false,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(10),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: isSelected ? Colors.white.withOpacity(0.15) : Colors.transparent,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              children: [
                Stack(
                  clipBehavior: Clip.none,
                  children: [
                    Icon(
                      isSelected ? activeIcon : icon,
                      color: isSelected ? Colors.white : Colors.white70,
                      size: 22,
                    ),
                    if (showBadge && !isSelected)
                      Positioned(
                        right: -4,
                        top: -4,
                        child: Container(
                          width: 8,
                          height: 8,
                          decoration: BoxDecoration(
                            color: AppTheme.danger,
                            shape: BoxShape.circle,
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Row(
                    children: [
                      Flexible(
                        child: Text(
                          label,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                            color: isSelected ? Colors.white : Colors.white70,
                          ),
                        ),
                      ),
                      if (isPremium) ...[
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.amber,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text(
                            'PRO',
                            style: TextStyle(
                              color: Colors.black87,
                              fontSize: 9,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                if (isSelected)
                  Container(
                    width: 4,
                    height: 20,
                    decoration: BoxDecoration(
                      color: AppTheme.accent,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Bottom Navigation Bar for Mobile - 5 tabs with Training
class _BottomNavBar extends StatelessWidget {
  const _BottomNavBar();

  int _calculateSelectedIndex(BuildContext context) {
    final String location = GoRouterState.of(context).uri.toString();

    // Dashboard → Assessments → Training → AI Chat → Settings
    if (location.startsWith('/home')) return 0;
    if (location.startsWith('/reports')) return 1;
    if (location.startsWith('/training') || location.startsWith('/documents')) return 2;
    if (location.startsWith('/chat')) return 3;
    // Settings tab includes Lloyd's Market pages
    if (location.startsWith('/settings') || location.startsWith('/lloyds')) return 4;

    return 0;
  }

  void _onItemTapped(BuildContext context, int index) {
    switch (index) {
      case 0:
        context.go('/home');
        break;
      case 1:
        context.go('/reports');
        break;
      case 2:
        context.go('/documents');
        break;
      case 3:
        context.go('/chat');
        break;
      case 4:
        context.go('/settings');
        break;
    }
  }

  void _showUpgradeDialog(BuildContext context, String featureName) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Row(
          children: [
            Icon(Icons.lock, color: Colors.amber),
            const SizedBox(width: 8),
            const Text('Premium Feature'),
          ],
        ),
        content: Text(
          '$featureName is available for Premium users. Upgrade your subscription to access this feature.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              context.go('/settings/subscription');
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryDark,
            ),
            child: const Text('Upgrade'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final selectedIndex = _calculateSelectedIndex(context);

    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surface,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.08),
            blurRadius: 20,
            offset: const Offset(0, -5),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _NavItem(
                key: const Key('navTab_0'),
                icon: Icons.dashboard_outlined,
                activeIcon: Icons.dashboard,
                label: AppLocalizations.of(context)?.home ?? 'Home',
                isSelected: selectedIndex == 0,
                onTap: () => _onItemTapped(context, 0),
              ),
              _NavItem(
                key: const Key('navTab_1'),
                icon: Icons.assessment_outlined,
                activeIcon: Icons.assessment,
                label: AppLocalizations.of(context)?.reports ?? 'Assess',
                isSelected: selectedIndex == 1,
                onTap: () => _onItemTapped(context, 1),
              ),
              // Documents - Premium only (show with lock for lower tiers)
              _NavItem(
                key: const Key('navTab_2'),
                icon: Icons.description_outlined,
                activeIcon: Icons.description,
                label: 'Docs',
                isSelected: selectedIndex == 2,
                onTap: subscriptionService.isPremium
                    ? () => _onItemTapped(context, 2)
                    : () => _showUpgradeDialog(context, 'Documents'),
                isPremium: !subscriptionService.isPremium,
              ),
              // Chat
              _NavItem(
                key: const Key('navTab_3'),
                icon: Icons.chat_bubble_outline,
                activeIcon: Icons.chat_bubble,
                label: AppLocalizations.of(context)?.chat ?? 'Chat',
                isSelected: selectedIndex == 3,
                onTap: () => _onItemTapped(context, 3),
                showBadge: false,
                isPremium: false,
              ),
              _NavItem(
                key: const Key('navTab_4'),
                icon: Icons.settings_outlined,
                activeIcon: Icons.settings,
                label: AppLocalizations.of(context)?.settings ?? 'Settings',
                isSelected: selectedIndex == 4,
                onTap: () => _onItemTapped(context, 4),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final IconData activeIcon;
  final String label;
  final bool isSelected;
  final VoidCallback onTap;
  final bool showBadge;
  final bool isPremium;

  const _NavItem({
    super.key,
    required this.icon,
    required this.activeIcon,
    required this.label,
    required this.isSelected,
    required this.onTap,
    this.showBadge = false,
    this.isPremium = false,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.primaryDark.withOpacity(0.1) : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Stack(
              clipBehavior: Clip.none,
              children: [
                Icon(
                  isSelected ? activeIcon : icon,
                  color: isSelected ? AppTheme.primaryDark : AppTheme.textHint,
                  size: 24,
                ),
                if (showBadge && !isSelected)
                  Positioned(
                    right: -4,
                    top: -4,
                    child: Container(
                      width: 10,
                      height: 10,
                      decoration: BoxDecoration(
                        color: AppTheme.danger,
                        shape: BoxShape.circle,
                        border: Border.all(color: AppTheme.surface, width: 1.5),
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 4),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                    color: isSelected ? AppTheme.primaryDark : AppTheme.textHint,
                  ),
                ),
                if (isPremium) ...[
                  const SizedBox(width: 2),
                  Icon(
                    Icons.lock,
                    size: 10,
                    color: Colors.amber,
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// User Profile Menu - Shows popup with Settings/Logout
class _UserProfileMenu extends StatelessWidget {
  final VoidCallback? onNavigate;

  const _UserProfileMenu({this.onNavigate});

  void _showUserMenu(BuildContext context) {
    final RenderBox button = context.findRenderObject() as RenderBox;
    final RenderBox overlay = Overlay.of(context).context.findRenderObject() as RenderBox;
    final RelativeRect position = RelativeRect.fromRect(
      Rect.fromPoints(
        button.localToGlobal(Offset.zero, ancestor: overlay),
        button.localToGlobal(button.size.bottomRight(Offset.zero), ancestor: overlay),
      ),
      Offset.zero & overlay.size,
    );

    final l10n = AppLocalizations.of(context);
    showMenu<String>(
      context: context,
      position: position,
      color: AppTheme.surface,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      items: [
        PopupMenuItem<String>(
          value: 'settings',
          child: Row(
            children: [
              Icon(Icons.settings_outlined, size: 20, color: AppTheme.textPrimary),
              const SizedBox(width: 12),
              Text(l10n.settings),
            ],
          ),
        ),
        PopupMenuItem<String>(
          value: 'profile',
          child: Row(
            children: [
              Icon(Icons.person_outline, size: 20, color: AppTheme.textPrimary),
              const SizedBox(width: 12),
              Text(l10n.profile),
            ],
          ),
        ),
        const PopupMenuDivider(),
        PopupMenuItem<String>(
          value: 'logout',
          child: Row(
            children: [
              Icon(Icons.logout, size: 20, color: AppTheme.danger),
              const SizedBox(width: 12),
              Text(l10n.logOut, style: TextStyle(color: AppTheme.danger)),
            ],
          ),
        ),
      ],
    ).then((value) {
      if (value == null) return;
      onNavigate?.call();

      switch (value) {
        case 'settings':
          context.go('/settings');
          break;
        case 'profile':
          context.go('/settings/profile');
          break;
        case 'logout':
          _confirmLogout(context);
          break;
      }
    });
  }

  void _confirmLogout(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final navigator = GoRouter.of(context);

    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(l10n?.logOut ?? 'Log Out'),
        content: Text(l10n?.logOutConfirmation ?? 'Are you sure you want to log out?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: Text(l10n?.cancel ?? 'Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(dialogContext);
              // Clear cache and logout
              documentsPrefetchService.clearCache();
              await authService.logout();
              // Navigate to welcome screen using the captured navigator
              if (context.mounted) {
                navigator.go('/welcome');
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.danger,
            ),
            child: Text(l10n?.logOut ?? 'Log Out'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // Get user data from auth service
    final user = authService.user;
    final fullName = user?['full_name'] ?? user?['name'] ?? 'User';
    final email = user?['email'] ?? '';
    final initials = fullName.isNotEmpty
        ? fullName.split(' ').map((n) => n.isNotEmpty ? n[0] : '').take(2).join().toUpperCase()
        : 'U';

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => _showUserMenu(context),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            border: Border(top: BorderSide(color: Colors.white12)),
          ),
          child: Row(
            children: [
              CircleAvatar(
                radius: 18,
                backgroundColor: AppTheme.accent,
                child: Text(
                  initials,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      fullName,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (email.isNotEmpty)
                      Text(
                        email,
                        style: const TextStyle(
                          color: Colors.white60,
                          fontSize: 11,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                  ],
                ),
              ),
              Icon(
                Icons.more_vert,
                color: Colors.white60,
                size: 20,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
