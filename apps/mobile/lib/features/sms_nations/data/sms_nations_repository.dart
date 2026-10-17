import 'package:yelisport/core/network/api_client.dart';
import 'package:yelisport/features/sms_nations/domain/sms_nation_athlete.dart';

class SmsNationsRepository {
  const SmsNationsRepository(this._api);

  final ApiClient _api;

  Future<SmsNationsSearchResult> searchAthletes({
    String? eligibilityCountryId,
    String? residenceCountryId,
    String? sportId,
    String? discipline,
    String? search,
    bool? availableForOpportunities,
    int limit = 24,
    int offset = 0,
  }) async {
    final query = <String, dynamic>{
      'limit': limit,
      'offset': offset,
      if (eligibilityCountryId != null)
        'eligibility_country_id': eligibilityCountryId,
      if (residenceCountryId != null)
        'residence_country_id': residenceCountryId,
      if (sportId != null) 'sport_id': sportId,
      if (discipline != null && discipline.isNotEmpty)
        'discipline': discipline,
      if (search != null && search.trim().length >= 2)
        'search': search.trim(),
      if (availableForOpportunities != null)
        'available_for_opportunities': availableForOpportunities,
    };

    final data = await _api.getObject(
      '/sms-nations/athletes',
      queryParameters: query,
    );

    return SmsNationsSearchResult.fromJson(data);
  }
}
