import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/events/presentation/events_screen.dart';
import 'package:yelisport/features/events/presentation/my_events_screen.dart';
import 'package:yelisport/features/favorites/presentation/favorites_providers.dart';
import 'package:yelisport/features/favorites/presentation/favorites_screen.dart';
import 'package:yelisport/features/profile/presentation/profile_providers.dart';
import 'package:yelisport/features/profile/presentation/profile_screen.dart';
import 'package:yelisport/features/settings/presentation/settings_screen.dart';
import 'package:yelisport/features/sports/presentation/sport_detail_screen.dart';
import 'package:yelisport/features/sports/presentation/sports_providers.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sports = ref.watch(sportsProvider);
    final profile = ref.watch(profileProvider);
    final user = ref.watch(authRepositoryProvider).currentSession?.user;
    final favoriteSports =
        ref.watch(favoriteSportIdsProvider).valueOrNull ?? const <String>{};
    final displayName = profile.valueOrNull?.displayName;
    return Scaffold(
      appBar: AppBar(
        title: const Text('YeliSport'),
        actions: [
          IconButton(
            tooltip: 'Mes favoris',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const FavoritesScreen()),
            ),
            icon: const Icon(Icons.favorite),
          ),
          IconButton(
            tooltip: 'Mon profil',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const ProfileScreen()),
            ),
            icon: const Icon(Icons.person),
          ),
          IconButton(
            tooltip: 'Paramètres',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const SettingsScreen()),
            ),
            icon: const Icon(Icons.settings),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          await ref.refresh(sportsProvider.future);
        },
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      displayName != null && displayName.isNotEmpty
                          ? 'Bienvenue, $displayName'
                          : 'Bienvenue',
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                    if (user?.email != null) Text(user!.email!),
                    const SizedBox(height: 18),
                    Wrap(
                      spacing: 10,
                      children: [
                        FilledButton.icon(
                          icon: const Icon(Icons.event),
                          label: const Text('Événements'),
                          onPressed: () => Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => const EventsScreen(),
                            ),
                          ),
                        ),
                        OutlinedButton.icon(
                          icon: const Icon(Icons.event_available),
                          label: const Text('Mes événements'),
                          onPressed: () => Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => const MyEventsScreen(),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 24),
                    Text('Sports', style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 12),
                    TextField(
                      decoration: const InputDecoration(
                        hintText: 'Rechercher un sport',
                        prefixIcon: Icon(Icons.search),
                        border: OutlineInputBorder(),
                      ),
                      onChanged: (value) {
                        ref.read(sportSearchProvider.notifier).state = value;
                      },
                    ),
                  ],
                ),
              ),
            ),
            sports.when(
              loading: () => const SliverFillRemaining(
                child: Center(child: CircularProgressIndicator()),
              ),
              error: (error, _) => SliverFillRemaining(
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text('Impossible de charger les sports.'),
                      TextButton(
                        onPressed: () => ref.invalidate(sportsProvider),
                        child: const Text('Réessayer'),
                      ),
                    ],
                  ),
                ),
              ),
              data: (items) {
                if (items.isEmpty) {
                  return const SliverFillRemaining(
                    child: Center(child: Text('Aucun sport trouvé.')),
                  );
                }
                return SliverList.separated(
                  itemCount: items.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final sport = items[index];
                    return ListTile(
                      leading: const CircleAvatar(child: Icon(Icons.sports_soccer)),
                      title: Text(sport.name),
                      subtitle: sport.description == null ? null : Text(sport.description!),
                      trailing: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          IconButton(
                            tooltip: favoriteSports.contains(sport.id)
                                ? 'Retirer des favoris'
                                : 'Ajouter aux favoris',
                            icon: Icon(
                              favoriteSports.contains(sport.id)
                                  ? Icons.favorite
                                  : Icons.favorite_border,
                            ),
                            onPressed: () async {
                              await ref.read(favoritesRepositoryProvider).toggleSport(
                                    sport.id,
                                    favorite: !favoriteSports.contains(sport.id),
                                  );
                              ref.invalidate(favoriteSportIdsProvider);
                            },
                          ),
                          const Icon(Icons.chevron_right),
                        ],
                      ),
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => SportDetailScreen(slug: sport.slug),
                        ),
                      ),
                    );
                  },
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
