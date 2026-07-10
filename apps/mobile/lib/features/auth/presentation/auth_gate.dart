import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/auth/presentation/sign_in_screen.dart';
import 'package:yelisport/features/home/presentation/home_screen.dart';

class AuthGate extends ConsumerWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repository = ref.watch(authRepositoryProvider);
    final authState = ref.watch(authStateProvider);
    final session = authState.valueOrNull?.session ?? repository.currentSession;
    if (session != null) {
      return const HomeScreen();
    }
    if (authState.isLoading && !authState.hasValue) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return const SignInScreen();
  }
}
