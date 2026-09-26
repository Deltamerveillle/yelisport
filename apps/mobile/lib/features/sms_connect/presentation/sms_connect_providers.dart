import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/app/di/providers.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/sms_connect/data/sms_connect_repository.dart';
import 'package:yelisport/features/sms_connect/domain/sms_connect_models.dart';

final smsConnectRepositoryProvider = Provider<SMSConnectRepository>(
  (ref) => SMSConnectRepository(ref.watch(apiClientProvider)),
);

final smsConnectInboxProvider =
    FutureProvider.autoDispose<List<SMSConnectInterest>>((ref) {
  ref.watch(authStateProvider);
  return ref.watch(smsConnectRepositoryProvider).inbox();
});

final smsConnectOpportunitiesProvider =
    FutureProvider.autoDispose<List<SMSConnectOpportunity>>((ref) {
  ref.watch(authStateProvider);
  return ref.watch(smsConnectRepositoryProvider).opportunities();
});

final smsConnectDecisionProvider = StateNotifierProvider.autoDispose
    .family<SMSConnectDecisionController, AsyncValue<void>, String>((ref, id) {
  ref.watch(authStateProvider);
  final repository = ref.watch(smsConnectRepositoryProvider);
  return SMSConnectDecisionController((decision) async {
    await repository.respond(id, decision);
  }, () {
    ref.invalidate(smsConnectInboxProvider);
    ref.invalidate(smsConnectOpportunitiesProvider);
  });
});

class SMSConnectDecisionController extends StateNotifier<AsyncValue<void>> {
  SMSConnectDecisionController(this._send, this._refresh)
      : super(const AsyncData(null));
  final Future<void> Function(AthleteDecision) _send;
  final void Function() _refresh;
  bool _disposed = false;

  Future<bool> respond(AthleteDecision decision) async {
    if (_disposed || state.isLoading) return false;
    state = const AsyncLoading();
    try {
      await _send(decision);
      if (_disposed) return false;
      state = const AsyncData(null);
      _refresh();
      return true;
    } catch (error, stack) {
      if (!_disposed) state = AsyncError(error, stack);
      return false;
    }
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
