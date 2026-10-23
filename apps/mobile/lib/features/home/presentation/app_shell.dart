import 'package:flutter/material.dart';
import 'package:yelisport/features/home/presentation/home_screen.dart';
import 'package:yelisport/features/sms24/presentation/fixtures_screen.dart';
import 'package:yelisport/features/sms24/presentation/news_screen.dart';
import 'package:yelisport/features/sms_nations/presentation/sms_nations_screen.dart';
import 'package:yelisport/features/sms_connect/presentation/my_opportunities_screen.dart';
import 'package:yelisport/features/events/presentation/events_screen.dart';
import 'package:yelisport/features/profile/presentation/profile_screen.dart';
import 'package:yelisport/features/settings/presentation/settings_screen.dart';

/// Persistent destination navigation on desktop and smaller screens.
/// Core destinations are switched in-place, never pushed on a back stack.
class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _tab = 0;

  static const _names = <String>[
    'Accueil', 'Rencontres', 'Actualités', 'SMS Nations',
    'SMS Connect', 'Événements', 'Mon profil', 'Paramètres',
  ];

  static const _icons = <IconData>[
    Icons.home_outlined, Icons.sports_soccer, Icons.newspaper_outlined,
    Icons.public, Icons.handshake_outlined, Icons.event_outlined,
    Icons.person_outline, Icons.settings_outlined,
  ];

  void _select(int index) => setState(() => _tab = index);

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final wide = width >= 840;
    final tabs = <Widget>[
      HomeScreen(onNavigate: _select),
      const FixturesScreen(),
      const NewsScreen(),
      const SmsNationsScreen(),
      const MyOpportunitiesScreen(),
      const EventsScreen(),
      const ProfileScreen(),
      const SettingsScreen(),
      _MoreScreen(onSelect: _select),
    ];

    return Scaffold(
      body: Row(children: [
        if (wide) ...[
          NavigationRail(
            selectedIndex: _tab == 8 ? 0 : _tab,
            onDestinationSelected: _select,
            extended: width >= 1120,
            labelType: width >= 1120
                ? NavigationRailLabelType.none
                : NavigationRailLabelType.all,
            leading: const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Tooltip(
                message: 'Succès Mondial Sports',
                child: Icon(Icons.emoji_events_outlined),
              ),
            ),
            destinations: [
              for (var i = 0; i < _names.length; i++)
                NavigationRailDestination(
                  icon: Icon(_icons[i]),
                  label: Text(_names[i]),
                ),
            ],
          ),
          const VerticalDivider(width: 1),
        ],
        Expanded(child: IndexedStack(index: _tab, children: tabs)),
      ]),
      bottomNavigationBar: wide ? null : NavigationBar(
        selectedIndex: _tab < 4 ? _tab : 4,
        onDestinationSelected: (value) => _select(value == 4 ? 8 : value),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), label: 'Accueil'),
          NavigationDestination(icon: Icon(Icons.sports_soccer), label: 'Live'),
          NavigationDestination(icon: Icon(Icons.newspaper_outlined), label: 'News'),
          NavigationDestination(icon: Icon(Icons.public), label: 'Nations'),
          NavigationDestination(icon: Icon(Icons.apps_outlined), label: 'Plus'),
        ],
      ),
    );
  }
}

class _MoreScreen extends StatelessWidget {
  const _MoreScreen({required this.onSelect});

  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Les espaces SMS24')),
      body: ListView(children: [
        for (var i = 4; i < _AppShellState._names.length; i++)
          ListTile(
            leading: Icon(_AppShellState._icons[i]),
            title: Text(_AppShellState._names[i]),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => onSelect(i),
          ),
        const Divider(),
        const ListTile(
          title: Text('SMS Talent • SMS Discover • SMS Passport • SMS Proof'),
          subtitle: Text('Parcours complémentaires en cours d’intégration'),
        ),
      ]),
    );
  }
}
