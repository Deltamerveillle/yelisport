import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:yelisport/app/di/providers.dart';

final sms24NewsProvider = FutureProvider.autoDispose<List<dynamic>>(
  (ref) => ref.watch(apiClientProvider).getList('/sms24/news',
    queryParameters: {'limit': 30},
  ),
);

class NewsScreen extends ConsumerWidget {
  const NewsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final news = ref.watch(sms24NewsProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Actualités sportives'),
        actions: [
          IconButton(
            tooltip: 'Actualiser les actualités',
            onPressed: () => ref.invalidate(sms24NewsProvider),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: news.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => Center(child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Impossible de charger les actualités.'),
            TextButton(
              onPressed: () => ref.invalidate(sms24NewsProvider),
              child: const Text('Réessayer'),
            ),
          ],
        )),
        data: (items) => RefreshIndicator(
          onRefresh: () async { await ref.refresh(sms24NewsProvider.future); },
          child: items.isEmpty
              ? ListView(children: const [
                  SizedBox(height: 140),
                  Center(child: Text(
                    'Aucune actualité publiée pour le moment.\n'
                    'Seules les informations validées seront diffusées.',
                    textAlign: TextAlign.center,
                  )),
                ])
              : ListView.builder(
                  itemCount: items.length,
                  itemBuilder: (context, index) {
                    final article = Map<String, dynamic>.from(items[index] as Map);
                    final date = DateTime.tryParse(
                      article['published_at']?.toString() ?? '',
                    );
                    final url = article['source_url']?.toString();
                    return Card(
                      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      child: ListTile(
                        title: Text(article['title']?.toString() ?? ''),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (article['excerpt'] != null)
                              Text(article['excerpt'].toString(), maxLines: 3,
                                overflow: TextOverflow.ellipsis),
                            const SizedBox(height: 5),
                            Text([
                              article['publisher_name'] ?? article['source_name'] ?? 'Source',
                              if (date != null) DateFormat('dd/MM/yyyy HH:mm').format(date.toLocal()),
                            ].join(' • ')),
                          ],
                        ),
                        trailing: url != null ? IconButton(
                          tooltip: 'Copier le lien de la source',
                          icon: const Icon(Icons.copy),
                          onPressed: () async {
                            await Clipboard.setData(ClipboardData(text: url));
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Lien source copié.')),
                              );
                            }
                          },
                        ) : null,
                      ),
                    );
                  },
                ),
        ),
      ),
    );
  }
}
