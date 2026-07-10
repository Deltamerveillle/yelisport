class UserSettings {
  const UserSettings({
    required this.language,
    required this.darkMode,
    required this.notificationsEnabled,
  });

  factory UserSettings.fromJson(Map<String, dynamic> json) {
    return UserSettings(
      language: json['language'] as String? ?? 'fr',
      darkMode: json['dark_mode'] as bool? ?? false,
      notificationsEnabled: json['notifications_enabled'] as bool? ?? true,
    );
  }

  final String language;
  final bool darkMode;
  final bool notificationsEnabled;
}
