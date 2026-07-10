import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/app/di/providers.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/events/data/events_repository.dart';
import 'package:yelisport/features/events/domain/sport_event.dart';

final eventsRepositoryProvider = Provider<EventsRepository>(
  (ref) => EventsRepository(ref.watch(apiClientProvider)),
);

final upcomingEventsProvider = FutureProvider.autoDispose<List<SportEvent>>((ref) {
  ref.watch(authStateProvider);
  return ref.watch(eventsRepositoryProvider).listUpcoming();
});

final myEventsProvider = FutureProvider.autoDispose<List<SportEvent>>((ref) {
  ref.watch(authStateProvider);
  return ref.watch(eventsRepositoryProvider).listMine();
});
