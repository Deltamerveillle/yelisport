import 'package:flutter/material.dart';
import 'package:yelisport/app/theme/app_colors.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/auth/presentation/sign_in_screen.dart';
import 'package:yelisport/features/auth/presentation/sign_up_screen.dart';
import 'package:yelisport/features/sports/presentation/sms24_sport_banner.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/features/sports/presentation/sports_providers.dart';
import 'package:yelisport/features/sports/presentation/athlete_enrollment_screen.dart';

class SportDetailScreen extends ConsumerWidget {
  const SportDetailScreen({required this.slug, this.onReturn, super.key});

  final String slug;
  final VoidCallback? onReturn;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Rebuild when a visitor signs in without losing the chosen discipline.
    ref.watch(authStateProvider);
    final loggedIn = ref.watch(authRepositoryProvider).currentSession != null;
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
        data: (item) => Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1040),
            child: ListView(
              padding: const EdgeInsets.all(24),
              children: [
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: onReturn ?? () => Navigator.of(context).maybePop(),
                    icon: const Icon(Icons.arrow_back),
                    label: const Text('Accueil  ›  Tous les sports'),
                  ),
                ),
                const SizedBox(height: 12),
                Sms24SportBanner(
                  title: item.name,
                  subtitle: 'Explorez cette discipline et créez votre profil '
                      'sportif pour présenter vos performances au monde.',
                  icon: iconForSport(item.slug),
                ),
                const SizedBox(height: 22),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(22),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Votre talent mérite d’être vu',
                          style: Theme.of(context).textTheme.titleLarge),
                        const SizedBox(height: 10),
                        const Text(
                          'Sélectionnez votre sport, vérifiez votre abonnement, '
                          'complétez votre passeport et déposez une vidéo '
                          'courte ou vos photos, sous réserve de modération.',
                        ),
                        const SizedBox(height: 18),
                        FilledButton.icon(
                          icon: Icon(loggedIn
                              ? Icons.badge_outlined
                              : Icons.person_add_alt_1),
                          label: Text(loggedIn
                              ? 'Accéder à mon passeport sportif'
                              : 'Créer mon compte pour poursuivre'),
                          onPressed: () => Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => loggedIn
                                  ? AthleteEnrollmentScreen(sport: item)
                                  : const SignUpScreen(),
                            ),
                          ),
                        ),
                        if (!loggedIn) ...[
                          const SizedBox(height: 10),
                          OutlinedButton.icon(
                            icon: const Icon(Icons.login),
                            label: const Text('Déjà inscrit ? Se connecter'),
                            onPressed: () => Navigator.of(context).push(
                              MaterialPageRoute<void>(
                                builder: (_) => const SignInScreen(),
                              ),
                            ),
                          ),
                          const SizedBox(height: 8),
                          const Text(
                            'La création du compte est gratuite. '
                            'La création du passeport et le dépôt de médias '
                            'nécessitent ensuite un abonnement actif.',
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
                if (item.description != null && item.description!.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Text(item.description!),
                    ),
                  ),
                ],
                const SizedBox(height: 18),
                Row(children: [
                  const Icon(Icons.info_outline, color: AppColors.primary),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Rencontres, classements et actualités apparaîtront '
                      'lorsque des sources vérifiées alimenteront ce sport.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                ]),
              ],
            ),
          ),
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
    'badminton' => Icons.sports_tennis,
    'boxing' => Icons.sports_mma,
    'cycling' => Icons.directions_bike,
    'futsal' => Icons.sports_soccer,
    'judo' => Icons.sports_martial_arts,
    'wrestling' => Icons.sports_mma,
    'swimming' => Icons.pool,
    'taekwondo' => Icons.sports_martial_arts,
    'table-tennis' => Icons.sports_tennis,
    'cricket' => Icons.sports_cricket,
    _ => Icons.sports,
  };
}
