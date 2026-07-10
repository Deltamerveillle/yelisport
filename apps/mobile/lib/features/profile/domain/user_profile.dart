class UserProfile {
  const UserProfile({
    required this.userId,
    this.displayName,
    required this.locale,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      userId: json['user_id'] as String,
      displayName: json['display_name'] as String?,
      locale: json['locale'] as String? ?? 'fr',
    );
  }

  final String userId;
  final String? displayName;
  final String locale;
}
