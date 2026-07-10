import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:yelisport/features/settings/domain/user_settings.dart';

class SettingsRepository {
  const SettingsRepository(this._client);

  final SupabaseClient _client;

  Future<UserSettings> getSettings() async {
    final userId = _requireUserId();
    final data = await _client.from('user_settings').select().eq('user_id', userId).single();
    return UserSettings.fromJson(data);
  }

  Future<void> update(UserSettings settings) async {
    await _client.from('user_settings').upsert({
      'user_id': _requireUserId(),
      'language': settings.language,
      'dark_mode': settings.darkMode,
      'notifications_enabled': settings.notificationsEnabled,
    });
  }

  String _requireUserId() {
    final id = _client.auth.currentUser?.id;
    if (id == null) throw AuthException('Session utilisateur absente.');
    return id;
  }
}
