import 'package:yelisport/app/config/environment.dart';

class AppConfig {
  const AppConfig({required this.environment, required this.apiBaseUrl});

  factory AppConfig.fromEnvironment() {
    const environmentName = String.fromEnvironment(
      'APP_ENV',
      defaultValue: 'development',
    );
    const apiBaseUrl = String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://localhost:8080/api/v1',
    );
    return AppConfig(
      environment: Environment.fromName(environmentName),
      apiBaseUrl: Uri.parse(apiBaseUrl),
    );
  }

  final Environment environment;
  final Uri apiBaseUrl;
}
