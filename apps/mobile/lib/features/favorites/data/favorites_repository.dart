import 'package:supabase_flutter/supabase_flutter.dart';

class FavoritesRepository {
  const FavoritesRepository(this._client);

  final SupabaseClient _client;

  Future<Set<String>> favoriteSportIds() => _ids('favorite_sports', 'sport_id');
  Future<Set<String>> favoriteEventIds() => _ids('favorite_events', 'event_id');

  Future<void> toggleSport(String sportId, {required bool favorite}) {
    return _toggle('favorite_sports', 'sport_id', sportId, favorite: favorite);
  }

  Future<void> toggleEvent(String eventId, {required bool favorite}) {
    return _toggle('favorite_events', 'event_id', eventId, favorite: favorite);
  }

  Future<Set<String>> _ids(String table, String column) async {
    final data = await _client.from(table).select(column).eq('user_id', _userId);
    return data.map((row) => row[column] as String).toSet();
  }

  Future<void> _toggle(
    String table,
    String column,
    String targetId, {
    required bool favorite,
  }) async {
    final query = _client.from(table);
    if (favorite) {
      await query.upsert({'user_id': _userId, column: targetId});
    } else {
      await query.delete().eq('user_id', _userId).eq(column, targetId);
    }
  }

  String get _userId {
    final id = _client.auth.currentUser?.id;
    if (id == null) throw AuthException('Session utilisateur absente.');
    return id;
  }
}
