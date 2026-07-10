import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/settings/domain/user_settings.dart';
import 'package:yelisport/features/settings/presentation/settings_providers.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  Future<void> _update(WidgetRef ref, UserSettings settings) async {
    await ref.read(settingsRepositoryProvider).update(settings);
    ref.invalidate(settingsProvider);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(settingsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Paramètres')),
      body: settings.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: TextButton(
            onPressed: () => ref.invalidate(settingsProvider),
            child: const Text('Réessayer'),
          ),
        ),
        data: (value) => ListView(
          children: [
            SwitchListTile(
              title: const Text('Mode sombre'),
              value: value.darkMode,
              onChanged: (enabled) => _update(
                ref,
                UserSettings(
                  language: value.language,
                  darkMode: enabled,
                  notificationsEnabled: value.notificationsEnabled,
                ),
              ),
            ),
            SwitchListTile(
              title: const Text('Notifications'),
              value: value.notificationsEnabled,
              onChanged: (enabled) => _update(
                ref,
                UserSettings(
                  language: value.language,
                  darkMode: value.darkMode,
                  notificationsEnabled: enabled,
                ),
              ),
            ),
            ListTile(
              title: const Text('Langue'),
              trailing: DropdownButton<String>(
                value: value.language,
                items: const [
                  DropdownMenuItem(value: 'fr', child: Text('Français')),
                  DropdownMenuItem(value: 'en', child: Text('English')),
                ],
                onChanged: (language) {
                  if (language == null) return;
                  _update(
                    ref,
                    UserSettings(
                      language: language,
                      darkMode: value.darkMode,
                      notificationsEnabled: value.notificationsEnabled,
                    ),
                  );
                },
              ),
            ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.logout),
              title: const Text('Se déconnecter'),
              textColor: Theme.of(context).colorScheme.error,
              iconColor: Theme.of(context).colorScheme.error,
              onTap: () async {
                await ref.read(authRepositoryProvider).signOut();
                if (context.mounted) Navigator.of(context).popUntil((route) => route.isFirst);
              },
            ),
          ],
        ),
      ),
    );
  }
}
