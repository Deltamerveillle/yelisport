import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

final appRouter = GoRouter(
  routes: [
    GoRoute(
      path: '/',
      builder: (context, state) => const _BootstrapScreen(),
    ),
  ],
);

class _BootstrapScreen extends StatelessWidget {
  const _BootstrapScreen();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('YeliSport')),
      body: const Center(
        child: Semantics(
          label: 'YeliSport prêt',
          child: Text('YeliSport'),
        ),
      ),
    );
  }
}
