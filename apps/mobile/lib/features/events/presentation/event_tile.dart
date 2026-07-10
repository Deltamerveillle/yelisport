import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:yelisport/features/events/domain/sport_event.dart';

class EventTile extends StatelessWidget {
  const EventTile({
    required this.event,
    required this.actionLabel,
    required this.onAction,
    super.key,
  });

  final SportEvent event;
  final String actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final date = DateFormat('dd/MM/yyyy à HH:mm').format(event.startsAt.toLocal());
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(event.title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            Text('$date · ${event.location}'),
            Text('${event.capacity} places'),
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton.tonal(
                onPressed: onAction,
                child: Text(actionLabel),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
