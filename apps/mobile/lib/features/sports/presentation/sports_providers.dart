import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/app/di/providers.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/sports/data/sports_repository.dart';
import 'package:yelisport/features/sports/domain/sport.dart';

final sportsRepositoryProvider = Provider<SportsRepository>(
  (ref) => SportsRepository(ref.watch(apiClientProvider)),
);

final sportsProvider = FutureProvider.autoDispose<List<Sport>>((ref) {
  ref.watch(authStateProvider);
  return ref.watch(sportsRepositoryProvider).listSports();
});
