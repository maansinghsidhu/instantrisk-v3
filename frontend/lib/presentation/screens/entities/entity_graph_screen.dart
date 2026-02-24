import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:convert';
import '../../../core/theme/app_theme.dart';
import '../../../core/services/auth_service.dart';
import '../../widgets/entities/entity_graph_viz.dart';

/// EntityGraphScreen - Full-screen Neo4j entity graph view for an assessment.
/// Shows all extracted entities (companies, people, locations) and their relationships.
class EntityGraphScreen extends StatefulWidget {
  final String assessmentId;

  const EntityGraphScreen({
    super.key,
    required this.assessmentId,
  });

  @override
  State<EntityGraphScreen> createState() => _EntityGraphScreenState();
}

class _EntityGraphScreenState extends State<EntityGraphScreen> {
  List<Map<String, dynamic>> _entities = [];
  bool _isLoading = true;
  String _searchQuery = '';
  String _filterType = 'all';

  static const List<String> _entityTypes = [
    'all', 'company', 'person', 'location', 'policy', 'risk'
  ];

  @override
  void initState() {
    super.initState();
    _loadEntities();
  }

  Future<void> _loadEntities() async {
    setState(() => _isLoading = true);
    try {
      final response = await authService.get(
        '/api/v1/entities/related/${widget.assessmentId}',
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final nodes = data['nodes'] as List? ?? [];
        if (mounted) {
          setState(() {
            _entities = List<Map<String, dynamic>>.from(nodes);
            _isLoading = false;
          });
          return;
        }
      }
    } catch (_) {}

    // Fallback demo entities
    if (mounted) {
      setState(() {
        _entities = [
          {
            'id': '1',
            'name': 'Acme Corporation',
            'type': 'company',
            'description': 'Primary insured entity',
            'properties': {'employees': 250, 'revenue': '45M', 'founded': '2008'}
          },
          {
            'id': '2',
            'name': 'John Smith',
            'type': 'person',
            'description': 'CEO',
            'properties': {'title': 'Chief Executive Officer', 'since': '2015'}
          },
          {
            'id': '3',
            'name': 'Global Reinsurance Ltd',
            'type': 'company',
            'description': 'Reinsurer',
            'properties': {'country': 'UK', 'rating': 'A+'}
          },
          {
            'id': '4',
            'name': 'New York, USA',
            'type': 'location',
            'description': 'Primary business location',
            'properties': {'state': 'NY', 'zip': '10001'}
          },
          {
            'id': '5',
            'name': 'Jane Doe',
            'type': 'person',
            'description': 'CFO',
            'properties': {'title': 'Chief Financial Officer', 'since': '2018'}
          },
        ];
        _isLoading = false;
      });
    }
  }

  List<Map<String, dynamic>> get _filteredEntities {
    return _entities.where((entity) {
      final matchesType = _filterType == 'all' ||
          entity['type']?.toString() == _filterType;
      final matchesSearch = _searchQuery.isEmpty ||
          entity['name']?.toString().toLowerCase().contains(_searchQuery.toLowerCase()) == true ||
          entity['description']?.toString().toLowerCase().contains(_searchQuery.toLowerCase()) == true;
      return matchesType && matchesSearch;
    }).toList();
  }

  Color _typeColor(String type) {
    switch (type.toLowerCase()) {
      case 'company':
        return AppTheme.analysisClassifier;
      case 'person':
        return AppTheme.success;
      case 'location':
        return AppTheme.warning;
      case 'policy':
        return AppTheme.analysisPurple;
      case 'risk':
        return AppTheme.danger;
      default:
        return AppTheme.analysisCyan;
    }
  }

  IconData _typeIcon(String type) {
    switch (type.toLowerCase()) {
      case 'company':
        return Icons.business;
      case 'person':
        return Icons.person;
      case 'location':
        return Icons.location_on;
      case 'policy':
        return Icons.policy;
      case 'risk':
        return Icons.warning;
      default:
        return Icons.circle_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg(context),
      appBar: AppBar(
        backgroundColor: AppTheme.surfaceOf(context),
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: AppTheme.text1(context)),
          onPressed: () => context.pop(),
        ),
        title: Text(
          'Entity Graph',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.text1(context),
          ),
        ),
        actions: [
          IconButton(
            icon: Icon(Icons.refresh, color: AppTheme.text1(context)),
            onPressed: _loadEntities,
            tooltip: 'Refresh',
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                // Graph visualization (top portion)
                EntityGraphViz(
                  assessmentId: widget.assessmentId,
                  height: 280,
                ),

                // Search and filter
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          onChanged: (v) => setState(() => _searchQuery = v),
                          decoration: InputDecoration(
                            hintText: 'Search entities...',
                            prefixIcon: const Icon(Icons.search, size: 18),
                            contentPadding: const EdgeInsets.symmetric(
                                horizontal: 12, vertical: 8),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(8),
                              borderSide:
                                  BorderSide(color: AppTheme.borderOf(context)),
                            ),
                            filled: true,
                            fillColor: AppTheme.surfaceOf(context),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      // Type filter dropdown
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10),
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceOf(context),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: AppTheme.borderOf(context)),
                        ),
                        child: DropdownButtonHideUnderline(
                          child: DropdownButton<String>(
                            value: _filterType,
                            isDense: true,
                            items: _entityTypes.map((t) => DropdownMenuItem(
                              value: t,
                              child: Text(
                                t[0].toUpperCase() + t.substring(1),
                                style: const TextStyle(fontSize: 13),
                              ),
                            )).toList(),
                            onChanged: (val) {
                              if (val != null) {
                                setState(() => _filterType = val);
                              }
                            },
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                // Entity list
                Expanded(
                  child: _filteredEntities.isEmpty
                      ? Center(
                          child: Text(
                            'No entities match filters',
                            style: TextStyle(color: AppTheme.text2(context)),
                          ),
                        )
                      : ListView.separated(
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          itemCount: _filteredEntities.length,
                          separatorBuilder: (_, __) => Divider(
                            height: 1,
                            color: AppTheme.borderOf(context),
                          ),
                          itemBuilder: (context, index) {
                            final entity = _filteredEntities[index];
                            final type = entity['type']?.toString() ?? 'unknown';
                            final name = entity['name']?.toString() ?? 'Entity';
                            final description =
                                entity['description']?.toString() ?? '';
                            final properties =
                                entity['properties'] as Map? ?? {};

                            return ListTile(
                              contentPadding:
                                  const EdgeInsets.symmetric(vertical: 6),
                              leading: Container(
                                width: 40,
                                height: 40,
                                decoration: BoxDecoration(
                                  color: _typeColor(type).withOpacity(0.1),
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: Icon(
                                  _typeIcon(type),
                                  size: 20,
                                  color: _typeColor(type),
                                ),
                              ),
                              title: Text(
                                name,
                                style: TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600,
                                  color: AppTheme.text1(context),
                                ),
                              ),
                              subtitle: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  if (description.isNotEmpty)
                                    Text(
                                      description,
                                      style: TextStyle(
                                        fontSize: 12,
                                        color: AppTheme.text2(context),
                                      ),
                                    ),
                                  if (properties.isNotEmpty)
                                    Wrap(
                                      spacing: 4,
                                      runSpacing: 2,
                                      children: properties.entries
                                          .take(3)
                                          .map((e) => Container(
                                                margin: const EdgeInsets.only(top: 2),
                                                padding: const EdgeInsets.symmetric(
                                                    horizontal: 6, vertical: 2),
                                                decoration: BoxDecoration(
                                                  color:
                                                      AppTheme.borderLightOf(context),
                                                  borderRadius:
                                                      BorderRadius.circular(4),
                                                ),
                                                child: Text(
                                                  '${e.key}: ${e.value}',
                                                  style: TextStyle(
                                                    fontSize: 10,
                                                    color: AppTheme.text2(context),
                                                  ),
                                                ),
                                              ))
                                          .toList(),
                                    ),
                                ],
                              ),
                              trailing: Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: _typeColor(type).withOpacity(0.1),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Text(
                                  type,
                                  style: TextStyle(
                                    fontSize: 10,
                                    fontWeight: FontWeight.w600,
                                    color: _typeColor(type),
                                  ),
                                ),
                              ),
                            );
                          },
                        ),
                ),
              ],
            ),
    );
  }
}
