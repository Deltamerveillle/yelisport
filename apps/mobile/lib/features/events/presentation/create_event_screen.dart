import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:yelisport/features/events/domain/sport_event.dart';
import 'package:yelisport/features/events/presentation/events_providers.dart';
import 'package:yelisport/features/sports/presentation/sports_providers.dart';

class CreateEventScreen extends ConsumerStatefulWidget {
  const CreateEventScreen({super.key});

  @override
  ConsumerState<CreateEventScreen> createState() => _CreateEventScreenState();
}

class _CreateEventScreenState extends ConsumerState<CreateEventScreen> {
  final _formKey = GlobalKey<FormState>();
  final _title = TextEditingController();
  final _location = TextEditingController();
  final _capacity = TextEditingController(text: '20');
  String? _sportId;
  DateTime _startsAt = DateTime.now().add(const Duration(days: 1));
  bool _submitting = false;

  @override
  void dispose() {
    _title.dispose();
    _location.dispose();
    _capacity.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final date = await showDatePicker(
      context: context,
      initialDate: _startsAt,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 730)),
    );
    if (date != null) {
      setState(() {
        _startsAt = DateTime(date.year, date.month, date.day, 10);
      });
    }
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate() || _sportId == null) return;
    setState(() => _submitting = true);
    try {
      await ref.read(eventsRepositoryProvider).create(
            EventDraft(
              sportId: _sportId!,
              title: _title.text.trim(),
              location: _location.text.trim(),
              startsAt: _startsAt,
              endsAt: _startsAt.add(const Duration(hours: 2)),
              capacity: int.parse(_capacity.text),
            ),
          );
      ref.invalidate(upcomingEventsProvider);
      if (mounted) Navigator.of(context).pop();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Création de l'événement impossible.")),
        );
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final sports = ref.watch(allSportsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Créer un événement')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: Column(
            children: [
              sports.when(
                loading: () => const LinearProgressIndicator(),
                error: (error, _) => const Text('Sports indisponibles.'),
                data: (items) => DropdownButtonFormField<String>(
                  value: _sportId,
                  decoration: const InputDecoration(labelText: 'Sport'),
                  items: items
                      .map(
                        (sport) => DropdownMenuItem(
                          value: sport.id,
                          child: Text(sport.name),
                        ),
                      )
                      .toList(),
                  onChanged: (value) => setState(() => _sportId = value),
                  validator: (value) => value == null ? 'Choisissez un sport.' : null,
                ),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _title,
                decoration: const InputDecoration(labelText: 'Titre'),
                validator: (value) => (value?.trim().length ?? 0) >= 3
                    ? null
                    : '3 caractères minimum.',
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _location,
                decoration: const InputDecoration(labelText: 'Lieu'),
                validator: (value) => (value?.trim().length ?? 0) >= 2
                    ? null
                    : 'Lieu requis.',
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _capacity,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Nombre de places'),
                validator: (value) {
                  final number = int.tryParse(value ?? '');
                  return number != null && number > 0 ? null : 'Capacité invalide.';
                },
              ),
              const SizedBox(height: 16),
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Date'),
                subtitle: Text(DateFormat('dd/MM/yyyy à HH:mm').format(_startsAt)),
                trailing: const Icon(Icons.calendar_month),
                onTap: _pickDate,
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _submitting ? null : _submit,
                  child: Text(_submitting ? 'Création…' : 'Créer'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
