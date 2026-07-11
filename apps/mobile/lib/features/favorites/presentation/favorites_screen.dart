import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/features/events/presentation/event_tile.dart';
import 'package:yelisport/features/events/presentation/events_providers.dart';
import 'package:yelisport/features/favorites/presentation/favorites_providers.dart';
import 'package:yelisport/features/sports/presentation/sports_providers.dart';

class FavoritesScreen extends ConsumerWidget {
  const FavoritesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sportIds = ref.watch(favoriteSportIdsProvider).valueOrNull ?? const <String>{};
    final eventIds = ref.watch(favoriteEventIdsProvider).valueOrNull ?? const <String>{};
    final sports = ref.watch(allSportsProvider).valueOrNull ?? const [];
    final events = ref.watch(upcomingEventsProvider).valueOrNull ?? const [];
    final favoriteSports = sports.where((item) => sportIds.contains(item.id)).toList();
    final favoriteEvents = events.where((item) => eventIds.contains(item.id)).toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Mes favoris')),
      body: ListView(
        padding: const EdgeInsets.symmetric(vertical: 12),
        children: [
          const ListTile(title: Text('Sports')),
          if (favoriteSports.isEmpty)
            const ListTile(title: Text('Aucun sport favori.'))
          else
            for (final sport in favoriteSports)
              ListTile(
                leading: const Icon(Icons.favorite),
                title: Text(sport.name),
              ),
          const Divider(),
          const ListTile(title: Text('Événements')),
          if (favoriteEvents.isEmpty)
            const ListTile(title: Text('Aucun événement favori.'))
          else
            for (final event in favoriteEvents)
              EventTile(
                event: event,
                actionLabel: 'Favori',
                onAction: null,
                isFavorite: true,
                onFavorite: () async {
                  await ref
                      .read(favoritesRepositoryProvider)
                      .toggleEvent(event.id, favorite: false);
                  ref.invalidate(favoriteEventIdsProvider);
                },
              ),
        ],
      ),
    );
  }
}
