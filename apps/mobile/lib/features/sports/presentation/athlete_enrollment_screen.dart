import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:yelisport/app/di/providers.dart';
import 'package:yelisport/features/sports/domain/sport.dart';

/// Enrolment never treats a payment intention as proof of payment.
class AthleteEnrollmentScreen extends ConsumerStatefulWidget {
  const AthleteEnrollmentScreen({required this.sport, super.key});
  final Sport sport;

  @override
  ConsumerState<AthleteEnrollmentScreen> createState() => _AthleteEnrollmentState();
}

class _AthleteEnrollmentState extends ConsumerState<AthleteEnrollmentScreen> {
  final _formKey = GlobalKey<FormState>();
  final _firstName = TextEditingController();
  final _lastName = TextEditingController();
  final _city = TextEditingController();
  final _country = TextEditingController();
  final _speciality = TextEditingController();
  final _club = TextEditingController();
  final _summary = TextEditingController();
  bool _busy = false;
  String? _athleteId;
  String? _error;
  int? _refreshKey;

  @override
  void dispose() {
    for (final c in [
      _firstName, _lastName, _city, _country, _speciality, _club, _summary,
    ]) { c.dispose(); }
    super.dispose();
  }

  Future<Map<String, dynamic>> _access() =>
      ref.read(apiClientProvider).getObject('/subscriptions/me/access');

  void _reload() => setState(() => _refreshKey = (_refreshKey ?? 0) + 1);

  Future<void> _createAthlete() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() { _busy = true; _error = null; });
    try {
      final access = await _access();
      if (access['has_premium_access'] != true) {
        throw StateError('Abonnement actif requis pour continuer.');
      }
      final api = ref.read(apiClientProvider);
      final profile = await api.postObject('/athletes', data: {
        'sport_id': widget.sport.id,
        'first_name': _firstName.text.trim(),
        'last_name': _lastName.text.trim(),
        'city': _city.text.trim(),
        'country': _country.text.trim(),
      });
      final id = profile['id'].toString();
      await api.postObject('/athletes/$id/passport', data: {
        'discipline': _speciality.text.trim().isEmpty
            ? widget.sport.name : _speciality.text.trim(),
        'club_name': _club.text.trim(),
        'sporting_summary': _summary.text.trim(),
      });
      if (mounted) setState(() => _athleteId = id);
    } catch (_) {
      if (mounted) {
        setState(() => _error =
            'Le dossier ne peut pas être finalisé. Vérifie ton abonnement et '
            'l’existence éventuelle d’un profil pour ce sport.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _uploadPhoto() async {
    final athleteId = _athleteId;
    if (athleteId == null) return;
    final photo = await ImagePicker().pickImage(
      source: ImageSource.gallery, imageQuality: 85, maxWidth: 1600,
    );
    if (photo == null) return;
    setState(() { _busy = true; _error = null; });
    try {
      if ((await _access())['has_premium_access'] != true) {
        throw StateError('Abonnement inactif');
      }
      final lower = photo.name.toLowerCase();
      final extension = lower.endsWith('.png') ? 'png' :
          lower.endsWith('.webp') ? 'webp' : 'jpg';
      final mime = extension == 'png' ? 'image/png' :
          extension == 'webp' ? 'image/webp' : 'image/jpeg';
      final bytes = await photo.readAsBytes();
      if (bytes.lengthInBytes > 8 * 1024 * 1024) {
        throw StateError('Photo trop volumineuse (8 Mo maximum)');
      }
      final supabase = ref.read(supabaseProvider);
      final userId = supabase.auth.currentUser?.id;
      if (userId == null) throw StateError('Session expirée');
      final random = Random.secure();
      final hex = List.generate(16,
        (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
      final uuid = '${hex.substring(0,8)}-${hex.substring(8,12)}-4${hex.substring(13,16)}-a${hex.substring(17,20)}-${hex.substring(20,32)}';
      final path = '$userId/$athleteId/$uuid.$extension';
      await supabase.storage.from('sms24-athlete-media')
          .uploadBinary(path, bytes, fileOptions: FileOptions(contentType: mime));
      await ref.read(apiClientProvider).postObject(
        '/athletes/$athleteId/media',
        data: {'storage_path': path, 'media_type': 'photo', 'mime_type': mime},
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Photo déposée pour vérification. Non publiée.'),
        ));
      }
    } catch (_) {
      if (mounted) setState(() => _error =
          'Envoi impossible. Le stockage privé doit être configuré et '
          'ton abonnement actif. Aucun média n’a été publié.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Inscription • ${widget.sport.name}')),
      body: FutureBuilder<Map<String, dynamic>>(
        key: ValueKey(_refreshKey),
        future: _access(),
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            if (snapshot.hasError) {
              return Center(child: TextButton(
                onPressed: _reload, child: const Text('Réessayer'),
              ));
            }
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.data?['has_premium_access'] != true) {
            return _SubscriptionStep(onReload: _reload);
          }
          return Form(
            key: _formKey,
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Text('Passeport sportif • ${widget.sport.name}',
                  style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 12),
                const Text('Renseigne ton profil. Tes informations ne sont '
                    'pas publiées automatiquement.'),
                const SizedBox(height: 16),
                if (_athleteId == null) ...[
                  _field(_firstName, 'Prénom', required: true),
                  _field(_lastName, 'Nom', required: true),
                  _field(_country, 'Pays'),
                  _field(_city, 'Ville'),
                  _field(_speciality, 'Discipline / spécialité'),
                  _field(_club, 'Club actuel'),
                  _field(_summary, 'Parcours sportif', lines: 3),
                  FilledButton(
                    onPressed: _busy ? null : _createAthlete,
                    child: Text(_busy ? 'Enregistrement…' : 'Créer mon passeport'),
                  ),
                ] else ...[
                  const Icon(Icons.check_circle_outline, size: 44),
                  const Text('Passeport créé. Tu peux maintenant '
                      'déposer une photo pour vérification.'),
                  const SizedBox(height: 12),
                  FilledButton.icon(
                    icon: const Icon(Icons.add_a_photo_outlined),
                    onPressed: _busy ? null : _uploadPhoto,
                    label: const Text('Téléverser une photo'),
                  ),
                  const SizedBox(height: 12),
                  const Text('La vidéo courte (15–30 secondes) sera '
                      'activée après validation du stockage et du contrôle '
                      'automatique de durée.'),
                ],
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!, style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                  )),
                ],
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _field(TextEditingController controller, String label, {
    bool required = false, int lines = 1,
  }) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: TextFormField(
      controller: controller,
      maxLines: lines,
      decoration: InputDecoration(
        labelText: label, border: const OutlineInputBorder(),
      ),
      validator: required ? (value) => (value?.trim().isEmpty ?? true)
          ? 'Champ obligatoire' : null : null,
    ),
  );
}

class _SubscriptionStep extends ConsumerStatefulWidget {
  const _SubscriptionStep({required this.onReload});
  final VoidCallback onReload;
  @override
  ConsumerState<_SubscriptionStep> createState() => _SubscriptionStepState();
}

class _SubscriptionStepState extends ConsumerState<_SubscriptionStep> {
  String? _message;
  String? _selectedPlan;
  bool _busy = false;

  Future<void> _initiate(String code) async {
    setState(() { _busy = true; _message = null; });
    try {
      final payment = await ref.read(apiClientProvider)
          .postObject('/payments/initiate', data: {'plan_code': code});
      if (mounted) setState(() => _message =
          'Demande de paiement créée : ${payment['reference']}. '
          'Statut : ${payment['status']}. L’abonnement ne sera ouvert '
          'qu’après confirmation effective du paiement.');
    } catch (_) {
      if (mounted) setState(() => _message =
          'Paiement non disponible pour cette offre. Aucun abonnement activé.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<List<dynamic>>(
    future: ref.read(apiClientProvider).getList('/payments/plans'),
    builder: (context, snapshot) => ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('Abonnement requis',
          style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 10),
        const Text('Pour créer ton dossier sportif et déposer des médias, '
            'ton abonnement doit être actif. '
            'Une demande de paiement en attente ne suffit pas.'),
        const SizedBox(height: 15),
        if (snapshot.hasData)
          for (final raw in snapshot.data!)
            RadioListTile<String>(
              title: Text((raw as Map)['name'].toString()),
              subtitle: Text('${raw['amount_minor']} ${raw['currency']} '
                  '• ${raw['duration_days']} jours'),
              value: raw['plan_code'].toString(),
              groupValue: _selectedPlan,
              onChanged: (value) => setState(() => _selectedPlan = value),
            ),
        if (snapshot.connectionState == ConnectionState.waiting)
          const LinearProgressIndicator(),
        if (snapshot.hasError)
          const Text('Catalogue des abonnements indisponible.'),
        if (snapshot.hasData && snapshot.data!.isEmpty)
          const Text('Aucune offre achetable disponible pour le moment.'),
        FilledButton(
          onPressed: _busy || _selectedPlan == null
              ? null : () => _initiate(_selectedPlan!),
          child: Text(_busy ? 'Préparation…' : 'Préparer le paiement'),
        ),
        if (_message != null) Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: SelectableText(_message!),
        ),
        OutlinedButton.icon(
          onPressed: widget.onReload,
          icon: const Icon(Icons.refresh),
          label: const Text('Vérifier mon abonnement'),
        ),
      ],
    ),
  );
}
