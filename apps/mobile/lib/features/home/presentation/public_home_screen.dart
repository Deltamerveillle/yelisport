import 'package:flutter/material.dart';
import 'package:yelisport/app/theme/app_colors.dart';
import 'package:yelisport/features/ads/presentation/ad_slot.dart';
import 'package:yelisport/features/auth/presentation/sign_in_screen.dart';
import 'package:yelisport/features/auth/presentation/sign_up_screen.dart';
import 'package:yelisport/features/home/presentation/sms_space_screen.dart';

/// Public showcase, available before creating an account. No fabricated
/// athlete, match, partner, price or advertising campaign is displayed here.
class PublicHomeScreen extends StatelessWidget {
  const PublicHomeScreen({required this.onNavigate, super.key});

  final ValueChanged<int> onNavigate;

  void _open(BuildContext context, Widget page) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => page),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('SMS24 • SUCCÈS MONDIAL SPORTS'),
        actions: [
          TextButton(
            onPressed: () => _open(context, const SignInScreen()),
            child: const Text('Connexion'),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(18),
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: AppColors.primary,
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('SUCCÈS MONDIAL SPORTS',
                    style: TextStyle(color: AppColors.secondary,
                        fontWeight: FontWeight.bold, letterSpacing: 1.2)),
                SizedBox(height: 12),
                Text('Aucun talent africain ne doit rester invisible.',
                    style: TextStyle(color: Colors.white,
                        fontSize: 23, fontWeight: FontWeight.bold)),
                SizedBox(height: 12),
                Text('Découvrez les sports, les talents et les possibilités '
                    'de visibilité avant de créer votre compte.',
                    style: TextStyle(color: Colors.white)),
              ],
            ),
          ),
          const SizedBox(height: 18),
          const AdSlot(),
          const SizedBox(height: 20),
          Text('Explorer SMS24',
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 8, children: [
            FilledButton.icon(
              onPressed: () => onNavigate(15),
              icon: const Icon(Icons.sports),
              label: const Text('Tous les sports'),
            ),
            OutlinedButton.icon(
              onPressed: () => onNavigate(1),
              icon: const Icon(Icons.scoreboard_outlined),
              label: const Text('Rencontres'),
            ),
            OutlinedButton.icon(
              onPressed: () => onNavigate(2),
              icon: const Icon(Icons.article_outlined),
              label: const Text('Actualités'),
            ),
          ]),
          const SizedBox(height: 18),
          Text('Les espaces SMS24',
              style: Theme.of(context).textTheme.titleLarge),
          for (var i = 0; i < SmsSpace.values.length; i++)
            Card(
              child: ListTile(
                leading: const Icon(Icons.explore_outlined),
                title: Text(SmsSpace.values[i].title),
                subtitle: Text(SmsSpace.values[i].introduction),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => onNavigate(9 + i),
              ),
            ),
          const SizedBox(height: 16),
          Text('Faire connaître un athlète',
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          const Text(
            '1. Choisir son sport. 2. Créer un compte et choisir un abonnement '
            'actif. 3. Compléter son passeport sportif. 4. Déposer des médias '
            'privés. 5. Après modération, présenter son talent selon les '
            'prestations souscrites. Les trois évaluations humaines déterminent '
            'uniquement l’éligibilité au suivi qualifiant.',
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: () => _open(context, const SignUpScreen()),
            icon: const Icon(Icons.person_add_alt_1),
            label: const Text('Créer mon compte'),
          ),
          OutlinedButton.icon(
            onPressed: () => onNavigate(13),
            icon: const Icon(Icons.badge_outlined),
            label: const Text('Découvrir SMS Passport'),
          ),
          const SizedBox(height: 22),
          const AdSlot(compact: true),
          const SizedBox(height: 12),
          const Text(
            'Les emplacements publicitaires sont des espaces de présentation : '
            'aucun annonceur fictif ni campagne active n’est revendiqué.',
          ),
        ],
      ),
    );
  }
}
