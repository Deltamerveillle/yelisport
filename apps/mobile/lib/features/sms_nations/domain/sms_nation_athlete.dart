class SmsNationAthlete {
  const SmsNationAthlete({
    required this.athleteId,
    required this.firstName,
    required this.lastName,
    required this.sportId,
    required this.sportSlug,
    required this.sportName,
    required this.talentEvaluated,
    this.city,
    this.avatarUrl,
    this.residenceCountryId,
    this.residenceCountryIso2,
    this.residenceCountryName,
    this.discipline,
    this.category,
    this.position,
    this.clubName,
    this.leagueName,
    this.teamName,
    this.availableForOpportunities,
    this.eligibilityCountryId,
    this.eligibilityStatus,
    this.eligibilityIsPrimary,
    this.discoverVideoId,
    this.discoverVideoUrl,
    this.discoverThumbnailUrl,
    this.discoverCaption,
    this.discoverDurationSeconds,
    this.talentScore,
    this.talentCompletedAt,
  });

  factory SmsNationAthlete.fromJson(Map<String, dynamic> json) {
    return SmsNationAthlete(
      athleteId: json['athlete_id'] as String,
      firstName: json['first_name'] as String,
      lastName: json['last_name'] as String,
      sportId: json['sport_id'] as String,
      sportSlug: json['sport_slug'] as String,
      sportName: json['sport_name'] as String,
      talentEvaluated: json['talent_evaluated'] as bool? ?? false,
      city: json['city'] as String?,
      avatarUrl: json['avatar_url'] as String?,
      residenceCountryId: json['residence_country_id'] as String?,
      residenceCountryIso2: json['residence_country_iso2'] as String?,
      residenceCountryName: json['residence_country_name'] as String?,
      discipline: json['discipline'] as String?,
      category: json['category'] as String?,
      position: json['position'] as String?,
      clubName: json['club_name'] as String?,
      leagueName: json['league_name'] as String?,
      teamName: json['team_name'] as String?,
      availableForOpportunities:
          json['available_for_opportunities'] as bool?,
      eligibilityCountryId: json['eligibility_country_id'] as String?,
      eligibilityStatus: json['eligibility_status'] as String?,
      eligibilityIsPrimary: json['eligibility_is_primary'] as bool?,
      discoverVideoId: json['discover_video_id'] as String?,
      discoverVideoUrl: json['discover_video_url'] as String?,
      discoverThumbnailUrl:
          json['discover_thumbnail_url'] as String?,
      discoverCaption: json['discover_caption'] as String?,
      discoverDurationSeconds:
          json['discover_duration_seconds'] as int?,
      talentScore: json['talent_score'] == null
          ? null
          : double.tryParse(json['talent_score'].toString()),
      talentCompletedAt: json['talent_completed_at'] == null
          ? null
          : DateTime.tryParse(
              json['talent_completed_at'] as String,
            ),
    );
  }

  final String athleteId;
  final String firstName;
  final String lastName;
  final String sportId;
  final String sportSlug;
  final String sportName;
  final bool talentEvaluated;
  final String? city;
  final String? avatarUrl;
  final String? residenceCountryId;
  final String? residenceCountryIso2;
  final String? residenceCountryName;
  final String? discipline;
  final String? category;
  final String? position;
  final String? clubName;
  final String? leagueName;
  final String? teamName;
  final bool? availableForOpportunities;
  final String? eligibilityCountryId;
  final String? eligibilityStatus;
  final bool? eligibilityIsPrimary;
  final String? discoverVideoId;
  final String? discoverVideoUrl;
  final String? discoverThumbnailUrl;
  final String? discoverCaption;
  final int? discoverDurationSeconds;
  final double? talentScore;
  final DateTime? talentCompletedAt;

  String get fullName => '$firstName $lastName';

}

class SmsNationsSearchResult {
  const SmsNationsSearchResult({
    required this.items,
    required this.total,
    required this.limit,
    required this.offset,
  });

  factory SmsNationsSearchResult.fromJson(Map<String, dynamic> json) {
    return SmsNationsSearchResult(
      items: (json['items'] as List<dynamic>)
          .map(
            (item) => SmsNationAthlete.fromJson(
              item as Map<String, dynamic>,
            ),
          )
          .toList(growable: false),
      total: json['total'] as int,
      limit: json['limit'] as int,
      offset: json['offset'] as int,
    );
  }

  final List<SmsNationAthlete> items;
  final int total;
  final int limit;
  final int offset;

}
