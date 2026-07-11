import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/features/events/presentation/event_tile.dart';
import 'package:yelisport/features/events/presentation/events_providers.dart';
import 'package:yelisport/features/favorites/presentation/favorites_providers.dart';

class MyEventsScreen extends ConsumerWidget {
  const MyEventsScreen({super.key});

  Future<void> _cancel(BuildContext context, WidgetRef ref, String eventId) async {
    try {
      await ref.read(eventsRepositoryProvider).cancel(eventId);
      ref.invalidate(myEventsProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Inscription annulée.')),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Annulation impossible.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final events = ref.watch(myEventsProvider);
    final favorites = ref.watch(favoriteEventIdsProvider).valueOrNull ?? const <String>{};
    return Scaffold(
      appBar: AppBar(title: const Text('Mes événements')),
      body: events.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: TextButton(
            onPressed: () => ref.invalidate(myEventsProvider),
            child: const Text('Réessayer'),
          ),
        ),
        data: (items) => items.isEmpty
            ? const Center(child: Text("Vous n'êtes inscrit à aucun événement."))
            : ListView.builder(
                itemCount: items.length,
                itemBuilder: (context, index) => EventTile(
                  event: items[index],
                  isFavorite: favorites.contains(items[index].id),
                  onFavorite: () async {
                    final id = items[index].id;
                    await ref.read(favoritesRepositoryProvider).toggleEvent(
                          id,
                          favorite: !favorites.contains(id),
                        );
                    ref.invalidate(favoriteEventIdsProvider);
                  },
                  actionLabel: "Annuler l'inscription",
                  onAction: () => _cancel(context, ref, items[index].id),
                ),
              ),
      ),
    );
  }
}
