import 'package:yelisport/core/network/api_client.dart';
import 'package:yelisport/features/sports/domain/sport.dart';

class SportsRepository {
  const SportsRepository(this._api);

  final ApiClient _api;

  Future<List<Sport>> listSports({String? search}) async {
    final data = await _api.getList(
      '/sports',
      queryParameters: search == null || search.isEmpty
          ? null
          : {'search': search},
    );
    return data
        .map((item) => Sport.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }

  Future<Sport> getSport(String slug) async {
    final data = await _api.getObject('/sports/$slug');
    return Sport.fromJson(data);
  }
}
