import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/app/router/app_router.dart';
import 'package:yelisport/app/theme/app_theme.dart';
import 'package:yelisport/features/settings/presentation/settings_providers.dart';

class YeliSportApp extends ConsumerWidget {
  const YeliSportApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final darkMode = ref.watch(settingsProvider).valueOrNull?.darkMode ?? false;
    return MaterialApp.router(
      title: 'YeliSport',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: ThemeData.dark(useMaterial3: true),
      themeMode: darkMode ? ThemeMode.dark : ThemeMode.light,
      routerConfig: appRouter,
    );
  }
}
