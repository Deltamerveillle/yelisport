import 'package:dio/dio.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class ApiClient {
  ApiClient({required Uri baseUrl, required SupabaseClient supabase})
    : _supabase = supabase,
      _dio = Dio(
        BaseOptions(
          baseUrl: baseUrl.toString(),
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 10),
          headers: const {'Accept': 'application/json'},
        ),
      );

  final Dio _dio;
  final SupabaseClient _supabase;

  Future<List<dynamic>> getList(
    String path, {
    Map<String, dynamic>? queryParameters,
  }) async {
    final token = _supabase.auth.currentSession?.accessToken;
    final response = await _dio.get<List<dynamic>>(
      path,
      queryParameters: queryParameters,
      options: Options(
        headers: token == null ? null : {'Authorization': 'Bearer $token'},
      ),
    );
    return response.data ?? const [];
  }

  Future<Map<String, dynamic>> getObject(String path) async {
    final token = _supabase.auth.currentSession?.accessToken;
    final response = await _dio.get<Map<String, dynamic>>(
      path,
      options: Options(
        headers: token == null ? null : {'Authorization': 'Bearer $token'},
      ),
    );
    return response.data ?? const {};
  }

  Future<Map<String, dynamic>> postObject(
    String path, {
    Map<String, dynamic>? data,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      path,
      data: data,
      options: Options(headers: _authHeaders()),
    );
    return response.data ?? const {};
  }

  Future<Map<String, dynamic>> deleteObject(String path) async {
    final response = await _dio.delete<Map<String, dynamic>>(
      path,
      options: Options(headers: _authHeaders()),
    );
    return response.data ?? const {};
  }

  Map<String, String>? _authHeaders() {
    final token = _supabase.auth.currentSession?.accessToken;
    return token == null ? null : {'Authorization': 'Bearer $token'};
  }
}
