import 'package:flutter/material.dart';
import 'package:yelisport/app/theme/app_colors.dart';

abstract final class AppTheme {
  static ThemeData get light {
    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.primary,
      primary: AppColors.primary,
      onPrimary: Colors.white,
      secondary: AppColors.secondary,
      onSecondary: AppColors.primary,
      tertiary: AppColors.success,
      surface: AppColors.surface,
      error: AppColors.error,
    );
    return ThemeData(
      colorScheme: scheme,
      useMaterial3: true,
      scaffoldBackgroundColor: scheme.surface,
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        centerTitle: false,
        elevation: 0,
        titleTextStyle: TextStyle(
          fontSize: 18, fontWeight: FontWeight.w700,
          color: Colors.white, letterSpacing: 0.2,
        ),
      ),
      cardTheme: CardThemeData(
        color: AppColors.paper,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: const BorderSide(color: Color(0xFFE2E7EF)),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.secondary,
          foregroundColor: AppColors.primary,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.paper,
        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
      ),
      navigationRailTheme: const NavigationRailThemeData(
        backgroundColor: AppColors.primary,
        selectedIconTheme: IconThemeData(color: AppColors.secondary),
        unselectedIconTheme: IconThemeData(color: Color(0xFFBAC4D3)),
        selectedLabelTextStyle: TextStyle(
          color: AppColors.secondary, fontWeight: FontWeight.w700,
        ),
        unselectedLabelTextStyle: TextStyle(color: Color(0xFFBAC4D3)),
        indicatorColor: AppColors.primaryLight,
      ),
      navigationBarTheme: const NavigationBarThemeData(
        backgroundColor: AppColors.paper,
        indicatorColor: Color(0xFFFFEBC4),
      ),
    );
  }
}
