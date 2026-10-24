import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';
import 'package:yelisport/app/di/providers.dart';
import 'package:yelisport/features/ads/presentation/ad_slot.dart';
import 'package:yelisport/features/sms24/presentation/fixtures_screen.dart';
import 'package:yelisport/features/sms24/presentation/news_screen.dart';
import 'package:yelisport/features/sms_nations/presentation/sms_nations_screen.dart';
import 'package:yelisport/features/sports/presentation/sport_detail_screen.dart';
import 'package:yelisport/features/sports/presentation/sports_providers.dart';

/// Real, navigable entry points. A page never represents an unavailable
/// evaluation or commercial service as having been completed.
enum SmsSpace { tripleVision, intelligence, talent, discover, passport, proof }

extension SmsSpaceContent on SmsSpace {
  String get title => switch (this) {
    SmsSpace.tripleVision => 'SMS Triple Vision',
    SmsSpace.intelligence => 'SMS Intelligence',
    SmsSpace.talent => 'SMS Talent',
    SmsSpace.discover => 'SMS Discover',
    SmsSpace.passport => 'SMS Passport',
    SmsSpace.proof => 'SMS Proof',
  };

  String get introduction => switch (this) {
    SmsSpace.tripleVision =>
      'Comprendre le regard croisé des analyses numériques et des entraîneurs.',
    SmsSpace.intelligence =>
      'Explorer les informations sportives publiées et leurs sources.',
    SmsSpace.talent =>
      'Comprendre les étapes de la détection et de l’évaluation des athlètes.',
    SmsSpace.discover =>
      'Découvrir les vidéos sportives autorisées à la publication.',
    SmsSpace.passport =>
      'Choisir son sport et accéder à son dossier sportif personnel.',
    SmsSpace.proof =>
      'Comprendre la vérification et la traçabilité des performances.',
  };

  List<String> get details => switch (this) {
    SmsSpace.tripleVision => [
      'Trois analyses IA sont consultatives : elles ne décident jamais seules.',
      'Trois évaluateurs humains rendent chacun une note indépendante.',
      'Le suivi qualifiant exige que chaque note humaine dépasse 50/100.',
      'Cette page explique la méthode ; elle ne simule aucune évaluation.',
    ],
    SmsSpace.intelligence => [
      'Consultez les rencontres, résultats et actualités effectivement collectés.',
      'Les données ne sont affichées que lorsqu’une source est disponible.',
      'Une donnée absente n’est jamais remplacée par un résultat inventé.',
    ],
    SmsSpace.talent => [
      'L’athlète présente son sport, son parcours et ses justificatifs.',
      'Trois entraîneurs vérifiés évaluent son dossier séparément.',
      'Une recommandation officielle exige trois notes strictement supérieures à 50/100.',
      'Un athlète non qualifié conserve sa visibilité liée à son abonnement.',
    ],
    SmsSpace.discover => [
      'Les vidéos sont soumises à modération avant leur diffusion publique.',
      'Les vidéos non approuvées restent invisibles aux visiteurs.',
      'Aucun profil fictif ni vidéo de démonstration n’est présenté comme réel.',
    ],
    SmsSpace.passport => [
      'Sélectionnez votre discipline dans la liste des sports.',
      'Vérifiez votre abonnement et renseignez votre passeport.',
      'Vous pourrez ensuite déposer une photo ou une courte vidéo privée.',
      'Un dépôt ne signifie jamais une publication automatique.',
    ],
    SmsSpace.proof => [
      'La preuve sportive associe un résultat à des éléments vérifiables.',
      'La vérification et la décision humaine doivent rester distinguées.',
      'Aucune performance non contrôlée ne reçoit le statut « vérifiée ».',
    ],
  };
}

void _openScreen(BuildContext context, Widget page) {
  Navigator.of(context).push(
    MaterialPageRoute<void>(builder: (_) => page),
  );
}

class SmsSpaceScreen extends StatelessWidget {
  const SmsSpaceScreen({required this.space, super.key});

  final SmsSpace space;

  @override
  Widget build(BuildContext context) {
    final showSportChoice = space == SmsSpace.talent ||
        space == SmsSpace.passport || space == SmsSpace.proof;
    return Scaffold(
      appBar: AppBar(title: Text(space.title)),
      body: ListView(
        padding: const EdgeInsets.all(18),
        children: [
          Text(space.title, style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 8),
          Text(space.introduction,
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 20),
          for (final detail in space.details)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(15),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.check_circle_outline, size: 22),
                    const SizedBox(width: 12),
                    Expanded(child: Text(detail)),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 18),
          if (showSportChoice)
            FilledButton.icon(
              onPressed: () => _openScreen(
                  context, const SmsSportsDirectoryScreen()),
              icon: const Icon(Icons.sports),
              label: const Text('Choisir mon sport'),
            ),
          if (space == SmsSpace.talent || space == SmsSpace.discover)
            OutlinedButton.icon(
              onPressed: () =>
                  _openScreen(context, const SmsNationsScreen()),
              icon: const Icon(Icons.public),
              label: const Text('Découvrir les athlètes'),
            ),
          if (space == SmsSpace.tripleVision ||
              space == SmsSpace.intelligence)
            FilledButton.icon(
              onPressed: () => _openScreen(context, const FixturesScreen()),
              icon: const Icon(Icons.scoreboard_outlined),
              label: const Text('Voir les rencontres et résultats'),
            ),
          if (space == SmsSpace.intelligence)
            OutlinedButton.icon(
              onPressed: () => _openScreen(context, const NewsScreen()),
              icon: const Icon(Icons.article_outlined),
              label: const Text('Consulter les actualités'),
            ),
          if (space == SmsSpace.discover) const _DiscoverFeed(),
          const SizedBox(height: 18),
          const AdSlot(compact: true),
          const SizedBox(height: 16),
          const Text(
            'SMS24 ne garantit ni recrutement, ni sélection, ni visibilité '
            'indépendamment des conditions de l’abonnement souscrit.',
          ),
        ],
      ),
    );
  }
}

/// Use the real sports catalogue; never invent a demo athlete.
class SmsSportsDirectoryScreen extends ConsumerWidget {
  const SmsSportsDirectoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sports = ref.watch(allSportsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Choisir mon sport')),
      body: sports.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('Catalogue des sports indisponible.'),
            TextButton(
              onPressed: () => ref.invalidate(allSportsProvider),
              child: const Text('Réessayer'),
            ),
          ]),
        ),
        data: (items) => items.isEmpty
            ? const Center(child: Text('Aucun sport disponible actuellement.'))
            : ListView.builder(
                itemCount: items.length,
                itemBuilder: (context, index) {
                  final sport = items[index];
                  return ListTile(
                    leading: Icon(iconForSport(sport.slug)),
                    title: Text(sport.name),
                    subtitle: const Text('Consulter et créer mon passeport'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () =>
                        _openScreen(context, SportDetailScreen(slug: sport.slug)),
                  );
                },
              ),
      ),
    );
  }
}

final smsDiscoverFeedProvider = FutureProvider.autoDispose<List<dynamic>>(
  (ref) => ref.watch(apiClientProvider).getList(
    '/discover', queryParameters: {'limit': 30},
  ),
);

class _DiscoverFeed extends ConsumerWidget {
  const _DiscoverFeed();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final videos = ref.watch(smsDiscoverFeedProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Vidéos publiées',
            style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        videos.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (_, __) => Column(children: [
            const Text('Impossible de charger les vidéos validées.'),
            TextButton(
              onPressed: () => ref.invalidate(smsDiscoverFeedProvider),
              child: const Text('Réessayer'),
            ),
          ]),
          data: (items) {
            if (items.isEmpty) {
              return const Card(
                child: Padding(
                  padding: EdgeInsets.all(18),
                  child: Text('Aucune vidéo approuvée et publiée pour '
                      'le moment. Les dépôts privés ne sont pas montrés.'),
                ),
              );
            }
            return Column(children: [
              for (final raw in items)
                if (raw is Map)
                  _DiscoverItem(data: Map<String, dynamic>.from(raw)),
            ]);
          },
        ),
      ],
    );
  }
}

class _DiscoverItem extends StatelessWidget {
  const _DiscoverItem({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final url = data['video_url']?.toString() ?? '';
    final parsed = Uri.tryParse(url);
    final canPlay = parsed != null && parsed.scheme == 'https';
    final caption = data['caption']?.toString();
    return Card(
      child: ListTile(
        leading: const Icon(Icons.play_circle_outline),
        title: Text(caption != null && caption.trim().isNotEmpty
            ? caption : 'Vidéo sportive'),
        subtitle: Text('Durée : ' +
            (data['duration_seconds']?.toString() ?? '?') + ' secondes'),
        trailing: canPlay ? const Icon(Icons.chevron_right) : null,
        onTap: canPlay
            ? () => _openScreen(context,
                SmsDiscoverVideoScreen(url: parsed))
            : null,
      ),
    );
  }
}

/// Playback only for a moderated public URL from the Discover API.
class SmsDiscoverVideoScreen extends StatefulWidget {
  const SmsDiscoverVideoScreen({required this.url, super.key});

  final Uri url;

  @override
  State<SmsDiscoverVideoScreen> createState() => _SmsDiscoverVideoScreenState();
}

class _SmsDiscoverVideoScreenState extends State<SmsDiscoverVideoScreen> {
  late final VideoPlayerController controller;
  late final Future<void> ready;

  @override
  void initState() {
    super.initState();
    controller = VideoPlayerController.networkUrl(widget.url);
    ready = controller.initialize();
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Vidéo SMS Discover')),
      body: Center(
        child: FutureBuilder<void>(
          future: ready,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return const Text('Lecture momentanément indisponible.');
            }
            if (snapshot.connectionState != ConnectionState.done) {
              return const CircularProgressIndicator();
            }
            return Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                AspectRatio(
                  aspectRatio: controller.value.aspectRatio,
                  child: VideoPlayer(controller),
                ),
                const SizedBox(height: 12),
                IconButton.filled(
                  onPressed: () => setState(() {
                    if (controller.value.isPlaying) {
                      controller.pause();
                    } else {
                      controller.play();
                    }
                  }),
                  icon: Icon(controller.value.isPlaying
                      ? Icons.pause : Icons.play_arrow),
                  tooltip: controller.value.isPlaying ? 'Pause' : 'Lire',
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}
