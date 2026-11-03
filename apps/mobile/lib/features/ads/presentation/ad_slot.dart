import 'package:flutter/material.dart';

/// Reserved commercial inventory. This widget never claims a real advertiser.
class AdSlot extends StatelessWidget {
  const AdSlot({this.compact = false, super.key});
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Emplacement réservé aux communications publicitaires',
      child: Container(
        width: double.infinity,
        constraints: BoxConstraints(minHeight: compact ? 72 : 104),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('ESPACE PUBLICITAIRE',
                style: Theme.of(context).textTheme.labelSmall),
            const SizedBox(height: 6),
            const Text('Votre marque sur Succès Mondial Sports',
                textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}
