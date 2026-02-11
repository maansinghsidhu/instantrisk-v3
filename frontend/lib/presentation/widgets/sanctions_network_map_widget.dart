import 'package:flutter/material.dart';
import 'package:graphview/GraphView.dart';
import 'dart:math' as math;
import '../../core/theme/app_theme.dart';

/// Enhanced Network Map Widget with Force-Directed Layout
/// Displays sanctions screening results as an interactive network graph
///
/// Features:
/// - Force-directed layout for natural node positioning
/// - Entity-type icons (person, company, vessel)
/// - Animated glow for high-risk nodes
/// - Interactive zoom controls
/// - Tap nodes to see detailed information
/// - Color-coded risk levels
class SanctionsNetworkMapWidget extends StatefulWidget {
  final Map<String, dynamic> networkData;
  final Function(String entityId)? onNodeTap;

  const SanctionsNetworkMapWidget({
    super.key,
    required this.networkData,
    this.onNodeTap,
  });

  @override
  State<SanctionsNetworkMapWidget> createState() => _SanctionsNetworkMapWidgetState();
}

class _SanctionsNetworkMapWidgetState extends State<SanctionsNetworkMapWidget>
    with SingleTickerProviderStateMixin {
  final Graph graph = Graph()..isTree = false;
  final Map<String, Node> nodeMap = {};

  // Zoom and pan
  final TransformationController _transformController = TransformationController();
  double _currentScale = 1.0;

  // Animation for high-risk nodes
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  // Selected node for detail view
  String? _selectedNodeId;

  @override
  void initState() {
    super.initState();
    _buildGraph();

    // Setup pulse animation for high-risk nodes
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat(reverse: true);

    _pulseAnimation = Tween<double>(begin: 0.3, end: 0.8).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _transformController.dispose();
    super.dispose();
  }

  void _buildGraph() {
    final nodes = widget.networkData['nodes'] as List<dynamic>? ?? [];
    final edges = widget.networkData['edges'] as List<dynamic>? ?? [];

    // Create nodes
    for (final nodeData in nodes) {
      final id = nodeData['id']?.toString() ?? '';
      final node = Node.Id(id);
      nodeMap[id] = node;
      graph.addNode(node);
    }

    // Create edges
    for (final edgeData in edges) {
      final sourceId = edgeData['source']?.toString() ?? '';
      final targetId = edgeData['target']?.toString() ?? '';

      final sourceNode = nodeMap[sourceId];
      final targetNode = nodeMap[targetId];

      if (sourceNode != null && targetNode != null) {
        graph.addEdge(sourceNode, targetNode);
      }
    }
  }

  Color _getNodeColor(Map<String, dynamic> nodeData) {
    final type = nodeData['type']?.toString() ?? '';
    final score = (nodeData['score'] ?? 0).toDouble();

    if (type == 'sanctions_match' || score >= 80) {
      return const Color(0xFFDC2626); // Red-600
    } else if (type == 'pep_match' || score >= 60) {
      return const Color(0xFFEA580C); // Orange-600
    } else if (type == 'related') {
      return const Color(0xFFD97706); // Amber-600
    }
    return const Color(0xFF2563EB); // Blue-600
  }

  IconData _getEntityIcon(Map<String, dynamic> nodeData) {
    final role = nodeData['role']?.toString().toLowerCase() ?? '';
    final type = nodeData['entity_type']?.toString().toLowerCase() ?? '';

    if (role.contains('vessel') || type.contains('vessel') || type.contains('ship')) {
      return Icons.directions_boat;
    } else if (role.contains('company') || type.contains('company') || type.contains('corporate')) {
      return Icons.business;
    } else if (role.contains('director') || role.contains('officer')) {
      return Icons.badge;
    } else if (role.contains('shareholder') || role.contains('ubo')) {
      return Icons.account_balance;
    }
    return Icons.person;
  }

  Map<String, dynamic>? _getNodeData(String nodeId) {
    final nodes = widget.networkData['nodes'] as List<dynamic>? ?? [];
    for (final node in nodes) {
      if (node['id']?.toString() == nodeId) {
        return Map<String, dynamic>.from(node);
      }
    }
    return null;
  }

  String? _getEdgeLabel(String sourceId, String targetId) {
    final edges = widget.networkData['edges'] as List<dynamic>? ?? [];
    for (final edge in edges) {
      if (edge['source']?.toString() == sourceId &&
          edge['target']?.toString() == targetId) {
        return edge['relationship']?.toString();
      }
    }
    return null;
  }

  void _zoomIn() {
    final currentScale = _transformController.value.getMaxScaleOnAxis();
    final newScale = math.min(currentScale * 1.3, 3.0);
    _transformController.value = Matrix4.identity()..scale(newScale);
    setState(() => _currentScale = newScale);
  }

  void _zoomOut() {
    final currentScale = _transformController.value.getMaxScaleOnAxis();
    final newScale = math.max(currentScale / 1.3, 0.3);
    _transformController.value = Matrix4.identity()..scale(newScale);
    setState(() => _currentScale = newScale);
  }

  void _resetZoom() {
    _transformController.value = Matrix4.identity();
    setState(() => _currentScale = 1.0);
  }

  void _showNodeDetail(Map<String, dynamic> nodeData) {
    final name = nodeData['name']?.toString() ?? 'Unknown';
    final type = nodeData['type']?.toString() ?? 'unknown';
    final role = nodeData['role']?.toString() ?? 'Entity';
    final score = (nodeData['score'] ?? 0).toDouble();
    final datasets = nodeData['datasets'] as List<dynamic>? ?? [];
    final matchedName = nodeData['matched_name']?.toString();
    final color = _getNodeColor(nodeData);

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) => Container(
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Handle bar
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey[300],
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 20),

            // Header
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(
                    _getEntityIcon(nodeData),
                    color: color,
                    size: 28,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        name,
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        role.replaceAll('_', ' ').toUpperCase(),
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: color,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ],
                  ),
                ),
                if (score > 0)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    decoration: BoxDecoration(
                      color: color,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      '${score.toStringAsFixed(0)}%',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
                    ),
                  ),
              ],
            ),

            const SizedBox(height: 24),

            // Risk Status
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: color.withOpacity(0.05),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: color.withOpacity(0.2)),
              ),
              child: Row(
                children: [
                  Icon(
                    type == 'sanctions_match' ? Icons.warning_amber :
                    type == 'pep_match' ? Icons.star :
                    type == 'related' ? Icons.link : Icons.check_circle,
                    color: color,
                    size: 24,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          type == 'sanctions_match' ? 'SANCTIONS MATCH' :
                          type == 'pep_match' ? 'PEP MATCH' :
                          type == 'related' ? 'RELATED ENTITY' : 'CLEAR',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            color: color,
                            letterSpacing: 0.5,
                          ),
                        ),
                        if (matchedName != null) ...[
                          const SizedBox(height: 4),
                          Text(
                            'Matched: $matchedName',
                            style: const TextStyle(
                              fontSize: 13,
                              color: AppTheme.textSecondary,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ),

            // Datasets
            if (datasets.isNotEmpty) ...[
              const SizedBox(height: 16),
              const Text(
                'SANCTIONS LISTS',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textSecondary,
                  letterSpacing: 1,
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: datasets.map((ds) => Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppTheme.background,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Text(
                    ds.toString().toUpperCase(),
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                )).toList(),
              ),
            ],

            const SizedBox(height: 24),

            // Close button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pop(context),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryDark,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  'Close',
                  style: TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
            ),
            SizedBox(height: MediaQuery.of(context).padding.bottom),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final nodes = widget.networkData['nodes'] as List<dynamic>? ?? [];
    final edges = widget.networkData['edges'] as List<dynamic>? ?? [];

    // Count high-risk nodes
    final highRiskCount = nodes.where((n) {
      final score = (n['score'] ?? 0).toDouble();
      return score >= 80 || n['type'] == 'sanctions_match';
    }).length;

    if (nodes.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(32),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: AppTheme.border),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.background,
                shape: BoxShape.circle,
              ),
              child: Icon(
                Icons.hub_outlined,
                size: 48,
                color: AppTheme.textHint,
              ),
            ),
            const SizedBox(height: 16),
            const Text(
              'No network data available',
              style: TextStyle(
                color: AppTheme.textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Run "Extensive" screening to generate\nthe entity network map',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: AppTheme.textSecondary,
                fontSize: 13,
                height: 1.4,
              ),
            ),
          ],
        ),
      );
    }

    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.border),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  AppTheme.primaryDark.withOpacity(0.05),
                  Colors.transparent,
                ],
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
              ),
              borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [Colors.orange.shade400, Colors.orange.shade600],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.orange.withOpacity(0.3),
                        blurRadius: 8,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: const Icon(
                    Icons.hub,
                    color: Colors.white,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Entity Network Map',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '${nodes.length} entities • ${edges.length} connections',
                        style: const TextStyle(
                          fontSize: 13,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
                // High risk badge
                if (highRiskCount > 0)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: Colors.red.shade50,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: Colors.red.shade200),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.warning_amber, size: 14, color: Colors.red.shade700),
                        const SizedBox(width: 4),
                        Text(
                          '$highRiskCount high-risk',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: Colors.red.shade700,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),

          // Legend
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(
              children: [
                _buildLegendItem(const Color(0xFFDC2626), 'Sanctions Match'),
                const SizedBox(width: 16),
                _buildLegendItem(const Color(0xFFEA580C), 'PEP'),
                const SizedBox(width: 16),
                _buildLegendItem(const Color(0xFFD97706), 'Related'),
                const SizedBox(width: 16),
                _buildLegendItem(const Color(0xFF2563EB), 'Clear'),
              ],
            ),
          ),

          const Divider(height: 32),

          // Graph View with zoom controls
          Stack(
            children: [
              // Graph
              SizedBox(
                height: 450,
                child: ClipRRect(
                  borderRadius: const BorderRadius.vertical(bottom: Radius.circular(20)),
                  child: InteractiveViewer(
                    transformationController: _transformController,
                    constrained: false,
                    boundaryMargin: const EdgeInsets.all(200),
                    minScale: 0.3,
                    maxScale: 3.0,
                    onInteractionEnd: (details) {
                      setState(() {
                        _currentScale = _transformController.value.getMaxScaleOnAxis();
                      });
                    },
                    child: GraphView(
                      graph: graph,
                      algorithm: FruchtermanReingoldAlgorithm(
                        FruchtermanReingoldConfiguration(
                          iterations: 500,
                          attractionRate: 0.5,
                          repulsionRate: 1.0,
                        ),
                      ),
                      paint: Paint()
                        ..color = AppTheme.border.withOpacity(0.6)
                        ..strokeWidth = 2
                        ..style = PaintingStyle.stroke,
                      builder: (Node node) {
                        final nodeId = node.key?.value?.toString() ?? '';
                        final nodeData = _getNodeData(nodeId);
                        return _buildEnhancedNode(nodeId, nodeData);
                      },
                    ),
                  ),
                ),
              ),

              // Zoom controls
              Positioned(
                right: 16,
                bottom: 16,
                child: Container(
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.1),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      _buildZoomButton(Icons.add, _zoomIn),
                      Container(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Text(
                          '${(_currentScale * 100).toInt()}%',
                          style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ),
                      _buildZoomButton(Icons.remove, _zoomOut),
                      const Divider(height: 1),
                      _buildZoomButton(Icons.fit_screen, _resetZoom),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildLegendItem(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: color.withOpacity(0.4),
                blurRadius: 4,
                offset: const Offset(0, 1),
              ),
            ],
          ),
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: const TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w500,
            color: AppTheme.textSecondary,
          ),
        ),
      ],
    );
  }

  Widget _buildZoomButton(IconData icon, VoidCallback onPressed) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onPressed,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Icon(icon, size: 20, color: AppTheme.textSecondary),
        ),
      ),
    );
  }

  Widget _buildEnhancedNode(String nodeId, Map<String, dynamic>? nodeData) {
    final name = nodeData?['name']?.toString() ?? nodeId;
    final type = nodeData?['type']?.toString() ?? 'unknown';
    final score = (nodeData?['score'] ?? 0).toDouble();
    final datasets = nodeData?['datasets'] as List<dynamic>? ?? [];
    final role = nodeData?['role']?.toString() ?? '';

    final color = _getNodeColor(nodeData ?? {});
    final isHighRisk = type == 'sanctions_match' || score >= 80;
    final icon = _getEntityIcon(nodeData ?? {});

    return GestureDetector(
      onTap: () {
        if (nodeData != null) {
          _showNodeDetail(nodeData);
        }
        widget.onNodeTap?.call(nodeId);
      },
      child: AnimatedBuilder(
        animation: _pulseAnimation,
        builder: (context, child) {
          return Container(
            constraints: const BoxConstraints(
              maxWidth: 160,
              minWidth: 110,
            ),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: color,
                width: isHighRisk ? 3 : 2,
              ),
              boxShadow: [
                BoxShadow(
                  color: color.withOpacity(isHighRisk ? _pulseAnimation.value : 0.15),
                  blurRadius: isHighRisk ? 16 : 8,
                  spreadRadius: isHighRisk ? 2 : 0,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: child,
          );
        },
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Icon with gradient background
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      color.withOpacity(0.15),
                      color.withOpacity(0.05),
                    ],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  shape: BoxShape.circle,
                  border: Border.all(color: color.withOpacity(0.3)),
                ),
                child: Icon(
                  isHighRisk ? Icons.warning_amber : icon,
                  color: color,
                  size: 22,
                ),
              ),
              const SizedBox(height: 10),

              // Name
              Text(
                name,
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                  height: 1.2,
                ),
              ),

              // Role badge
              if (role.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(
                  role.replaceAll('_', ' ').toUpperCase(),
                  style: TextStyle(
                    fontSize: 9,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textHint,
                    letterSpacing: 0.5,
                  ),
                ),
              ],

              // Score badge
              if (score > 0) ...[
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    '${score.toStringAsFixed(0)}%',
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                    ),
                  ),
                ),
              ],

              // Dataset tags
              if (datasets.isNotEmpty) ...[
                const SizedBox(height: 6),
                Wrap(
                  spacing: 4,
                  runSpacing: 4,
                  alignment: WrapAlignment.center,
                  children: datasets.take(2).map((ds) => Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppTheme.background,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      ds.toString().toUpperCase(),
                      style: const TextStyle(
                        fontSize: 8,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textHint,
                      ),
                    ),
                  )).toList(),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
