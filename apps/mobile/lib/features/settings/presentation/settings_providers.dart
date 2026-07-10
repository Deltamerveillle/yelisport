import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/app/di/providers.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/settings/data/settings_repository.dart';
import 'package:yelisport/features/settings/domain/user_settings.dart';

final settingsRepositoryProvider = Provider<SettingsRepository>(
  (ref) => SettingsRepository(ref.watch(supabaseProvider)),
);

final settingsProvider = FutureProvider.autoDispose<UserSettings>((ref) {
  ref.watch(authStateProvider);
  return ref.watch(settingsRepositoryProvider).getSettings();
});
