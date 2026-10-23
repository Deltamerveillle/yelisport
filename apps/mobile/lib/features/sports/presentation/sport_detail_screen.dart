import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/features/sports/presentation/sports_providers.dart';

class SportDetailScreen extends ConsumerWidget {
  const SportDetailScreen({required this.slug, super.key});

  final String slug;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sport = ref.watch(sportDetailProvider(slug));
    return Scaffold(
      appBar: AppBar(title: const Text('Fiche du sport')),
      body: sport.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('Impossible de charger ce sport.'),
              TextButton(
                onPressed: () => ref.invalidate(sportDetailProvider(slug)),
                child: const Text('Réessayer'),
              ),
            ],
          ),
        ),
        data: (item) => ListView(
          padding: const EdgeInsets.all(24),
          children: [
            CircleAvatar(
              radius: 44,
              child: Icon(iconForSport(item.slug), size: 44),
            ),
            const SizedBox(height: 24),
            Text(
              item.name,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            if (item.description != null) ...[
              const SizedBox(height: 20),
              Text(item.description!, textAlign: TextAlign.center),
            ],
          ],
        ),
      ),
    );
  }

}

IconData iconForSport(String sportSlug) {
  return switch (sportSlug) {
    'basketball' => Icons.sports_basketball,
    'rugby' => Icons.sports_rugby,
    'handball' => Icons.sports_handball,
    'volleyball' => Icons.sports_volleyball,
    'tennis' => Icons.sports_tennis,
    'baseball' => Icons.sports_baseball,
    'american-football' => Icons.sports_football,
    'hockey' => Icons.sports_hockey,
    'golf' => Icons.sports_golf,
    'athletics' => Icons.directions_run,
    'football' => Icons.sports_soccer,
    _ => Icons.sports,
  };
}
