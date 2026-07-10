import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:yelisport/features/profile/presentation/profile_providers.dart';

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _biography = TextEditingController();
  final _city = TextEditingController();
  final _country = TextEditingController();
  bool _initialized = false;
  bool _saving = false;

  @override
  void dispose() {
    _name.dispose();
    _biography.dispose();
    _city.dispose();
    _country.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await ref.read(profileRepositoryProvider).updateProfile(
            displayName: _name.text,
            biography: _biography.text,
            city: _city.text,
            country: _country.text,
          );
      ref.invalidate(profileProvider);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Profil enregistré.')),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Enregistrement impossible.')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _pickAvatar() async {
    final image = await ImagePicker().pickImage(
      source: ImageSource.gallery,
      maxWidth: 1024,
      imageQuality: 85,
    );
    if (image == null) return;
    final extension = image.name.split('.').last.toLowerCase();
    await ref.read(profileRepositoryProvider).uploadAvatar(
          await image.readAsBytes(),
          extension,
        );
    ref.invalidate(profileProvider);
  }

  @override
  Widget build(BuildContext context) {
    final profile = ref.watch(profileProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Mon profil')),
      body: profile.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: TextButton(
            onPressed: () => ref.invalidate(profileProvider),
            child: const Text('Réessayer'),
          ),
        ),
        data: (value) {
          if (!_initialized) {
            _name.text = value.displayName ?? '';
            _biography.text = value.biography ?? '';
            _city.text = value.city ?? '';
            _country.text = value.country ?? '';
            _initialized = true;
          }
          return SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Form(
              key: _formKey,
              child: Column(
                children: [
                  InkWell(
                    onTap: _pickAvatar,
                    borderRadius: BorderRadius.circular(60),
                    child: CircleAvatar(
                      radius: 52,
                      backgroundImage: value.avatarUrl == null
                          ? null
                          : NetworkImage(value.avatarUrl!),
                      child: value.avatarUrl == null
                          ? const Icon(Icons.add_a_photo, size: 34)
                          : null,
                    ),
                  ),
                  const SizedBox(height: 24),
                  TextFormField(
                    controller: _name,
                    decoration: const InputDecoration(labelText: 'Nom affiché'),
                    validator: (text) => (text?.trim().length ?? 0) >= 2
                        ? null
                        : '2 caractères minimum.',
                  ),
                  const SizedBox(height: 14),
                  TextFormField(
                    controller: _biography,
                    maxLines: 4,
                    maxLength: 500,
                    decoration: const InputDecoration(labelText: 'Biographie'),
                  ),
                  const SizedBox(height: 14),
                  TextFormField(
                    controller: _city,
                    decoration: const InputDecoration(labelText: 'Ville'),
                  ),
                  const SizedBox(height: 14),
                  TextFormField(
                    controller: _country,
                    decoration: const InputDecoration(labelText: 'Pays'),
                  ),
                  const SizedBox(height: 24),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: _saving ? null : _save,
                      child: Text(_saving ? 'Enregistrement…' : 'Enregistrer'),
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
