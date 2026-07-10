import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/app/di/providers.dart';
import 'package:yelisport/features/sports/data/sports_repository.dart';
import 'package:yelisport/features/sports/domain/sport.dart';

final sportsRepositoryProvider = Provider<SportsRepository>(
  (ref) => SportsRepository(ref.watch(apiClientProvider)),
);

final sportsProvider = FutureProvider<List<Sport>>(
  (ref) => ref.watch(sportsRepositoryProvider).listSports(),
);
