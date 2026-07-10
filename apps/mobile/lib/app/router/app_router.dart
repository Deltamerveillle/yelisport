import 'package:go_router/go_router.dart';
import 'package:yelisport/features/auth/presentation/auth_gate.dart';

final appRouter = GoRouter(
  routes: [
    GoRoute(
      path: '/',
      builder: (context, state) => const AuthGate(),
    ),
  ],
);
