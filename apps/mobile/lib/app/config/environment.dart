enum Environment {
  development,
  staging,
  production;

  static Environment fromName(String value) {
    return Environment.values.firstWhere(
      (environment) => environment.name == value,
      orElse: () => Environment.development,
    );
  }
}
