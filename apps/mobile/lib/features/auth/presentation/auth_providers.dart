import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:yelisport/app/di/providers.dart';
import 'package:yelisport/features/auth/data/auth_repository.dart';

final authRepositoryProvider = Provider<AuthGateway>(
  (ref) => AuthRepository(ref.watch(supabaseProvider)),
);

final authStateProvider = StreamProvider<AuthState>((ref) {
  return ref.watch(authRepositoryProvider).authChanges;
});
