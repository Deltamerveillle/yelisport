import 'package:dio/dio.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class ApiClient {
  ApiClient({required Uri baseUrl, required SupabaseClient supabase})
      : _supabase = supabase,
        _dio = Dio(
          BaseOptions(
            baseUrl: baseUrl.toString(),
            connectTimeout: const Duration(seconds: 30),
            // The free Render backend may need time to wake from an idle state.
            receiveTimeout: const Duration(seconds: 75),
            headers: const {'Accept': 'application/json'},
          ),
        );

  final Dio _dio;
  final SupabaseClient _supabase;

  /// Retry only idempotent reads after transient network/gateway failures.
  /// A 401/403 or other application response is never retried.
  Future<Response<T>> _readWithRetry<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
  }) async {
    for (var attempt = 0; ; attempt++) {
      try {
        final token = _supabase.auth.currentSession?.accessToken;
        return await _dio.get<T>(
          path,
          queryParameters: queryParameters,
          options: Options(
            headers: token == null ? null : {'Authorization': 'Bearer $token'},
          ),
        );
      } on DioException catch (error) {
        if (attempt >= 1 || !_isTransientReadFailure(error)) rethrow;
        await Future<void>.delayed(const Duration(seconds: 2));
      }
    }
  }

  static bool _isTransientReadFailure(DioException error) {
    if (error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.receiveTimeout ||
        error.type == DioExceptionType.connectionError) {
      return true;
    }
    final status = error.response?.statusCode;
    return status == 502 || status == 503 || status == 504;
  }

  Future<List<dynamic>> getList(
    String path, {
    Map<String, dynamic>? queryParameters,
  }) async {
    final response = await _readWithRetry<List<dynamic>>(
      path,
      queryParameters: queryParameters,
    );
    return response.data ?? const [];
  }

  Future<Map<String, dynamic>> getObject(
    String path, {
    Map<String, dynamic>? queryParameters,
  }) async {
    final response = await _readWithRetry<Map<String, dynamic>>(
      path,
      queryParameters: queryParameters,
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

  Future<Map<String, dynamic>> patchObject(
    String path, {
    Map<String, dynamic>? data,
  }) async {
    final response = await _dio.patch<Map<String, dynamic>>(
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
