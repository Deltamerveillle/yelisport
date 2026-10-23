import 'package:flutter/material.dart';
import 'package:yelisport/features/ads/presentation/ad_slot.dart';
import 'package:yelisport/features/sms_nations/presentation/sms_nations_screen.dart';
import 'package:yelisport/core/localization/generated/app_localizations.dart';
import 'package:yelisport/features/sms_connect/presentation/my_opportunities_screen.dart';
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
  const HomeScreen({this.onNavigate, super.key});

  final ValueChanged<int>? onNavigate;

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
        title: const Text('SMS24 • Succès Mondial Sports'),
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
          final refreshedSports = ref.refresh(sportsProvider.future);
          await refreshedSports;
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
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        color: const Color(0xFF101B30),
                        borderRadius: BorderRadius.circular(18),
                      ),
                      child: const Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'SUCCÈS MONDIAL SPORTS',
                            style: TextStyle(
                              color: Color(0xFFD6A847),
                              fontSize: 13,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 1.5,
                            ),
                          ),
                          SizedBox(height: 10),
                          Text(
                            'Aucun talent africain ne doit rester invisible.',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 21,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 18),
                    const AdSlot(),
                    const SizedBox(height: 18),
                    Text('Le sport en temps réel',
                        style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 10),
                    Wrap(spacing: 10, runSpacing: 8, children: [
                      FilledButton.icon(
                        onPressed: onNavigate == null ? null : () => onNavigate!(1),
                        icon: const Icon(Icons.sports_soccer),
                        label: const Text('Rencontres & Live'),
                      ),
                      OutlinedButton.icon(
                        onPressed: onNavigate == null ? null : () => onNavigate!(2),
                        icon: const Icon(Icons.newspaper_outlined),
                        label: const Text('Actualités'),
                      ),
                    ]),
                    const SizedBox(height: 10),
                    Text('Les résultats et les nouvelles apparaissent après '
                      'la collecte et la validation des sources.',
                      style: Theme.of(context).textTheme.bodySmall),
                    const SizedBox(height: 18),
                    Text(
                      'Les espaces SMS24',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 10),
                    Column(
                      children: [
                          Card(
                            child: ListTile(
                              leading: const Icon(Icons.public),
                              title: const Text('SMS Nations'),
                              subtitle: const Text('Découvrir les athlètes'),
                              trailing: const Icon(Icons.chevron_right),
                              onTap: () {
                                if (onNavigate != null) {
                                  onNavigate!(3);
                                } else {
                                  Navigator.of(context).push(
                                    MaterialPageRoute<void>(
                                      builder: (_) => const SmsNationsScreen(),
                                    ),
                                  );
                                }
                              },
                            ),
                          ),
                          Card(
                            child: ListTile(
                              leading: const Icon(Icons.stars),
                              title: const Text('SMS Talent'),
                              subtitle: const Text('Talents sportifs'),
                              trailing: const Text('En préparation',
                                  style: TextStyle(fontSize: 11)),
                            ),
                          ),
                          Card(
                            child: ListTile(
                              leading: const Icon(Icons.play_circle_outline),
                              title: const Text('SMS Discover'),
                              subtitle: const Text('Vidéos et découvertes'),
                              trailing: const Text('En préparation',
                                  style: TextStyle(fontSize: 11)),
                            ),
                          ),
                          Card(
                            child: ListTile(
                              leading: const Icon(Icons.badge_outlined),
                              title: const Text('SMS Passport'),
                              subtitle: const Text('Passeport sportif'),
                              trailing: const Text('En préparation',
                                  style: TextStyle(fontSize: 11)),
                            ),
                          ),
                          Card(
                            child: ListTile(
                              leading: const Icon(Icons.verified_outlined),
                              title: const Text('SMS Proof'),
                              subtitle: const Text('Performances'),
                              trailing: const Text('En préparation',
                                  style: TextStyle(fontSize: 11)),
                            ),
                          ),
                          Card(
                            child: ListTile(
                              leading: const Icon(Icons.handshake_outlined),
                              title: const Text('SMS Connect'),
                              subtitle: const Text('Mes opportunités'),
                              trailing: const Icon(Icons.chevron_right),
                              onTap: () => onNavigate != null
                                  ? onNavigate!(4)
                                  : Navigator.of(context).push(
                                      MaterialPageRoute<void>(
                                        builder: (_) => const MyOpportunitiesScreen(),
                                      ),
                                    ),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 18),
                    Wrap(
                      spacing: 10,
                      children: [
                        OutlinedButton.icon(
                          icon: const Icon(Icons.handshake_outlined),
                          label: Text(
                              AppLocalizations.of(context).smsConnectTitle),
                          onPressed: () => Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => const MyOpportunitiesScreen(),
                            ),
                          ),
                        ),
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
                    const AdSlot(compact: true),
                    const SizedBox(height: 18),
                    Text('Sports',
                        style: Theme.of(context).textTheme.titleLarge),
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
                      leading: CircleAvatar(child: Icon(iconForSport(sport.slug))),
                      title: Text(sport.name),
                      subtitle: sport.description == null
                          ? null
                          : Text(sport.description!),
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
                              await ref
                                  .read(favoritesRepositoryProvider)
                                  .toggleSport(
                                    sport.id,
                                    favorite:
                                        !favoriteSports.contains(sport.id),
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
