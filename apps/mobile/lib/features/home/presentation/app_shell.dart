import 'package:flutter/material.dart';
import 'package:yelisport/features/home/presentation/home_screen.dart';
import 'package:yelisport/features/sms24/presentation/fixtures_screen.dart';
import 'package:yelisport/features/sms24/presentation/news_screen.dart';
import 'package:yelisport/features/sms_nations/presentation/sms_nations_screen.dart';
import 'package:yelisport/features/sms_connect/presentation/my_opportunities_screen.dart';
import 'package:yelisport/features/events/presentation/events_screen.dart';
import 'package:yelisport/features/profile/presentation/profile_screen.dart';
import 'package:yelisport/features/settings/presentation/settings_screen.dart';

/// Persistent destination navigation on desktop and on small screens.
class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _tab = 0;

  static const _labels = [
    'Accueil', 'Rencontres', 'Actualités', 'SMS Nations', 'Plus',
  ];

  static const _icons = [
    Icons.home_outlined,
    Icons.sports_soccer,
    Icons.newspaper_outlined,
    Icons.public,
    Icons.apps_outlined,
  ];

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 840;
    final pages = <Widget>[
      HomeScreen(onNavigate: (index) => setState(() => _tab = index)),
      const FixturesScreen(),
      const NewsScreen(),
      const SmsNationsScreen(),
      _MoreScreen(goTo: (index) => setState(() => _tab = index)),
    ];
    return Scaffold(
      body: Row(children: [
        if (wide) ...[
          NavigationRail(
            selectedIndex: _tab,
            onDestinationSelected: (value) => setState(() => _tab = value),
            extended: MediaQuery.sizeOf(context).width >= 1120,
            labelType: MediaQuery.sizeOf(context).width >= 1120
                ? NavigationRailLabelType.none
                : NavigationRailLabelType.all,
            leading: const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Tooltip(message: 'Succès Mondial Sports',
                child: Icon(Icons.emoji_events_outlined)),
            ),
            destinations: [
              for (var i = 0; i < _labels.length; i++)
                NavigationRailDestination(
                  icon: Icon(_icons[i]),
                  label: Text(_labels[i]),
                ),
            ],
          ),
          const VerticalDivider(width: 1),
        ],
        Expanded(
          child: IndexedStack(
            index: _tab,
            children: pages,
          ),
        ),
      ]),
      bottomNavigationBar: wide ? null : NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (value) => setState(() => _tab = value),
        destinations: [
          for (var i = 0; i < _labels.length; i++)
            NavigationDestination(
              icon: Icon(_icons[i]),
              label: _labels[i],
            ),
        ],
      ),
    );
  }
}

class _MoreScreen extends StatelessWidget {
  const _MoreScreen({required this.goTo});
  final ValueChanged<int> goTo;

  @override
  Widget build(BuildContext context) {
    final entries = [
      ('Rencontres & Live', Icons.sports_soccer, () => goTo(1)),
      ('Actualités', Icons.newspaper, () => goTo(2)),
      ('SMS Nations', Icons.public, () => goTo(3)),
      ('SMS Connect', Icons.handshake_outlined,
          () => _open(context, const MyOpportunitiesScreen())),
      ('Événements', Icons.event,
          () => _open(context, const EventsScreen())),
      ('Mon profil', Icons.person_outline,
          () => _open(context, const ProfileScreen())),
      ('Paramètres', Icons.settings_outlined,
          () => _open(context, const SettingsScreen())),
    ];
    return Scaffold(
      appBar: AppBar(title: const Text('Les espaces SMS24')),
      body: ListView(children: [
        for (final item in entries)
          ListTile(
            leading: Icon(item.$2),
            title: Text(item.$1),
            trailing: const Icon(Icons.chevron_right),
            onTap: item.$3,
          ),
        const Divider(),
        const ListTile(
          title: Text('SMS Talent • SMS Discover • SMS Passport • SMS Proof'),
          subtitle: Text('Parcours complémentaires en cours d’intégration'),
        ),
      ]),
    );
  }

  void _open(BuildContext context, Widget screen) {
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => screen));
  }
}
