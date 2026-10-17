import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/app/di/providers.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/sms_nations/data/sms_nations_repository.dart';
import 'package:yelisport/features/sms_nations/domain/sms_nation_athlete.dart';

final smsNationsRepositoryProvider = Provider<SmsNationsRepository>(
  (ref) => SmsNationsRepository(ref.watch(apiClientProvider)),
);

final smsNationsSearchProvider =
    StateProvider.autoDispose<String>((ref) => '');

final smsNationsAvailableOnlyProvider =
    StateProvider.autoDispose<bool>((ref) => false);

final smsNationsAthletesProvider =
    FutureProvider.autoDispose<SmsNationsSearchResult>((ref) {
  ref.watch(authStateProvider);

  final search = ref.watch(smsNationsSearchProvider).trim();
  final availableOnly = ref.watch(smsNationsAvailableOnlyProvider);

  if (search.length == 1) {
    return Future.value(
      const SmsNationsSearchResult(
        items: [],
        total: 0,
        limit: 24,
        offset: 0,
      ),
    );
  }

  return ref.watch(smsNationsRepositoryProvider).searchAthletes(
        search: search.isEmpty ? null : search,
        availableForOpportunities: availableOnly ? true : null,
      );
});
