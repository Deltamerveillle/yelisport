import 'package:yelisport/core/network/api_client.dart';
import 'package:yelisport/features/sms_connect/domain/sms_connect_models.dart';

class SMSConnectRepository {
  const SMSConnectRepository(this._api);
  final ApiClient _api;

  Future<List<SMSConnectInterest>> inbox() async {
    final data = await _api.getList('/sms-connect/athlete/inbox');
    return data
        .map(
            (item) => SMSConnectInterest.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }

  Future<List<SMSConnectOpportunity>> opportunities() async {
    final data = await _api.getList('/sms-connect/athlete/opportunities');
    return data
        .map((item) =>
            SMSConnectOpportunity.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }

  Future<SMSConnectInterest> respond(
      String interestId, AthleteDecision decision) async {
    final json = await _api.patchObject(
      '/sms-connect/athlete/interests/${Uri.encodeComponent(interestId)}/response',
      data: {'athlete_response': decision.name},
    );
    final result = SMSConnectInterest.fromJson(json);
    if (result.id != interestId ||
        result.athleteResponse.name != decision.name) {
      throw const FormatException('Unexpected SMS Connect response');
    }
    return result;
  }
}
