import 'dart:convert';
import 'auth_service.dart';

/// RapidRate Service - ML-powered insurance pricing
class RapidRateService {
  static final RapidRateService _instance = RapidRateService._internal();
  factory RapidRateService() => _instance;
  RapidRateService._internal();

  String get _baseUrl => authService.baseUrl;

  /// Calculate premium using RapidRate ML model
  Future<Map<String, dynamic>> calculatePremium({
    required String policyType,
    required String state,
    required double exposure,
    double limit = 1000000,
    double deductible = 5000,
    String industry = 'general',
    double experienceMod = 1.0,
    int yearsInBusiness = 5,
    Map<String, dynamic>? lossHistory,
  }) async {
    final token = await authService.token;
    if (token == null) throw Exception('Not authenticated');

    final response = await authService.post('/rapidrate/price', body: {
      'policy_type': policyType,
      'state': state,
      'exposure': exposure,
      'limit': limit,
      'deductible': deductible,
      'industry': industry,
      'experience_mod': experienceMod,
      'years_in_business': yearsInBusiness,
      'loss_history': lossHistory,
    });

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('RapidRate pricing failed: ${response.statusCode}');
    }
  }

  /// Run Monte Carlo simulation
  Future<Map<String, dynamic>> simulate({
    required String policyType,
    required String state,
    required double exposure,
    double limit = 1000000,
    double deductible = 5000,
    int simulations = 10000,
  }) async {
    final token = await authService.token;
    if (token == null) throw Exception('Not authenticated');

    final response = await authService.post('/rapidrate/simulate', body: {
      'policy_type': policyType,
      'state': state,
      'exposure': exposure,
      'limit': limit,
      'deductible': deductible,
      'simulations': simulations,
    });

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('RapidRate simulation failed: ${response.statusCode}');
    }
  }

  /// Get base rates table
  Future<Map<String, dynamic>> getBaseRates() async {
    final token = await authService.token;
    if (token == null) throw Exception('Not authenticated');

    final response = await authService.get('/rapidrate/base-rates');

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load base rates: ${response.statusCode}');
    }
  }
}
