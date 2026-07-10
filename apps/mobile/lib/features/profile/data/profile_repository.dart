import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:yelisport/features/profile/domain/user_profile.dart';

class ProfileRepository {
  const ProfileRepository(this._client);

  final SupabaseClient _client;

  Future<UserProfile> getCurrentProfile() async {
    final user = _client.auth.currentUser;
    if (user == null) {
      throw AuthException('Session utilisateur absente.');
    }
    final data = await _client
        .from('profiles')
        .select('user_id, display_name, locale')
        .eq('user_id', user.id)
        .single();
    return UserProfile.fromJson(data);
  }
}
