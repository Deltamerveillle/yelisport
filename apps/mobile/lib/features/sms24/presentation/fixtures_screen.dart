import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:yelisport/app/di/providers.dart';

final fixtureStatusProvider = StateProvider.autoDispose<String>((ref) => 'all');

final fixturesProvider = FutureProvider.autoDispose.family<List<dynamic>, String>(
  (ref, status) => ref.watch(apiClientProvider).getList(
    '/sms24/fixtures',
    queryParameters: {
      'limit': 50,
      if (status != 'all') 'status': status,
    },
  ),
);

class FixturesScreen extends ConsumerWidget {
  const FixturesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = ref.watch(fixtureStatusProvider);
    final fixtures = ref.watch(fixturesProvider(status));
    return Scaffold(
      appBar: AppBar(
        title: const Text('Rencontres & Live'),
        actions: [
          IconButton(
            tooltip: 'Actualiser les rencontres',
            onPressed: () => ref.invalidate(fixturesProvider(status)),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: Column(
        children: [
          SingleChildScrollView(
            padding: const EdgeInsets.all(12),
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                for (final item in const [
                  ('all', 'Toutes'),
                  ('live', 'En direct'),
                  ('scheduled', 'À venir'),
                  ('finished', 'Résultats'),
                ])
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(item.$2),
                      selected: status == item.$1,
                      onSelected: (_) =>
                          ref.read(fixtureStatusProvider.notifier).state = item.$1,
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: fixtures.when(
              loading: () =>
                  const Center(child: CircularProgressIndicator()),
              error: (_, __) => Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text('Impossible de charger les rencontres.'),
                    TextButton(
                      onPressed: () => ref.invalidate(fixturesProvider(status)),
                      child: const Text('Réessayer'),
                    ),
                  ],
                ),
              ),
              data: (items) => RefreshIndicator(
                onRefresh: () async {
                  final updatedFixtures = ref.refresh(fixturesProvider(status).future);
                  await updatedFixtures;
                },
                child: items.isEmpty
                    ? ListView(
                        children: const [
                          SizedBox(height: 110),
                          Center(child: Text(
                            'Aucune rencontre disponible pour ce filtre.\n'
                            'Les données s’afficheront après leur collecte.',
                            textAlign: TextAlign.center,
                          )),
                        ],
                      )
                    : ListView.builder(
                        itemCount: items.length,
                        itemBuilder: (context, index) {
                          final fixture = Map<String, dynamic>.from(
                            items[index] as Map,
                          );
                          return _FixtureCard(fixture: fixture);
                        },
                      ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _FixtureCard extends StatelessWidget {
  const _FixtureCard({required this.fixture});

  final Map<String, dynamic> fixture;

  @override
  Widget build(BuildContext context) {
    final participants = (fixture['participants'] as List?) ?? const [];
    final names = participants.map((value) {
      final item = value as Map;
      final name = item['name']?.toString() ?? 'Participant';
      final score = item['score'];
      String? points;
      if (score is Map) {
        final value = score['total'] ?? score['current'] ?? score['score'];
        if (value is num || value is String) points = value.toString();
      }
      return points == null ? name : '$name ($points)';
    }).toList();
    final date = DateTime.tryParse(fixture['starts_at']?.toString() ?? '');
    final status = fixture['status']?.toString() ?? 'unknown';
    final clock = fixture['live_clock']?.toString();
    final source = fixture['source_name']?.toString() ?? 'Source non renseignée';

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              fixture['competition_name']?.toString() ??
                  fixture['sport_name']?.toString() ?? 'Sport',
              style: Theme.of(context).textTheme.labelLarge,
            ),
            const SizedBox(height: 9),
            Text(
              names.isNotEmpty
                  ? names.join('  •  ')
                  : (fixture['name']?.toString() ?? 'Rencontre'),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 9),
            Wrap(spacing: 12, runSpacing: 6, children: [
              Text(_statusLabel(status, clock)),
              if (date != null) Text(DateFormat('dd/MM/yyyy HH:mm').format(date.toLocal())),
              Text('Source : $source'),
            ]),
          ],
        ),
      ),
    );
  }

  String _statusLabel(String status, String? clock) {
    switch (status) {
      case 'live':
        return 'EN DIRECT ${clock ?? ''}';
      case 'scheduled':
        return 'À venir';
      case 'finished':
        return 'Terminé';
      case 'postponed':
        return 'Reporté';
      case 'cancelled':
        return 'Annulé';
      default:
        return status;
    }
  }
}
