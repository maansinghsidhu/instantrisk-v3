import 'package:flutter/material.dart';
import 'dart:math' as math;
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import 'dart:convert';

/// EntityGraphViz - Interactive Neo4j-style entity relationship graph visualization.
/// Shows companies, people, and their relationships extracted from insurance documents.
class EntityGraphViz extends StatefulWidget {
  final String assessmentId;
  final double height;
  final VoidCallback? onFullScreen;

  const EntityGraphViz({
    super.key,
    required this.assessmentId,
    this.height = 300,
    this.onFullScreen,
  });

  @override
  State<EntityGraphViz> createState() => _EntityGraphVizState();
}

class _EntityGraphVizState extends State<EntityGraphViz>
    with SingleTickerProviderStateMixin {
  List<_GraphNode> _nodes = [];
  List<_GraphEdge> _edges = [];
  bool _isLoading = true;
  String? _selectedNodeId;
  Offset _panOffset = Offset.zero;
  double _scale = 1.0;
  late AnimationController _animController;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );
    _loadEntityGraph();
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  Future<void> _loadEntityGraph() async {
    try {
      final response = await authService.get(
        '/assessments/${widget.assessmentId}/entities',
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        _buildGraph(data);
        return;
      }
    } catch (_) {}

    // Fallback: show demo graph structure
    _buildDemoGraph();
  }

  void _buildDemoGraph() {
    if (!mounted) return;
    final nodes = [
      _GraphNode(id: '1', label: 'Acme Corp', type: 'company', x: 0.5, y: 0.5),
      _GraphNode(id: '2', label: 'John Smith', type: 'person', x: 0.2, y: 0.3),
      _GraphNode(id: '3', label: 'Global Re', type: 'company', x: 0.8, y: 0.3),
      _GraphNode(id: '4', label: 'Policy #001', type: 'policy', x: 0.5, y: 0.8),
      _GraphNode(id: '5', label: 'Jane Doe', type: 'person', x: 0.2, y: 0.7),
    ];
    final edges = [
      _GraphEdge(fromId: '1', toId: '2', label: 'CEO'),
      _GraphEdge(fromId: '1', toId: '3', label: 'reinsured_by'),
      _GraphEdge(fromId: '1', toId: '4', label: 'has_policy'),
      _GraphEdge(fromId: '5', toId: '1', label: 'CFO'),
    ];
    setState(() {
      _nodes = nodes;
      _edges = edges;
      _isLoading = false;
    });
    _animController.forward();
  }

  void _buildGraph(Map<String, dynamic> data) {
    if (!mounted) return;
    final nodesData = data['nodes'] as List? ?? [];
    final edgesData = data['edges'] as List? ?? data['relationships'] as List? ?? [];

    final rng = math.Random(42);
    final nodes = nodesData.asMap().entries.map((entry) {
      final n = Map<String, dynamic>.from(entry.value as Map);
      return _GraphNode(
        id: n['id']?.toString() ?? '${entry.key}',
        label: n['label']?.toString() ?? n['name']?.toString() ?? 'Node',
        type: n['type']?.toString() ?? n['entity_type']?.toString() ?? 'unknown',
        x: (n['x'] as num?)?.toDouble() ?? rng.nextDouble(),
        y: (n['y'] as num?)?.toDouble() ?? rng.nextDouble(),
      );
    }).toList();

    final edges = edgesData.map((e) {
      final edge = Map<String, dynamic>.from(e as Map);
      return _GraphEdge(
        fromId: edge['from']?.toString() ?? edge['source']?.toString() ?? '',
        toId: edge['to']?.toString() ?? edge['target']?.toString() ?? '',
        label: edge['label']?.toString() ?? edge['type']?.toString() ?? '',
      );
    }).toList();

    setState(() {
      _nodes = nodes;
      _edges = edges;
      _isLoading = false;
    });
    _animController.forward();
  }

  Color _nodeColor(String type) {
    switch (type.toLowerCase()) {
      case 'company':
      case 'organization':
        return AppTheme.analysisClassifier;
      case 'person':
      case 'individual':
        return AppTheme.success;
      case 'policy':
        return AppTheme.analysisPurple;
      case 'location':
        return AppTheme.warning;
      case 'risk':
        return AppTheme.danger;
      default:
        return AppTheme.analysisCyan;
    }
  }

  IconData _nodeIcon(String type) {
    switch (type.toLowerCase()) {
      case 'company':
      case 'organization':
        return Icons.business;
      case 'person':
      case 'individual':
        return Icons.person;
      case 'policy':
        return Icons.policy;
      case 'location':
        return Icons.location_on;
      case 'risk':
        return Icons.warning;
      default:
        return Icons.circle;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceOf(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderOf(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: AppTheme.analysisIndigo.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.account_tree_outlined,
                    size: 18,
                    color: AppTheme.analysisIndigo,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Entity Relationships',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.text1(context),
                    ),
                  ),
                ),
                if (!_isLoading) ...[
                  Text(
                    '${_nodes.length} entities',
                    style: TextStyle(fontSize: 11, color: AppTheme.text2(context)),
                  ),
                  const SizedBox(width: 8),
                ],
                if (widget.onFullScreen != null)
                  IconButton(
                    icon: const Icon(Icons.open_in_full, size: 16),
                    onPressed: widget.onFullScreen,
                    tooltip: 'Full screen',
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                    color: AppTheme.text2(context),
                  ),
              ],
            ),
          ),

          Divider(height: 1, color: AppTheme.borderOf(context)),

          // Graph canvas
          SizedBox(
            height: widget.height,
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _nodes.isEmpty
                    ? Center(
                        child: Text(
                          'No entity data found',
                          style: TextStyle(color: AppTheme.text2(context)),
                        ),
                      )
                    : ClipRRect(
                        borderRadius: const BorderRadius.vertical(
                          bottom: Radius.circular(12),
                        ),
                        child: GestureDetector(
                          onPanUpdate: (details) {
                            setState(() => _panOffset += details.delta);
                          },
                          child: AnimatedBuilder(
                            animation: _animController,
                            builder: (context, _) {
                              return CustomPaint(
                                size: Size.infinite,
                                painter: _GraphPainter(
                                  nodes: _nodes,
                                  edges: _edges,
                                  panOffset: _panOffset,
                                  scale: _scale,
                                  selectedNodeId: _selectedNodeId,
                                  nodeColorFn: _nodeColor,
                                  nodeIconFn: _nodeIcon,
                                  animValue: _animController.value,
                                  isDark: AppTheme.isDark(context),
                                ),
                              );
                            },
                          ),
                        ),
                      ),
          ),

          // Legend
          if (!_isLoading && _nodes.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Wrap(
                spacing: 12,
                children: [
                  _LegendItem(label: 'Company', color: _nodeColor('company')),
                  _LegendItem(label: 'Person', color: _nodeColor('person')),
                  _LegendItem(label: 'Policy', color: _nodeColor('policy')),
                  _LegendItem(label: 'Location', color: _nodeColor('location')),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _GraphNode {
  final String id;
  final String label;
  final String type;
  final double x; // 0..1
  final double y; // 0..1

  _GraphNode({
    required this.id,
    required this.label,
    required this.type,
    required this.x,
    required this.y,
  });
}

class _GraphEdge {
  final String fromId;
  final String toId;
  final String label;

  _GraphEdge({required this.fromId, required this.toId, required this.label});
}

class _GraphPainter extends CustomPainter {
  final List<_GraphNode> nodes;
  final List<_GraphEdge> edges;
  final Offset panOffset;
  final double scale;
  final String? selectedNodeId;
  final Color Function(String type) nodeColorFn;
  final IconData Function(String type) nodeIconFn;
  final double animValue;
  final bool isDark;

  _GraphPainter({
    required this.nodes,
    required this.edges,
    required this.panOffset,
    required this.scale,
    required this.selectedNodeId,
    required this.nodeColorFn,
    required this.nodeIconFn,
    required this.animValue,
    required this.isDark,
  });

  Offset _nodePosition(_GraphNode node, Size size) {
    return Offset(
      node.x * size.width * scale + panOffset.dx,
      node.y * size.height * scale + panOffset.dy,
    );
  }

  @override
  void paint(Canvas canvas, Size size) {
    final edgePaint = Paint()
      ..color = (isDark ? Colors.white : Colors.black).withOpacity(0.15)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    // Draw edges
    for (final edge in edges) {
      final from = nodes.where((n) => n.id == edge.fromId).firstOrNull;
      final to = nodes.where((n) => n.id == edge.toId).firstOrNull;
      if (from == null || to == null) continue;

      final fromPos = _nodePosition(from, size);
      final toPos = _nodePosition(to, size);

      canvas.drawLine(fromPos, toPos, edgePaint);

      // Draw arrow
      final dir = (toPos - fromPos);
      final len = dir.distance;
      if (len > 0) {
        final norm = dir / len;
        final arrowPos = toPos - norm * 20;
        final perp = Offset(-norm.dy, norm.dx) * 6;
        final arrowPath = Path()
          ..moveTo(arrowPos.dx + perp.dx, arrowPos.dy + perp.dy)
          ..lineTo(toPos.dx - norm.dx * 20, toPos.dy - norm.dy * 20)
          ..lineTo(arrowPos.dx - perp.dx, arrowPos.dy - perp.dy);
        canvas.drawPath(arrowPath, edgePaint..style = PaintingStyle.stroke);

        // Edge label (center)
        if (edge.label.isNotEmpty) {
          final midX = (fromPos.dx + toPos.dx) / 2;
          final midY = (fromPos.dy + toPos.dy) / 2;
          final tp = TextPainter(
            text: TextSpan(
              text: edge.label,
              style: TextStyle(
                fontSize: 9,
                color: (isDark ? Colors.white : Colors.black).withOpacity(0.4),
              ),
            ),
            textDirection: TextDirection.ltr,
          )..layout();
          tp.paint(canvas, Offset(midX - tp.width / 2, midY - tp.height / 2));
        }
      }
    }

    // Draw nodes
    final radius = 20.0 * animValue;
    for (final node in nodes) {
      final pos = _nodePosition(node, size);
      final color = nodeColorFn(node.type);
      final isSelected = node.id == selectedNodeId;

      // Node circle
      final paint = Paint()
        ..color = color.withOpacity(0.15 + (isSelected ? 0.25 : 0))
        ..style = PaintingStyle.fill;
      canvas.drawCircle(pos, radius, paint);

      final borderPaint = Paint()
        ..color = color
        ..strokeWidth = isSelected ? 2.5 : 1.5
        ..style = PaintingStyle.stroke;
      canvas.drawCircle(pos, radius, borderPaint);

      // Node label
      final labelPainter = TextPainter(
        text: TextSpan(
          text: node.label.length > 12
              ? '${node.label.substring(0, 10)}...'
              : node.label,
          style: TextStyle(
            fontSize: 9,
            fontWeight: FontWeight.w600,
            color: isDark ? Colors.white : Colors.black87,
          ),
        ),
        textDirection: TextDirection.ltr,
        textAlign: TextAlign.center,
      )..layout(maxWidth: 80);
      labelPainter.paint(
        canvas,
        Offset(
          pos.dx - labelPainter.width / 2,
          pos.dy + radius + 3,
        ),
      );

      // Type text inside circle
      final typePainter = TextPainter(
        text: TextSpan(
          text: node.type.substring(0, math.min(3, node.type.length)).toUpperCase(),
          style: TextStyle(
            fontSize: 8,
            fontWeight: FontWeight.w700,
            color: color,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      typePainter.paint(
        canvas,
        Offset(pos.dx - typePainter.width / 2, pos.dy - typePainter.height / 2),
      );
    }
  }

  @override
  bool shouldRepaint(_GraphPainter old) =>
      old.animValue != animValue ||
      old.panOffset != panOffset ||
      old.selectedNodeId != selectedNodeId ||
      old.scale != scale;
}

class _LegendItem extends StatelessWidget {
  final String label;
  final Color color;

  const _LegendItem({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            color: color.withOpacity(0.3),
            shape: BoxShape.circle,
            border: Border.all(color: color, width: 1.5),
          ),
        ),
        const SizedBox(width: 4),
        Text(
          label,
          style: TextStyle(fontSize: 10, color: AppTheme.text2(context)),
        ),
      ],
    );
  }
}
