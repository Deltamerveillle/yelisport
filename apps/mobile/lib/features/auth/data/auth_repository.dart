import 'package:supabase_flutter/supabase_flutter.dart';

abstract interface class AuthGateway {
  Session? get currentSession;
  Stream<AuthState> get authChanges;

  Future<void> signUp({
    required String email,
    required String password,
    required String displayName,
  });

  Future<void> signIn({required String email, required String password});
  Future<void> signOut();
}

class AuthRepository implements AuthGateway {
  const AuthRepository(this._client);

  final SupabaseClient _client;

  @override
  Session? get currentSession => _client.auth.currentSession;
  @override
  Stream<AuthState> get authChanges => _client.auth.onAuthStateChange;

  @override
  Future<void> signUp({
    required String email,
    required String password,
    required String displayName,
  }) async {
    await _client.auth.signUp(
      email: email.trim(),
      password: password,
      data: {'display_name': displayName.trim()},
    );
  }

  @override
  Future<void> signIn({required String email, required String password}) async {
    await _client.auth.signInWithPassword(
      email: email.trim(),
      password: password,
    );
  }

  @override
  Future<void> signOut() => _client.auth.signOut();
}
