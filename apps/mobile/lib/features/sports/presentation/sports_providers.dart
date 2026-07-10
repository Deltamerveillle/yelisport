import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/app/di/providers.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/sports/data/sports_repository.dart';
import 'package:yelisport/features/sports/domain/sport.dart';

final sportsRepositoryProvider = Provider<SportsRepository>(
  (ref) => SportsRepository(ref.watch(apiClientProvider)),
);

final sportSearchProvider = StateProvider.autoDispose<String>((ref) => '');

final sportsProvider = FutureProvider.autoDispose<List<Sport>>((ref) {
  ref.watch(authStateProvider);
  final search = ref.watch(sportSearchProvider).trim();
  if (search.length == 1) return Future.value(const []);
  return ref
      .watch(sportsRepositoryProvider)
      .listSports(search: search.isEmpty ? null : search);
});

final sportDetailProvider = FutureProvider.autoDispose.family<Sport, String>(
  (ref, slug) {
    ref.watch(authStateProvider);
    return ref.watch(sportsRepositoryProvider).getSport(slug);
  },
);
