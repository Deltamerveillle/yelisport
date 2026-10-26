import 'package:flutter/material.dart';
import 'package:yelisport/app/theme/app_colors.dart';

/// Shared branded header for sport and athlete screens.
class Sms24SportBanner extends StatelessWidget {
  const Sms24SportBanner({
    required this.title,
    required this.subtitle,
    required this.icon,
    this.eyebrow = 'SMS24 • SUCCÈS MONDIAL SPORTS',
    super.key,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final String eyebrow;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppColors.primary, AppColors.primaryLight],
        ),
        borderRadius: BorderRadius.circular(22),
      ),
      child: Wrap(
        spacing: 20,
        runSpacing: 16,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          Container(
            width: 78,
            height: 78,
            decoration: BoxDecoration(
              color: AppColors.secondary,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Icon(icon, size: 41, color: AppColors.primary),
          ),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 600),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(eyebrow, style: const TextStyle(
                  color: AppColors.secondary, fontSize: 11,
                  fontWeight: FontWeight.w800, letterSpacing: 1,
                )),
                const SizedBox(height: 8),
                Text(title, style: const TextStyle(
                  color: Colors.white, fontSize: 27,
                  fontWeight: FontWeight.w800,
                )),
                const SizedBox(height: 8),
                Text(subtitle, style: const TextStyle(
                  color: Color(0xFFDCE5F1), fontSize: 14,
                  height: 1.4,
                )),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
