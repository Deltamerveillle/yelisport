import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/features/events/presentation/create_event_screen.dart';
import 'package:yelisport/features/events/presentation/event_tile.dart';
import 'package:yelisport/features/events/presentation/events_providers.dart';
import 'package:yelisport/features/events/presentation/my_events_screen.dart';

class EventsScreen extends ConsumerWidget {
  const EventsScreen({super.key});

  Future<void> _register(BuildContext context, WidgetRef ref, String eventId) async {
    try {
      await ref.read(eventsRepositoryProvider).register(eventId);
      ref.invalidate(myEventsProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Inscription confirmée.')),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Inscription impossible.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final events = ref.watch(upcomingEventsProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Événements'),
        actions: [
          IconButton(
            tooltip: 'Mes événements',
            icon: const Icon(Icons.event_available),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const MyEventsScreen()),
            ),
          ),
          IconButton(
            tooltip: 'Créer un événement',
            icon: const Icon(Icons.add),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const CreateEventScreen()),
            ),
          ),
        ],
      ),
      body: events.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: TextButton(
            onPressed: () => ref.invalidate(upcomingEventsProvider),
            child: const Text('Réessayer'),
          ),
        ),
        data: (items) => items.isEmpty
            ? const Center(child: Text('Aucun événement à venir.'))
            : RefreshIndicator(
                onRefresh: () async {
                  await ref.refresh(upcomingEventsProvider.future);
                },
                child: ListView.builder(
                  itemCount: items.length,
                  itemBuilder: (context, index) => EventTile(
                    event: items[index],
                    actionLabel: "S'inscrire",
                    onAction: () => _register(context, ref, items[index].id),
                  ),
                ),
              ),
      ),
    );
  }
}
