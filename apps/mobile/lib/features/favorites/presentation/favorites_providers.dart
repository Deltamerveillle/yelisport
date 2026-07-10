import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/app/di/providers.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/favorites/data/favorites_repository.dart';

final favoritesRepositoryProvider = Provider<FavoritesRepository>(
  (ref) => FavoritesRepository(ref.watch(supabaseProvider)),
);

final favoriteSportIdsProvider = FutureProvider.autoDispose<Set<String>>((ref) {
  ref.watch(authStateProvider);
  return ref.watch(favoritesRepositoryProvider).favoriteSportIds();
});

final favoriteEventIdsProvider = FutureProvider.autoDispose<Set<String>>((ref) {
  ref.watch(authStateProvider);
  return ref.watch(favoritesRepositoryProvider).favoriteEventIds();
});
