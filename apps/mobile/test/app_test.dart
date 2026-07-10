import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:yelisport/features/auth/data/auth_repository.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/auth/presentation/sign_in_screen.dart';
import 'package:yelisport/features/profile/domain/user_profile.dart';
import 'package:yelisport/features/sports/domain/sport.dart';

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
  Future<void> signUp({
    required String email,
    required String password,
    required String displayName,
  }) async {}
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
}
