import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:yelisport/app/theme/app_theme.dart';
import 'package:yelisport/core/localization/generated/app_localizations.dart';
import 'package:yelisport/core/network/api_client.dart';
import 'package:yelisport/features/auth/data/auth_repository.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/sms_connect/data/sms_connect_repository.dart';
import 'package:yelisport/features/sms_connect/domain/sms_connect_models.dart';
import 'package:yelisport/features/sms_connect/presentation/my_opportunities_screen.dart';
import 'package:yelisport/features/sms_connect/presentation/sms_connect_providers.dart';

Map<String, dynamic> interest(
        {String id = 'internal-interest', String response = 'pending'}) =>
    {
      'id': id,
      'athlete_id': 'private-athlete-id',
      'requester_user_id': 'private-requester-id',
      'email': 'private@example.com',
      'phone': 'private-phone',
      'whatsapp': 'private-whatsapp',
      'organization_name': 'Club SMS',
      'interest_type': 'trial',
      'subject': 'Invitation sportive',
      'message': 'Une proposition encadrée par SMS.',
      'status': 'delivered',
      'athlete_response': response,
      'athlete_responded_at': null,
      'created_at': '2026-09-26T10:00:00Z',
      'delivered_at': '2026-09-26T11:00:00Z',
    };

Map<String, dynamic> opportunity(String status,
        {String interestId = 'internal-interest'}) =>
    {
      ...interest(id: 'internal-opportunity-$status'),
      'interest_id': interestId,
      'status': status,
      'opened_at': '2026-09-26T12:00:00Z',
      'closed_at': ['active', 'progressing'].contains(status)
          ? null
          : '2026-09-27T12:00:00Z',
    };

class FakeApi implements ApiClient {
  List<Map<String, dynamic>> inbox = [interest()];
  List<Map<String, dynamic>> qualified = [];
  final paths = <String>[];
  final decisions = <String>[];
  Object? loadError;
  Object? patchError;
  Completer<void>? loadWait;
  Completer<void>? patchWait;

  @override
  Future<List<dynamic>> getList(String path,
      {Map<String, dynamic>? queryParameters}) async {
    paths.add(path);
    if (loadWait != null) await loadWait!.future;
    if (loadError != null) throw loadError!;
    return path.endsWith('/inbox') ? List.of(inbox) : List.of(qualified);
  }

  @override
  Future<Map<String, dynamic>> patchObject(String path,
      {Map<String, dynamic>? data}) async {
    paths.add(path);
    expect(data!.keys, ['athlete_response']);
    decisions.add(data['athlete_response'] as String);
    if (patchWait != null) await patchWait!.future;
    if (patchError != null) throw patchError!;
    inbox = [interest(response: decisions.last)];
    if (decisions.last == 'interested') qualified = [opportunity('active')];
    return inbox.single;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class FakeAuth implements AuthGateway {
  @override
  Session? currentSession = Session(
      accessToken: 'test',
      tokenType: 'bearer',
      user: User(
        id: 'private-user-id',
        appMetadata: {},
        userMetadata: {},
        aud: 'authenticated',
        createdAt: '2026-09-26T00:00:00Z',
      ));
  @override
  Stream<AuthState> get authChanges => const Stream.empty();
  @override
  Future<void> signIn(
      {required String email, required String password}) async {}
  @override
  Future<void> signOut() async {
    currentSession = null;
  }

  @override
  Future<bool> signUp(
          {required String email,
          required String password,
          required String displayName}) async =>
      false;
}

Future<void> showScreen(WidgetTester tester, FakeApi api,
    {String language = 'fr'}) async {
  tester.view.physicalSize = const Size(900, 1200);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(ProviderScope(
      overrides: [
        authRepositoryProvider.overrideWithValue(FakeAuth()),
        smsConnectRepositoryProvider
            .overrideWithValue(SMSConnectRepository(api)),
      ],
      child: MaterialApp(
        locale: Locale(language),
        theme: AppTheme.light,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const MyOpportunitiesScreen(),
      )));
}

void main() {
  test('models preserve statuses, dates and unknown nullable dates', () {
    final request = SMSConnectInterest.fromJson(interest());
    expect(request.needsResponse, true);
    expect(request.deliveredAt, DateTime.utc(2026, 9, 26, 11));
    expect(request.athleteRespondedAt, isNull);
    expect(
        SMSConnectInterest.fromJson(interest(response: 'declined'))
            .needsResponse,
        false);
    expect(
        SMSConnectInterest.fromJson({...interest(), 'status': 'approved'})
            .needsResponse,
        false);
    for (final status in OpportunityStatus.values) {
      final value = SMSConnectOpportunity.fromJson(opportunity(status.name));
      expect(value.isOngoing, ['active', 'progressing'].contains(status.name));
      expect(value.interestId, 'internal-interest');
    }
  });

  test('malformed required fields and unknown statuses fail closed', () {
    expect(() => SMSConnectInterest.fromJson({...interest(), 'id': 123}),
        throwsFormatException);
    expect(
        () => SMSConnectInterest.fromJson(
            {...interest(), 'athlete_response': 'yes'}),
        throwsArgumentError);
    expect(() => SMSConnectOpportunity.fromJson(opportunity('future-status')),
        throwsArgumentError);
    expect(
        () => SMSConnectOpportunity.fromJson(
            {...opportunity('active'), 'opened_at': 'bad'}),
        throwsFormatException);
  });

  test('repository uses real routes and only the decision payload', () async {
    final api = FakeApi();
    final repository = SMSConnectRepository(api);
    expect((await repository.inbox()).length, 1);
    expect(await repository.opportunities(), isEmpty);
    for (final decision in AthleteDecision.values) {
      final response = await repository.respond('internal-interest', decision);
      expect(response.athleteResponse.name, decision.name);
    }
    expect(api.paths, [
      '/sms-connect/athlete/inbox',
      '/sms-connect/athlete/opportunities',
      '/sms-connect/athlete/interests/internal-interest/response',
      '/sms-connect/athlete/interests/internal-interest/response',
    ]);
    expect(api.decisions, ['interested', 'declined']);
  });

  test('decision prevents concurrent duplicate requests', () async {
    final wait = Completer<void>();
    var calls = 0;
    var refreshes = 0;
    final controller = SMSConnectDecisionController((_) {
      calls++;
      return wait.future;
    }, () {
      refreshes++;
    });
    final first = controller.respond(AthleteDecision.interested);
    expect(controller.state.isLoading, true);
    expect(await controller.respond(AthleteDecision.declined), false);
    wait.complete();
    expect(await first, true);
    expect(calls, 1);
    expect(refreshes, 1);
    controller.dispose();
  });

  test('auth changes invalidate both read providers', () async {
    final auth = StreamController<AuthState>();
    final api = FakeApi();
    final container = ProviderContainer(overrides: [
      authStateProvider.overrideWith((ref) => auth.stream),
      smsConnectRepositoryProvider.overrideWithValue(SMSConnectRepository(api)),
    ]);
    final inboxSubscription =
        container.listen(smsConnectInboxProvider, (_, __) {});
    final opportunitiesSubscription =
        container.listen(smsConnectOpportunitiesProvider, (_, __) {});
    await container.read(smsConnectInboxProvider.future);
    await container.read(smsConnectOpportunitiesProvider.future);
    final count = api.paths.length;
    auth.add(AuthState(AuthChangeEvent.signedIn, FakeAuth().currentSession));
    await Future<void>.delayed(Duration.zero);
    await container.read(smsConnectInboxProvider.future);
    await container.read(smsConnectOpportunitiesProvider.future);
    expect(api.paths.length, greaterThan(count));
    inboxSubscription.close();
    opportunitiesSubscription.close();
    container.dispose();
    await auth.close();
  });

  testWidgets(
      'separates review ongoing completed and hides all internal fields',
      (tester) async {
    final api = FakeApi()
      ..qualified = OpportunityStatus.values
          .map((status) =>
              opportunity(status.name, interestId: 'converted-${status.name}'))
          .toList();
    await showScreen(tester, api);
    await tester.pumpAndSettle();
    expect(find.text('Je suis intéressé'), findsOneWidget);
    expect(find.text('Opportunité ouverte'), findsNothing);
    await tester.tap(find.text('En cours'));
    await tester.pumpAndSettle();
    expect(find.text('Opportunité ouverte'), findsOneWidget);
    expect(find.text('En progression'), findsOneWidget);
    expect(find.text('Retirée'), findsNothing);
    await tester.tap(find.text('Terminées'));
    await tester.pumpAndSettle();
    expect(find.text('Aboutie'), findsOneWidget);
    expect(find.text('Non aboutie'), findsOneWidget);
    expect(find.text('Retirée'), findsOneWidget);
    final text = tester
        .widgetList<Text>(find.byType(Text))
        .map((widget) => widget.data ?? '')
        .join(' ');
    for (final forbidden in [
      'internal-',
      'private-',
      'private@example.com',
      'requester_user_id',
      'whatsapp'
    ]) {
      expect(text.contains(forbidden), false);
    }
  });

  for (final decision in AthleteDecision.values) {
    testWidgets(
        '${decision.name} refreshes both lists without duplicate source cards',
        (tester) async {
      final api = FakeApi()..patchWait = Completer<void>();
      await showScreen(tester, api);
      await tester.pumpAndSettle();
      await tester.tap(find.text(decision == AthleteDecision.interested
          ? 'Je suis intéressé'
          : 'Décliner'));
      await tester.pump();
      expect(
          tester
              .widget<FilledButton>(
                  find.widgetWithText(FilledButton, 'Je suis intéressé'))
              .onPressed,
          isNull);
      expect(
          tester
              .widget<OutlinedButton>(
                  find.widgetWithText(OutlinedButton, 'Décliner'))
              .onPressed,
          isNull);
      api.patchWait!.complete();
      await tester.pumpAndSettle();
      expect(api.decisions, [decision.name]);
      expect(api.paths.where((path) => path.endsWith('/inbox')).length, 2);
      expect(
          api.paths.where((path) => path.endsWith('/opportunities')).length, 2);
      expect(find.text('Je suis intéressé'), findsNothing);
      await tester.tap(find.text('En cours'));
      await tester.pumpAndSettle();
      expect(
          find.text('Opportunité ouverte'),
          decision == AthleteDecision.interested
              ? findsOneWidget
              : findsNothing);
      if (decision == AthleteDecision.interested) {
        expect(find.text('Invitation sportive'), findsOneWidget);
      } else {
        expect(find.text('Aucune opportunité en cours.'), findsOneWidget);
        await tester.tap(find.text('À examiner'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Demandes traitées'));
        await tester.pumpAndSettle();
        expect(find.text('Demande déclinée'), findsOneWidget);
      }
    });
  }

  testWidgets('loading and safe load error then retry', (tester) async {
    final api = FakeApi()
      ..loadWait = Completer<void>()
      ..loadError = Exception('private-token');
    api.inbox.single['delivered_at'] = null;
    await showScreen(tester, api);
    await tester.pump();
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    api.loadWait!.complete();
    await tester.pumpAndSettle();
    expect(
        find.text('Impossible de charger vos opportunités.'), findsOneWidget);
    expect(find.textContaining('private-token'), findsNothing);
    api.loadError = null;
    await tester.tap(find.text('Réessayer'));
    await tester.pumpAndSettle();
    expect(find.text('Je suis intéressé'), findsOneWidget);
    expect(find.textContaining('Demande créée le'), findsOneWidget);
  });

  testWidgets('failed decision remains actionable with a safe message',
      (tester) async {
    final api = FakeApi()..patchError = Exception('private-token');
    await showScreen(tester, api);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Décliner'));
    await tester.pumpAndSettle();
    expect(find.text('Impossible de transmettre votre réponse. Réessayez.'),
        findsOneWidget);
    expect(find.textContaining('private-token'), findsNothing);
    expect(
        tester
            .widget<OutlinedButton>(
                find.widgetWithText(OutlinedButton, 'Décliner'))
            .onPressed,
        isNotNull);
  });

  testWidgets('empty states and English localization', (tester) async {
    final api = FakeApi()..inbox = [];
    await showScreen(tester, api, language: 'en');
    await tester.pumpAndSettle();
    expect(find.text('My opportunities'), findsOneWidget);
    expect(find.text('No requests to review.'), findsOneWidget);
    await tester.tap(find.text('Ongoing'));
    await tester.pumpAndSettle();
    expect(find.text('No ongoing opportunities.'), findsOneWidget);
    await tester.tap(find.text('Completed'));
    await tester.pumpAndSettle();
    expect(find.text('No completed opportunities.'), findsOneWidget);
  });
  testWidgets('signed-out users cannot read opportunities', (tester) async {
    final api = FakeApi();
    await tester.pumpWidget(ProviderScope(
        overrides: [
          authRepositoryProvider
              .overrideWithValue(FakeAuth()..currentSession = null),
          smsConnectRepositoryProvider
              .overrideWithValue(SMSConnectRepository(api)),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const MyOpportunitiesScreen(),
        )));
    await tester.pumpAndSettle();
    expect(find.text('Connexion'), findsOneWidget);
    expect(find.text('Invitation sportive'), findsNothing);
    expect(api.paths, isEmpty);
  });
}
