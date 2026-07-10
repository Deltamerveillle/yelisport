import 'package:flutter/material.dart';
import 'package:yelisport/app/router/app_router.dart';
import 'package:yelisport/app/theme/app_theme.dart';

class YeliSportApp extends StatelessWidget {
  const YeliSportApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'YeliSport',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      routerConfig: appRouter,
    );
  }
}
