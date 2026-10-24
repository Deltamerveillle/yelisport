import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/home/presentation/app_shell.dart';

class AuthGate extends ConsumerWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authStateProvider);
    if (authState.isLoading && !authState.hasValue) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return const AppShell();
  }
}
