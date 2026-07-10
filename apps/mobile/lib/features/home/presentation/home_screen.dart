import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/sports/presentation/sports_providers.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sports = ref.watch(sportsProvider);
    final user = ref.watch(authRepositoryProvider).currentSession?.user;
    return Scaffold(
      appBar: AppBar(
        title: const Text('YeliSport'),
        actions: [
          IconButton(
            tooltip: 'Se déconnecter',
            onPressed: () => ref.read(authRepositoryProvider).signOut(),
            icon: const Icon(Icons.logout),
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
                    Text('Bienvenue', style: Theme.of(context).textTheme.headlineMedium),
                    if (user?.email != null) Text(user!.email!),
                    const SizedBox(height: 24),
                    Text('Sports', style: Theme.of(context).textTheme.titleLarge),
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
              data: (items) => SliverList.separated(
                itemCount: items.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (context, index) {
                  final sport = items[index];
                  return ListTile(
                    leading: const CircleAvatar(child: Icon(Icons.sports_soccer)),
                    title: Text(sport.name),
                    subtitle: sport.description == null ? null : Text(sport.description!),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
