import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:yelisport/app/config/app_config.dart';
import 'package:yelisport/core/network/api_client.dart';

final appConfigProvider = Provider<AppConfig>(
  (ref) => AppConfig.fromEnvironment(),
);

final supabaseProvider = Provider<SupabaseClient>(
  (ref) => Supabase.instance.client,
);

final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient(
    baseUrl: ref.watch(appConfigProvider).apiBaseUrl,
    supabase: ref.watch(supabaseProvider),
  );
});
