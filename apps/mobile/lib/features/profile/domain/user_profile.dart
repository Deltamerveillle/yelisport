class UserProfile {
  const UserProfile({
    required this.userId,
    this.displayName,
    this.biography,
    this.city,
    this.country,
    this.avatarUrl,
    required this.locale,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      userId: json['user_id'] as String,
      displayName: json['display_name'] as String?,
      biography: json['biography'] as String?,
      city: json['city'] as String?,
      country: json['country'] as String?,
      avatarUrl: json['avatar_url'] as String?,
      locale: json['locale'] as String? ?? 'fr',
    );
  }

  final String userId;
  final String? displayName;
  final String? biography;
  final String? city;
  final String? country;
  final String? avatarUrl;
  final String locale;
}
