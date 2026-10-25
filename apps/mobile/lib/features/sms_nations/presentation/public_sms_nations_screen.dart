import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/app/di/providers.dart';
import 'package:yelisport/features/auth/presentation/sign_in_screen.dart';

/// Only the existing opt-in public Discover API is used for visitors.
/// Never fetch the authenticated SMS Nations directory without a session.
final publicNationsAthletesProvider = FutureProvider.autoDispose<List<dynamic>>(
  (ref) => ref.watch(apiClientProvider).getList(
    '/discover/athletes',
    queryParameters: {'limit': 50},
  ),
);

class PublicSmsNationsScreen extends ConsumerWidget {
  const PublicSmsNationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final athletes = ref.watch(publicNationsAthletesProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('SMS Nations')),
      body: RefreshIndicator(
        onRefresh: () async {
          final refreshed = ref.refresh(publicNationsAthletesProvider.future);
          await refreshed;
        },
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Text(
              'Découvrez les talents sportifs',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            const Text(
              'Seuls les sportifs ayant choisi d’apparaître dans la '
              'découverte publique peuvent être présentés ici.',
            ),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Vous êtes recruteur ou athlète ?'),
                    const SizedBox(height: 8),
                    const Text(
                      'Connectez-vous pour accéder aux services '
                      'réservés à votre compte.',
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      icon: const Icon(Icons.login),
                      label: const Text('Se connecter'),
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => const SignInScreen(),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 18),
            Text(
              'Profils publics',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            athletes.when(
              loading: () => const Center(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: CircularProgressIndicator(),
                ),
              ),
              error: (_, __) => Column(
                children: [
                  const Text('Profils publics momentanément indisponibles.'),
                  TextButton(
                    onPressed: () => ref.invalidate(publicNationsAthletesProvider),
                    child: const Text('Réessayer'),
                  ),
                ],
              ),
              data: (items) {
                if (items.isEmpty) {
                  return const Card(
                    child: Padding(
                      padding: EdgeInsets.all(20),
                      child: Text(
                        'Aucun profil public disponible actuellement. '
                        'Les athlètes pourront apparaître ici après '
                        'leur choix de visibilité et les vérifications requises.',
                      ),
                    ),
                  );
                }
                return Column(
                  children: [
                    for (final raw in items)
                      if (raw is Map)
                        _PublicAthleteCard(data: Map<String, dynamic>.from(raw)),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _PublicAthleteCard extends StatelessWidget {
  const _PublicAthleteCard({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final identity = data['athlete'];
    final passport = data['passport'];
    if (identity is! Map || passport is! Map) {
      return const SizedBox.shrink();
    }
    final first = identity['first_name']?.toString().trim() ?? '';
    final last = identity['last_name']?.toString().trim() ?? '';
    final name = '$first $last'.trim();
    final details = [
      passport['discipline'],
      passport['position'],
      passport['club_name'],
      identity['city'],
    ].whereType<String>().where((value) => value.isNotEmpty).join(' • ');

    return Card(
      child: ListTile(
        leading: const Icon(Icons.person_outline),
        title: Text(name.isEmpty ? 'Athlète' : name),
        subtitle: details.isEmpty ? null : Text(details),
      ),
    );
  }
}
