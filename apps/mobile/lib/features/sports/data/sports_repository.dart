import 'package:yelisport/core/network/api_client.dart';
import 'package:yelisport/features/sports/domain/sport.dart';

class SportsRepository {
  const SportsRepository(this._api);

  final ApiClient _api;

  Future<List<Sport>> listSports() async {
    final data = await _api.getList('/sports');
    return data
        .map((item) => Sport.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }
}
