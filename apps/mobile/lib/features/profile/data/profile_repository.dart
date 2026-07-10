import 'dart:typed_data';

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
        .select(
          'user_id, display_name, biography, city, country, avatar_url, locale',
        )
        .eq('user_id', user.id)
        .single();
    return UserProfile.fromJson(data);
  }

  Future<void> updateProfile({
    required String displayName,
    required String biography,
    required String city,
    required String country,
  }) async {
    final user = _requireUser();
    await _client.from('profiles').update({
      'display_name': displayName.trim(),
      'biography': biography.trim(),
      'city': city.trim(),
      'country': country.trim(),
    }).eq('user_id', user.id);
  }

  Future<String> uploadAvatar(Uint8List bytes, String extension) async {
    final user = _requireUser();
    final path = '${user.id}/avatar.$extension';
    await _client.storage.from('avatars').uploadBinary(
          path,
          bytes,
          fileOptions: const FileOptions(upsert: true),
        );
    final url = _client.storage.from('avatars').getPublicUrl(path);
    await _client.from('profiles').update({'avatar_url': url}).eq('user_id', user.id);
    return url;
  }

  User _requireUser() {
    final user = _client.auth.currentUser;
    if (user == null) throw AuthException('Session utilisateur absente.');
    return user;
  }
}
