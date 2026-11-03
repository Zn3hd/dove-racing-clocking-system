import 'package:flutter/material.dart';
import 'api.dart';

enum ManagementKind { participant, pigeon, race }

class ManagementForm extends StatefulWidget {
  final RacingApi api;
  final String token;
  final String clubId;
  final ManagementKind kind;
  const ManagementForm({super.key, required this.api, required this.token,
    required this.clubId, required this.kind});
  @override
  State<ManagementForm> createState() => _ManagementFormState();
}

class _ManagementFormState extends State<ManagementForm> {
  final form = GlobalKey<FormState>();
  final fields = <String, TextEditingController>{};
  bool busy = false;
  String? error;
  String role = 'member';
  String unit = 'm/min';
  String ranking = 'separate';
  String? loftId;
  late final Future<List<Map<String, dynamic>>> lofts;

  @override
  void initState() {
    super.initState();
    if (widget.kind == ManagementKind.race) {
      fields['minimum_speed_mpm'] = TextEditingController(text: '500');
      fields['maximum_speed_mpm'] = TextEditingController(text: '3000');
    }
    lofts = widget.kind == ManagementKind.pigeon
        ? widget.api.lofts(widget.token, widget.clubId)
        : Future.value(<Map<String, dynamic>>[]);
  }

  @override
  void dispose() {
    for (final c in fields.values) { c.dispose(); }
    super.dispose();
  }

  String value(String key) => fields[key]!.text.trim();

  Widget field(String key, String label, {bool secret = false, bool optional = false,
      bool numeric = false}) {
    final controller = fields.putIfAbsent(key, TextEditingController.new);
    return Padding(padding: const EdgeInsets.only(bottom: 12), child: TextFormField(
      controller: controller, obscureText: secret,
      keyboardType: numeric ? const TextInputType.numberWithOptions(decimal: true)
          : key == 'email' ? TextInputType.emailAddress : TextInputType.text,
      decoration: InputDecoration(labelText: label, border: const OutlineInputBorder()),
      validator: (text) {
        final v = text?.trim() ?? '';
        if (v.isEmpty) return optional ? null : '$label is required';
        if (key == 'email' && !v.contains('@')) return 'Enter a valid email';
        if (key == 'password' && v.length < 12) return 'Use at least 12 characters';
        if (numeric && (double.tryParse(v) == null || !double.parse(v).isFinite)) {
          return 'Enter a valid number';
        }
        if (key == 'release_latitude' && (double.parse(v) < -90 || double.parse(v) > 90)) {
          return 'Latitude must be between -90 and 90';
        }
        if (key == 'release_longitude' && (double.parse(v) < -180 || double.parse(v) > 180)) {
          return 'Longitude must be between -180 and 180';
        }
        return null;
      },
    ));
  }

  Future<void> submit() async {
    if (busy || !(form.currentState?.validate() ?? false)) return;
    if (widget.kind == ManagementKind.pigeon && loftId == null) {
      setState(() => error = 'Select a verified loft first.');
      return;
    }
    setState(() { busy = true; error = null; });
    try {
      switch (widget.kind) {
        case ManagementKind.participant:
          await widget.api.createParticipant(widget.token, {
            'club_id': widget.clubId, 'full_name': value('full_name'),
            'email': value('email'), 'phone': value('phone').isEmpty ? null : value('phone'),
            'password': value('password'), 'role': role,
          });
        case ManagementKind.pigeon:
          await widget.api.createPigeon(widget.token, {
            'loft_id': loftId, 'official_ring_number': value('official_ring_number'),
            'name': value('name').isEmpty ? null : value('name'),
          });
        case ManagementKind.race:
          final min = double.parse(value('minimum_speed_mpm'));
          final max = double.parse(value('maximum_speed_mpm'));
          if (max <= min) throw ApiException('Maximum speed must exceed minimum speed.');
          await widget.api.createRace(widget.token, {
            'club_id': widget.clubId, 'name': value('name'),
            'release_latitude': double.parse(value('release_latitude')),
            'release_longitude': double.parse(value('release_longitude')),
            'minimum_speed_mpm': min, 'maximum_speed_mpm': max,
            'display_speed_unit': unit, 'guest_ranking_mode': ranking,
          });
      }
      if (mounted) Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } catch (_) {
      if (mounted) setState(() => error = 'Unable to save. Please retry.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final kind = widget.kind;
    final title = switch (kind) {
      ManagementKind.participant => 'Register participant',
      ManagementKind.pigeon => 'Register pigeon',
      ManagementKind.race => 'Create draft race',
    };
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Form(key: form, child: ListView(padding: const EdgeInsets.all(20), children: [
        if (kind == ManagementKind.participant) ...[
          field('full_name', 'Full name'),
          field('email', 'Email'),
          field('phone', 'Phone', optional: true),
          field('password', 'Temporary password (12+ characters)', secret: true),
          DropdownButtonFormField<String>(
            initialValue: role, decoration: const InputDecoration(labelText: 'Role'),
            items: const [DropdownMenuItem(value: 'member', child: Text('Member')),
              DropdownMenuItem(value: 'guest', child: Text('Guest'))],
            onChanged: (v) => setState(() => role = v ?? 'member'),
          ),
        ],
        if (kind == ManagementKind.pigeon) ...[
          FutureBuilder<List<Map<String, dynamic>>>(future: lofts,
            builder: (context, snapshot) {
              if (snapshot.hasError) return const Text('Could not load lofts. Retry opening this form.');
              if (!snapshot.hasData) return const LinearProgressIndicator();
              final verified = snapshot.data!.where((l) => l['verified_at'] != null).toList();
              if (verified.isEmpty) {
                return const Text('No verified lofts available. Create and verify a loft in the web dashboard first.');
              }
              return DropdownButtonFormField<String>(
                initialValue: loftId, isExpanded: true,
                decoration: const InputDecoration(labelText: 'Verified loft'),
                items: verified.map((l) => DropdownMenuItem(
                  value: l['id'].toString(), child: Text(l['name']?.toString() ?? 'Loft'),
                )).toList(),
                onChanged: (v) => setState(() => loftId = v),
              );
            }),
          const SizedBox(height: 12),
          field('official_ring_number', 'Official ring number'),
          field('name', 'Pigeon name', optional: true),
        ],
        if (kind == ManagementKind.race) ...[
          const Text('Creates a draft race only. Official clocking remains disabled.'),
          const SizedBox(height: 12),
          field('name', 'Race name'),
          field('release_latitude', 'Release latitude', numeric: true),
          field('release_longitude', 'Release longitude', numeric: true),
          field('minimum_speed_mpm', 'Minimum speed (m/min)', numeric: true),
          field('maximum_speed_mpm', 'Maximum speed (m/min)', numeric: true),
          DropdownButtonFormField<String>(
            initialValue: unit, decoration: const InputDecoration(labelText: 'Display speed unit'),
            items: ['m/min', 'm/s', 'km/h'].map((v) => DropdownMenuItem(
              value: v, child: Text(v))).toList(),
            onChanged: (v) => setState(() => unit = v ?? 'm/min'),
          ),
          DropdownButtonFormField<String>(
            initialValue: ranking, decoration: const InputDecoration(labelText: 'Guest leaderboard'),
            items: const [
              DropdownMenuItem(value: 'separate', child: Text('Separate')),
              DropdownMenuItem(value: 'combined', child: Text('Combined')),
            ], onChanged: (v) => setState(() => ranking = v ?? 'separate'),
          ),
        ],
        if (error != null) Padding(padding: const EdgeInsets.symmetric(vertical: 12),
          child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
        const SizedBox(height: 20),
        FilledButton(onPressed: busy ? null : submit,
          child: busy ? const CircularProgressIndicator() : Text(title)),
      ])),
    );
  }
}
