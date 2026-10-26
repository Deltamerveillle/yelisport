import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/auth/presentation/sign_in_screen.dart';
import 'package:yelisport/features/home/presentation/public_home_screen.dart';
import 'package:yelisport/app/theme/app_colors.dart';
import 'package:yelisport/features/home/presentation/home_screen.dart';
import 'package:yelisport/features/home/presentation/sms_space_screen.dart';
import 'package:yelisport/features/sms24/presentation/fixtures_screen.dart';
import 'package:yelisport/features/sms24/presentation/news_screen.dart';
import 'package:yelisport/features/sms_nations/presentation/sms_nations_screen.dart';
import 'package:yelisport/features/sms_nations/presentation/public_sms_nations_screen.dart';
import 'package:yelisport/features/sms_connect/presentation/my_opportunities_screen.dart';
import 'package:yelisport/features/events/presentation/events_screen.dart';
import 'package:yelisport/features/profile/presentation/profile_screen.dart';
import 'package:yelisport/features/settings/presentation/settings_screen.dart';

/// Persistent destination navigation on desktop and smaller screens.
/// Core destinations are switched in-place, never pushed on a back stack.
class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  int _tab = 0;
  // Child routes stay inside the shell so the global navigation never disappears.
  final GlobalKey<NavigatorState> _contentKey = GlobalKey<NavigatorState>();
  final ValueNotifier<int> _activeTab = ValueNotifier<int>(0);

  @override
  void dispose() {
    _activeTab.dispose();
    super.dispose();
  }

  static const _names = <String>[
    'Accueil', 'Rencontres', 'Actualités', 'SMS Nations',
    'SMS Connect', 'Événements', 'Mon profil', 'Paramètres',
    'Espaces SMS24',
  ];

  static const _icons = <IconData>[
    Icons.home_outlined, Icons.sports_soccer, Icons.newspaper_outlined,
    Icons.public, Icons.handshake_outlined, Icons.event_outlined,
    Icons.person_outline, Icons.settings_outlined, Icons.apps_outlined,
  ];

  void _select(int index) {
    // Switching destination exits the current detail page automatically.
    _contentKey.currentState?.popUntil((route) => route.isFirst);
    _activeTab.value = index;
    setState(() => _tab = index);
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authStateProvider);
    final loggedIn = (auth.valueOrNull?.session ??
        ref.watch(authRepositoryProvider).currentSession) != null;
    final width = MediaQuery.sizeOf(context).width;
    final wide = width >= 840;
    final tabs = <Widget>[
      loggedIn ? HomeScreen(onNavigate: _select)
          : PublicHomeScreen(onNavigate: _select),
      const FixturesScreen(),
      const NewsScreen(),
      loggedIn ? const SmsNationsScreen()
          : const PublicSmsNationsScreen(),
      const MyOpportunitiesScreen(),
      loggedIn ? const EventsScreen() : const SignInScreen(),
      loggedIn ? const ProfileScreen() : const SignInScreen(),
      loggedIn ? const SettingsScreen() : const SignInScreen(),
      _MoreScreen(onSelect: _select),
      for (final space in SmsSpace.values)
        SmsSpaceScreen(space: space),
      const SmsSportsDirectoryScreen(),
    ];

    return Scaffold(
      body: Row(children: [
        if (wide) ...[
          NavigationRail(
            selectedIndex: _tab < _names.length ? _tab : 8,
            onDestinationSelected: _select,
            extended: width >= 1120,
            scrollable: true,
            minExtendedWidth: 235,
            labelType: width >= 1120
                ? NavigationRailLabelType.none
                : NavigationRailLabelType.all,
            leading: Padding(
              padding: const EdgeInsets.fromLTRB(12, 20, 12, 28),
              child: width >= 1120
                  ? const Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(children: [
                          Icon(Icons.public, color: AppColors.secondary,
                            size: 28),
                          SizedBox(width: 10),
                          Text('SMS24', style: TextStyle(
                            color: AppColors.secondary, fontSize: 23,
                            fontWeight: FontWeight.w800, letterSpacing: 1.2,
                          )),
                        ]),
                        SizedBox(height: 7),
                        Text('SUCCÈS MONDIAL SPORTS', style: TextStyle(
                          color: Colors.white, fontSize: 10,
                          fontWeight: FontWeight.w700, letterSpacing: 1.1,
                        )),
                        SizedBox(height: 4),
                        Text('LE MONDE VOIT VOTRE TALENT',
                          style: TextStyle(color: Color(0xFFB4C2D6),
                            fontSize: 9, letterSpacing: 0.7)),
                      ],
                    )
                  : const Tooltip(
                      message: 'SMS24 • Le monde voit votre talent',
                      child: Icon(Icons.public,
                        color: AppColors.secondary, size: 30),
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
          const VerticalDivider(width: 1, color: Color(0xFFDCE2E9)),
        ],
        Expanded(
          child: Navigator(
            key: _contentKey,
            onGenerateRoute: (_) => MaterialPageRoute<void>(
              builder: (_) => ValueListenableBuilder<int>(
                valueListenable: _activeTab,
                // Build only the active destination. IndexedStack eagerly
                // mounted every API-backed page and flooded the Render
                // backend during its cold start.
                builder: (context, active, _) => tabs[active],
              ),
            ),
          ),
        ),
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
        for (var i = 4; i < 8; i++)
          ListTile(
            leading: Icon(_AppShellState._icons[i]),
            title: Text(_AppShellState._names[i]),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => onSelect(i),
          ),
        const Divider(),
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 10, 16, 6),
          child: Text('DÉCOUVRIR LES ESPACES SMS24'),
        ),
        for (var i = 0; i < SmsSpace.values.length; i++)
          ListTile(
            leading: const Icon(Icons.explore_outlined),
            title: Text(SmsSpace.values[i].title),
            subtitle: Text(SmsSpace.values[i].introduction),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => onSelect(9 + i),
          ),
        const Divider(),
        ListTile(
          leading: const Icon(Icons.sports),
          title: const Text('Tous les sports'),
          subtitle: const Text('Choisir une discipline ou créer mon passeport'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => onSelect(15),
        ),
      ]),
    );
  }
}
