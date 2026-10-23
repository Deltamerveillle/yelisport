import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/features/sports/presentation/sports_providers.dart';
import 'package:yelisport/features/sports/presentation/athlete_enrollment_screen.dart';

class SportDetailScreen extends ConsumerWidget {
  const SportDetailScreen({required this.slug, this.onReturn, super.key});

  final String slug;
  final VoidCallback? onReturn;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sport = ref.watch(sportDetailProvider(slug));
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          tooltip: 'Retour à tous les sports',
          onPressed: onReturn ?? () => Navigator.of(context).maybePop(),
          icon: const Icon(Icons.arrow_back),
        ),
        title: const Text('Fiche du sport'),
        actions: [
          TextButton.icon(
            onPressed: onReturn ?? () => Navigator.of(context).maybePop(),
            icon: const Icon(Icons.list),
            label: const Text('Tous les sports'),
          ),
        ],
      ),
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
            TextButton.icon(
              onPressed: onReturn ?? () => Navigator.of(context).maybePop(),
              icon: const Icon(Icons.home_outlined),
              label: const Text('Accueil › Tous les sports'),
            ),
            const SizedBox(height: 18),
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
            const SizedBox(height: 24),
            FilledButton.icon(
              icon: const Icon(Icons.person_add_alt_1),
              label: const Text('Je suis athlète • créer mon passeport'),
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => AthleteEnrollmentScreen(sport: item),
                ),
              ),
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
