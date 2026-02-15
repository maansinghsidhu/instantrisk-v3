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

    final isDark = AppTheme.isDark(context);

    // Desktop: Permanent sidebar (>1000px)
    if (screenWidth > 1000) {
      return Scaffold(
        body: Row(
          children: [
            _Sidebar(onNavigate: null),
            // Subtle divider between sidebar and content
            Container(width: 0.5, color: AppTheme.borderOf(context).withOpacity(0.3)),
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
          backgroundColor: AppTheme.surfaceOf(context),
          elevation: 0,
          leading: IconButton(
            icon: Icon(Icons.menu_rounded, color: AppTheme.text2(context), size: 22),
            onPressed: () => _scaffoldKey.currentState?.openDrawer(),
          ),
          title: Row(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Image.asset('assets/images/logo-icon.png', width: 28, height: 28, fit: BoxFit.contain),
              ),
              const SizedBox(width: 10),
              Text(
                AppLocalizations.of(context)?.appName ?? 'InstantRisk',
                style: TextStyle(
                  color: AppTheme.text1(context),
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  letterSpacing: -0.3,
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

/// Sidebar for Web/Desktop — Clean, modern, ChatGPT-inspired
class _Sidebar extends StatelessWidget {
  final VoidCallback? onNavigate;

  const _Sidebar({this.onNavigate});

  int _calculateSelectedIndex(BuildContext context) {
    final String location = GoRouterState.of(context).uri.toString();
    if (location.startsWith('/home')) return 0;
    if (location.startsWith('/reports')) return 1;
    if (location.startsWith('/chat')) return 2;
    if (location.startsWith('/training')) return 3;
    if (location.startsWith('/documents')) return 4;
    if (location.startsWith('/settings') || location.startsWith('/lloyds')) return 5;
    return 0;
  }

  void _onItemTapped(BuildContext context, int index) {
    onNavigate?.call();
    switch (index) {
      case 0: context.go('/home'); break;
      case 1: context.go('/reports'); break;
      case 2: context.go('/chat'); break;
      case 3: context.go('/training'); break;
      case 4: context.go('/documents'); break;
      case 5: context.go('/settings'); break;
    }
  }

  void _showSidebarUpgradeDialog(BuildContext context, String featureName) {
    onNavigate?.call();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Row(
          children: [
            Icon(Icons.lock_outline_rounded, color: Colors.amber.shade600, size: 20),
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
            child: const Text('Upgrade'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final selectedIndex = _calculateSelectedIndex(context);

    final isDark = AppTheme.isDark(context);
    final sidebarBg = isDark ? AppTheme.darkBg : AppTheme.surfaceVariant;
    final sidebarText = isDark ? Colors.white : AppTheme.textPrimary;
    final sidebarTextMuted = isDark ? Colors.white.withOpacity(0.7) : AppTheme.textSecondary;
    final sidebarDivider = isDark ? Colors.white.withOpacity(0.08) : AppTheme.border;

    return Container(
      width: 260,
      color: sidebarBg,
      child: Column(
        children: [
          // Logo Header
          Container(
            padding: EdgeInsets.fromLTRB(20, onNavigate != null ? 48 : 20, 20, 16),
            child: Row(
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: Image.asset('assets/images/logo-icon.png', width: 36, height: 36, fit: BoxFit.contain),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    AppLocalizations.of(context).appName,
                    style: TextStyle(
                      color: sidebarText,
                      fontSize: 17,
                      fontWeight: FontWeight.w600,
                      letterSpacing: -0.3,
                    ),
                  ),
                ),
              ],
            ),
          ),

          Container(
            margin: const EdgeInsets.symmetric(horizontal: 16),
            height: 0.5,
            color: sidebarDivider,
          ),
          const SizedBox(height: 12),

          // Navigation Items
          Expanded(
            child: Builder(
              builder: (context) {
                final l10n = AppLocalizations.of(context)!;
                return ListView(
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                  children: [
                    _SidebarItem(
                      icon: Icons.grid_view_rounded,
                      label: l10n.dashboard,
                      isSelected: selectedIndex == 0,
                      onTap: () => _onItemTapped(context, 0),
                    ),
                    _SidebarItem(
                      icon: Icons.description_outlined,
                      label: l10n.reports,
                      isSelected: selectedIndex == 1,
                      onTap: () => _onItemTapped(context, 1),
                    ),

                    const _SectionLabel(label: 'ANALYTICS'),

                    _SidebarItem(
                      icon: Icons.auto_awesome_outlined,
                      label: l10n.chat,
                      isSelected: selectedIndex == 2,
                      onTap: () => _onItemTapped(context, 2),
                    ),

                    const _SectionLabel(label: 'DOCUMENTS'),

                    _SidebarItem(
                      icon: Icons.school_outlined,
                      label: 'Training',
                      isSelected: selectedIndex == 3,
                      onTap: subscriptionService.isPremium
                          ? () => _onItemTapped(context, 3)
                          : () => _showSidebarUpgradeDialog(context, 'Training'),
                      isPremium: !subscriptionService.isPremium,
                    ),
                    _SidebarItem(
                      icon: Icons.folder_outlined,
                      label: l10n.documents,
                      isSelected: selectedIndex == 4,
                      onTap: subscriptionService.isPremium
                          ? () => _onItemTapped(context, 4)
                          : () => _showSidebarUpgradeDialog(context, 'Documents'),
                      isPremium: !subscriptionService.isPremium,
                    ),

                    const _SectionLabel(label: 'PREFERENCES'),

                    _SidebarItem(
                      icon: Icons.tune_rounded,
                      label: l10n.settings,
                      isSelected: selectedIndex == 5,
                      onTap: () => _onItemTapped(context, 5),
                    ),
                  ],
                );
              },
            ),
          ),

          // User Profile at bottom
          _UserProfileMenu(onNavigate: onNavigate),
        ],
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String label;
  const _SectionLabel({required this.label});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 20, 14, 6),
      child: Text(
        label,
        style: TextStyle(
          color: AppTheme.textH(context),
          fontSize: 10,
          fontWeight: FontWeight.w600,
          letterSpacing: 1.5,
        ),
      ),
    );
  }
}

class _SidebarItem extends StatefulWidget {
  final IconData icon;
  final String label;
  final bool isSelected;
  final VoidCallback onTap;
  final bool showBadge;
  final bool isPremium;

  const _SidebarItem({
    required this.icon,
    required this.label,
    required this.isSelected,
    required this.onTap,
    this.showBadge = false,
    this.isPremium = false,
  });

  @override
  State<_SidebarItem> createState() => _SidebarItemState();
}

class _SidebarItemState extends State<_SidebarItem> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final isActive = widget.isSelected;
    final showHover = _isHovered && !isActive;
    final isDark = AppTheme.isDark(context);
    final activeColor = isDark ? Colors.white : AppTheme.textPrimary;
    final inactiveColor = isDark ? Colors.white.withOpacity(0.55) : AppTheme.textSecondary;
    final activeLabelColor = isDark ? Colors.white : AppTheme.textPrimary;
    final inactiveLabelColor = isDark ? Colors.white.withOpacity(0.7) : AppTheme.textSecondary;
    final hoverBg = isDark ? Colors.white.withOpacity(0.06) : AppTheme.border.withOpacity(0.5);
    final activeBg = isDark ? Colors.white.withOpacity(0.12) : AppTheme.primaryDark.withOpacity(0.08);

    return Padding(
      padding: const EdgeInsets.only(bottom: 2),
      child: MouseRegion(
        onEnter: (_) => setState(() => _isHovered = true),
        onExit: (_) => setState(() => _isHovered = false),
        child: GestureDetector(
          onTap: widget.onTap,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            curve: Curves.easeOut,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: isActive
                  ? activeBg
                  : showHover
                      ? hoverBg
                      : Colors.transparent,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                Icon(
                  widget.icon,
                  color: isActive ? activeColor : inactiveColor,
                  size: 20,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    widget.label,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: isActive ? FontWeight.w600 : FontWeight.w400,
                      color: isActive ? activeLabelColor : inactiveLabelColor,
                      letterSpacing: -0.1,
                    ),
                  ),
                ),
                if (widget.isPremium)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                    decoration: BoxDecoration(
                      color: Colors.amber.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      'PRO',
                      style: TextStyle(
                        color: Colors.amber.shade400,
                        fontSize: 9,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ),
                if (widget.showBadge && !isActive)
                  Container(
                    width: 6,
                    height: 6,
                    decoration: const BoxDecoration(
                      color: AppTheme.accent,
                      shape: BoxShape.circle,
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

/// Bottom Navigation Bar — Clean, minimal
class _BottomNavBar extends StatelessWidget {
  const _BottomNavBar();

  int _calculateSelectedIndex(BuildContext context) {
    final String location = GoRouterState.of(context).uri.toString();
    if (location.startsWith('/home')) return 0;
    if (location.startsWith('/reports')) return 1;
    if (location.startsWith('/training') || location.startsWith('/documents')) return 2;
    if (location.startsWith('/chat')) return 3;
    if (location.startsWith('/settings') || location.startsWith('/lloyds')) return 4;
    return 0;
  }

  void _onItemTapped(BuildContext context, int index) {
    switch (index) {
      case 0: context.go('/home'); break;
      case 1: context.go('/reports'); break;
      case 2: context.go('/documents'); break;
      case 3: context.go('/chat'); break;
      case 4: context.go('/settings'); break;
    }
  }

  void _showUpgradeDialog(BuildContext context, String featureName) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Row(
          children: [
            Icon(Icons.lock_outline_rounded, color: Colors.amber.shade600, size: 20),
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
        color: AppTheme.surfaceOf(context),
        border: Border(
          top: BorderSide(color: AppTheme.borderOf(context).withOpacity(0.5), width: 0.5),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _NavItem(
                key: const Key('navTab_0'),
                icon: Icons.grid_view_rounded,
                label: AppLocalizations.of(context)?.home ?? 'Home',
                isSelected: selectedIndex == 0,
                onTap: () => _onItemTapped(context, 0),
              ),
              _NavItem(
                key: const Key('navTab_1'),
                icon: Icons.description_outlined,
                label: AppLocalizations.of(context)?.reports ?? 'Assess',
                isSelected: selectedIndex == 1,
                onTap: () => _onItemTapped(context, 1),
              ),
              _NavItem(
                key: const Key('navTab_2'),
                icon: Icons.folder_outlined,
                label: 'Docs',
                isSelected: selectedIndex == 2,
                onTap: subscriptionService.isPremium
                    ? () => _onItemTapped(context, 2)
                    : () => _showUpgradeDialog(context, 'Documents'),
                isPremium: !subscriptionService.isPremium,
              ),
              _NavItem(
                key: const Key('navTab_3'),
                icon: Icons.auto_awesome_outlined,
                label: AppLocalizations.of(context)?.chat ?? 'Chat',
                isSelected: selectedIndex == 3,
                onTap: () => _onItemTapped(context, 3),
              ),
              _NavItem(
                key: const Key('navTab_4'),
                icon: Icons.tune_rounded,
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
  final String label;
  final bool isSelected;
  final VoidCallback onTap;
  final bool showBadge;
  final bool isPremium;

  const _NavItem({
    super.key,
    required this.icon,
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
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.primaryDark.withOpacity(0.08) : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Stack(
              clipBehavior: Clip.none,
              children: [
                Icon(
                  icon,
                  color: isSelected ? AppTheme.primaryDark : AppTheme.textH(context),
                  size: 22,
                ),
                if (showBadge && !isSelected)
                  Positioned(
                    right: -3,
                    top: -3,
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: AppTheme.accent,
                        shape: BoxShape.circle,
                        border: Border.all(color: AppTheme.surfaceOf(context), width: 1.5),
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 3),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                    color: isSelected ? AppTheme.primaryDark : AppTheme.textH(context),
                    letterSpacing: 0.1,
                  ),
                ),
                if (isPremium) ...[
                  const SizedBox(width: 2),
                  Icon(Icons.lock_outline_rounded, size: 9, color: Colors.amber.shade600),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// User Profile Menu — Clean minimal design
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
    final menuBg = AppTheme.isDark(context) ? AppTheme.darkCard : AppTheme.surface;
    final menuText = AppTheme.isDark(context) ? Colors.white : AppTheme.textPrimary;
    final menuTextMuted = AppTheme.isDark(context) ? Colors.white70 : AppTheme.textSecondary;

    showMenu<String>(
      context: context,
      position: position,
      color: menuBg,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      items: [
        PopupMenuItem<String>(
          value: 'settings',
          child: Row(
            children: [
              Icon(Icons.tune_rounded, size: 18, color: menuTextMuted),
              const SizedBox(width: 10),
              Text(l10n?.settings ?? 'Settings', style: TextStyle(color: menuText, fontSize: 13)),
            ],
          ),
        ),
        PopupMenuItem<String>(
          value: 'profile',
          child: Row(
            children: [
              Icon(Icons.person_outline_rounded, size: 18, color: menuTextMuted),
              const SizedBox(width: 10),
              Text(l10n?.profile ?? 'Profile', style: TextStyle(color: menuText, fontSize: 13)),
            ],
          ),
        ),
        const PopupMenuDivider(),
        PopupMenuItem<String>(
          value: 'logout',
          child: Row(
            children: [
              Icon(Icons.logout_rounded, size: 18, color: AppTheme.danger),
              const SizedBox(width: 10),
              Text(l10n?.logOut ?? 'Log out', style: TextStyle(color: AppTheme.danger, fontSize: 13)),
            ],
          ),
        ),
      ],
    ).then((value) {
      if (value == null) return;
      onNavigate?.call();
      switch (value) {
        case 'settings': context.go('/settings'); break;
        case 'profile': context.go('/settings/profile'); break;
        case 'logout': _confirmLogout(context); break;
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
              documentsPrefetchService.clearCache();
              await authService.logout();
              if (context.mounted) {
                navigator.go('/welcome');
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.danger, foregroundColor: Colors.white),
            child: Text(l10n?.logOut ?? 'Log Out'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
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
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            border: Border(top: BorderSide(color: AppTheme.borderOf(context))),
          ),
          child: Row(
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [AppTheme.primaryDark, AppTheme.primaryLight],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Center(
                  child: Text(
                    initials,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                      fontSize: 13,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      fullName,
                      style: TextStyle(
                        color: AppTheme.text1(context),
                        fontSize: 13,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    if (email.isNotEmpty)
                      Text(
                        email,
                        style: TextStyle(
                          color: AppTheme.textH(context),
                          fontSize: 11,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                  ],
                ),
              ),
              Icon(Icons.unfold_more_rounded, color: AppTheme.textH(context), size: 18),
            ],
          ),
        ),
      ),
    );
  }
}
