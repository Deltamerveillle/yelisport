import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/features/sms_nations/domain/sms_nation_athlete.dart';
import 'package:yelisport/features/sms_nations/presentation/sms_nations_providers.dart';

class SmsNationsScreen extends ConsumerWidget {
  const SmsNationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final athletes = ref.watch(smsNationsAthletesProvider);
    final availableOnly = ref.watch(smsNationsAvailableOnlyProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('SMS Nations')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Découvrez les talents sportifs',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                const Text('Aucun talent africain ne doit rester invisible.'),
                const SizedBox(height: 16),
                TextField(
                  decoration: const InputDecoration(
                    prefixIcon: Icon(Icons.search),
                    hintText: 'Rechercher un athlète',
                    border: OutlineInputBorder(),
                  ),
                  onChanged: (value) {
                    ref.read(smsNationsSearchProvider.notifier).state = value;
                  },
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Disponibles pour des opportunités'),
                  value: availableOnly,
                  onChanged: (value) {
                    ref.read(smsNationsAvailableOnlyProvider.notifier).state =
                        value;
                  },
                ),
              ],
            ),
          ),
          Expanded(
            child: athletes.when(
              loading: () => const Center(
                child: CircularProgressIndicator(),
              ),
              error: (error, stackTrace) => Center(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text('Impossible de charger les athlètes.'),
                      const SizedBox(height: 12),
                      FilledButton(
                        onPressed: () {
                          ref.invalidate(smsNationsAthletesProvider);
                        },
                        child: const Text('Réessayer'),
                      ),
                    ],
                  ),
                ),
              ),
              data: (result) {
                if (result.items.isEmpty) {
                  return const Center(
                    child: Text('Aucun athlète trouvé.'),
                  );
                }

                return ListView.builder(
                  itemCount: result.items.length,
                  itemBuilder: (context, index) {
                    final athlete = result.items[index];
                    return _AthleteCard(athlete: athlete);
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _AthleteCard extends StatelessWidget {
  const _AthleteCard({required this.athlete});

  final SmsNationAthlete athlete;

  @override
  Widget build(BuildContext context) {
    final details = [
      athlete.sportName,
      athlete.discipline,
      athlete.residenceCountryName,
      athlete.city,
    ].whereType<String>().where((value) => value.isNotEmpty).join(' • ');

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: ListTile(
        leading: CircleAvatar(
          child: Text(
            athlete.firstName.isNotEmpty
                ? athlete.firstName.substring(0, 1).toUpperCase()
                : '?',
          ),
        ),
        title: Text(athlete.fullName),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(details),
            if (athlete.clubName != null)
              Text('Club : \${athlete.clubName}'),
            if (athlete.talentEvaluated)
              Text(
                athlete.talentScore == null
                    ? 'Talent évalué'
                    : 'Évaluation : \${athlete.talentScore!.toStringAsFixed(1)}/100',
              ),
            if (athlete.availableForOpportunities == true)
              const Text('Disponible pour des opportunités'),
          ],
        ),
        isThreeLine: true,
      ),
    );
  }
}
