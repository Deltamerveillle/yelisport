import 'package:yelisport/app/config/environment.dart';

class AppConfig {
  const AppConfig({
    required this.environment,
    required this.apiBaseUrl,
    required this.supabaseUrl,
    required this.supabaseAnonKey,
  });

  factory AppConfig.fromEnvironment() {
    const environmentName = String.fromEnvironment(
      'APP_ENV',
      defaultValue: 'development',
    );
    const apiBaseUrl = String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://localhost:8080/api/v1',
    );
    const supabaseUrl = String.fromEnvironment(
      'SUPABASE_URL',
      defaultValue: 'http://localhost:54321',
    );
    const supabaseAnonKey = String.fromEnvironment(
      'SUPABASE_ANON_KEY',
      defaultValue: 'change-me',
    );
    return AppConfig(
      environment: Environment.fromName(environmentName),
      apiBaseUrl: Uri.parse(apiBaseUrl),
      supabaseUrl: Uri.parse(supabaseUrl),
      supabaseAnonKey: supabaseAnonKey,
    );
  }

  final Environment environment;
  final Uri apiBaseUrl;
  final Uri supabaseUrl;
  final String supabaseAnonKey;
}
