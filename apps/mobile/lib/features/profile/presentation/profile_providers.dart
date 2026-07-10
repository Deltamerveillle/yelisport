import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/app/di/providers.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/profile/data/profile_repository.dart';
import 'package:yelisport/features/profile/domain/user_profile.dart';

final profileRepositoryProvider = Provider<ProfileRepository>(
  (ref) => ProfileRepository(ref.watch(supabaseProvider)),
);

final profileProvider = FutureProvider.autoDispose<UserProfile>((ref) {
  ref.watch(authStateProvider);
  return ref.watch(profileRepositoryProvider).getCurrentProfile();
});
