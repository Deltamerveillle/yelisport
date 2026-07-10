import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:yelisport/features/auth/data/auth_repository.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/auth/presentation/sign_in_screen.dart';
import 'package:yelisport/features/events/domain/sport_event.dart';
import 'package:yelisport/features/events/presentation/event_tile.dart';
import 'package:yelisport/features/profile/domain/user_profile.dart';
import 'package:yelisport/features/sports/domain/sport.dart';
import 'package:yelisport/features/settings/domain/user_settings.dart';

class FakeAuthGateway implements AuthGateway {
  @override
  Stream<AuthState> get authChanges => const Stream.empty();
  @override
  Session? get currentSession => null;
  @override
  Future<void> signIn({required String email, required String password}) async {}
  @override
  Future<void> signOut() async {}
  @override
  Future<bool> signUp({
    required String email,
    required String password,
    required String displayName,
  }) async => false;
}

void main() {
  testWidgets('renders and validates the sign-in screen', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [authRepositoryProvider.overrideWithValue(FakeAuthGateway())],
        child: const MaterialApp(home: SignInScreen()),
      ),
    );

    expect(find.text('Connexion'), findsOneWidget);
    expect(find.text('Créer un compte'), findsOneWidget);
    await tester.tap(find.text('Se connecter'));
    await tester.pump();
    expect(find.text('Saisissez un email valide.'), findsOneWidget);
    expect(find.text('8 caractères minimum.'), findsOneWidget);
  });

  test('parses a sport returned by the API', () {
    final sport = Sport.fromJson({
      'id': 'sport-id',
      'slug': 'football',
      'name': 'Football',
      'description': null,
      'icon_url': null,
    });
    expect(sport.slug, 'football');
    expect(sport.name, 'Football');
  });

  test('parses the profile automatically created by Supabase', () {
    final profile = UserProfile.fromJson({
      'user_id': 'user-id',
      'display_name': 'Awa',
      'locale': 'fr',
    });
    expect(profile.displayName, 'Awa');
    expect(profile.locale, 'fr');
  });

  test('parses an event returned by the API', () {
    final event = SportEvent.fromJson({
      'id': 'event-id',
      'sport_id': 'sport-id',
      'organizer_id': 'user-id',
      'title': 'Football du samedi',
      'description': 'Match amical',
      'location': 'Abidjan',
      'starts_at': '2026-07-12T10:00:00Z',
      'ends_at': '2026-07-12T12:00:00Z',
      'capacity': 20,
    });
    expect(event.title, 'Football du samedi');
    expect(event.capacity, 20);
  });

  testWidgets('event tile displays details and triggers its action', (tester) async {
    var tapped = false;
    final event = SportEvent(
      id: 'event-id',
      sportId: 'sport-id',
      organizerId: 'user-id',
      title: 'Basket du dimanche',
      location: 'Cocody',
      startsAt: DateTime.utc(2026, 7, 12, 10),
      endsAt: DateTime.utc(2026, 7, 12, 12),
      capacity: 12,
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: EventTile(
            event: event,
            actionLabel: "S'inscrire",
            onAction: () => tapped = true,
          ),
        ),
      ),
    );
    expect(find.text('Basket du dimanche'), findsOneWidget);
    expect(find.text('12 places'), findsOneWidget);
    await tester.tap(find.text("S'inscrire"));
    expect(tapped, isTrue);
  });

  test('parses user settings with safe defaults', () {
    final settings = UserSettings.fromJson({
      'language': 'fr',
      'dark_mode': true,
      'notifications_enabled': false,
    });
    expect(settings.darkMode, isTrue);
    expect(settings.notificationsEnabled, isFalse);
  });
}
