import 'package:yelisport/core/network/api_client.dart';
import 'package:yelisport/features/events/domain/sport_event.dart';

class EventsRepository {
  const EventsRepository(this._api);

  final ApiClient _api;

  Future<List<SportEvent>> listUpcoming() => _list('/events');
  Future<List<SportEvent>> listMine() => _list('/events/mine');

  Future<SportEvent> create(EventDraft draft) async {
    final data = await _api.postObject('/events', data: draft.toJson());
    return SportEvent.fromJson(data);
  }

  Future<void> register(String eventId) async {
    await _api.postObject('/events/$eventId/registrations');
  }

  Future<void> cancel(String eventId) async {
    await _api.deleteObject('/events/$eventId/registrations/me');
  }

  Future<List<SportEvent>> _list(String path) async {
    final data = await _api.getList(path);
    return data
        .map((item) => SportEvent.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }
}
