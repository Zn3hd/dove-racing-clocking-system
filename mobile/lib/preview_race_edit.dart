import 'package:flutter/material.dart';
import 'api.dart';

class PreviewRaceEditPage extends StatefulWidget {
  final RacingApi api;
  final String token;
  final Map<String, dynamic> race;
  const PreviewRaceEditPage({super.key, required this.api,
    required this.token, required this.race});

  @override
  State<PreviewRaceEditPage> createState() => _PreviewRaceEditPageState();
}

class _PreviewRaceEditPageState extends State<PreviewRaceEditPage> {
  final form = GlobalKey<FormState>();
  final controllers = <String, TextEditingController>{};
  late String unit;
  late String ranking;
  bool busy = false;
  String? error;

  @override
  void initState() {
    super.initState();
    for (final key in ['name', 'release_latitude', 'release_longitude',
        'minimum_speed_mpm', 'maximum_speed_mpm']) {
      controllers[key] = TextEditingController(
        text: widget.race[key]?.toString() ??
            (key == 'minimum_speed_mpm' ? '500' :
             key == 'maximum_speed_mpm' ? '3000' : ''));
    }
    unit = widget.race['display_speed_unit']?.toString() ?? 'm/min';
    ranking = widget.race['guest_ranking_mode']?.toString() ?? 'separate';
  }

  @override
  void dispose() {
    for (final controller in controllers.values) { controller.dispose(); }
    super.dispose();
  }

  Widget field(String key, String label, {bool numeric = false}) =>
      Padding(padding: const EdgeInsets.only(bottom: 12),
        child: TextFormField(controller: controllers[key],
          keyboardType: numeric
              ? const TextInputType.numberWithOptions(decimal: true, signed: true)
              : TextInputType.text,
          decoration: InputDecoration(labelText: label,
            border: const OutlineInputBorder()),
          validator: (value) {
            final text = value?.trim() ?? '';
            if (text.isEmpty) return '$label is required';
            if (!numeric) return null;
            final number = double.tryParse(text);
            if (number == null || !number.isFinite) return 'Enter a valid number';
            if (key == 'release_latitude' && (number < -90 || number > 90)) {
              return 'Latitude must be between -90 and 90';
            }
            if (key == 'release_longitude' && (number < -180 || number > 180)) {
              return 'Longitude must be between -180 and 180';
            }
            if (key == 'minimum_speed_mpm' && number <= 0) {
              return 'Minimum speed must be positive';
            }
            return null;
          }));

  Future<void> save() async {
    if (busy || !(form.currentState?.validate() ?? false)) return;
    final min = double.parse(controllers['minimum_speed_mpm']!.text.trim());
    final max = double.parse(controllers['maximum_speed_mpm']!.text.trim());
    if (max <= min) {
      setState(() => error = 'Maximum speed must exceed minimum speed.');
      return;
    }
    final confirmed = await showDialog<bool>(context: context,
      builder: (context) => AlertDialog(
        title: const Text('Save draft race settings?'),
        content: const Text('This only updates temporary demo data. Official clocking stays disabled.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true),
            child: const Text('Save')),
        ]));
    if (confirmed != true || !mounted) return;
    setState(() { busy = true; error = null; });
    try {
      await widget.api.updatePreviewRace(widget.token,
        widget.race['id'].toString(), {
          'name': controllers['name']!.text.trim(),
          'release_latitude': double.parse(controllers['release_latitude']!.text.trim()),
          'release_longitude': double.parse(controllers['release_longitude']!.text.trim()),
          'minimum_speed_mpm': min, 'maximum_speed_mpm': max,
          'display_speed_unit': unit, 'guest_ranking_mode': ranking,
        });
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } catch (_) {
      if (mounted) setState(() => error = 'Unable to save demo race.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Edit demo draft race')),
    body: Form(key: form, child: ListView(padding: const EdgeInsets.all(20),
      children: [
        const Text('Sandbox only. Draft races cannot be started or clocked here.'),
        const SizedBox(height: 16),
        field('name', 'Race name'),
        field('release_latitude', 'Release latitude', numeric: true),
        field('release_longitude', 'Release longitude', numeric: true),
        field('minimum_speed_mpm', 'Minimum speed (m/min)', numeric: true),
        field('maximum_speed_mpm', 'Maximum speed (m/min)', numeric: true),
        DropdownButtonFormField<String>(initialValue: unit,
          decoration: const InputDecoration(labelText: 'Display speed unit'),
          items: ['m/min', 'm/s', 'km/h'].map((v) =>
            DropdownMenuItem(value: v, child: Text(v))).toList(),
          onChanged: busy ? null : (v) => setState(() => unit = v ?? 'm/min')),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(initialValue: ranking,
          decoration: const InputDecoration(labelText: 'Guest leaderboard'),
          items: const [
            DropdownMenuItem(value: 'separate', child: Text('Separate')),
            DropdownMenuItem(value: 'combined', child: Text('Combined')),
          ],
          onChanged: busy ? null : (v) => setState(() => ranking = v ?? 'separate')),
        if (error != null) Padding(padding: const EdgeInsets.only(top: 12),
          child: Text(error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error))),
        const SizedBox(height: 20),
        FilledButton(onPressed: busy ? null : save,
          child: Text(busy ? 'Saving…' : 'Save demo changes')),
      ])),
  );
}
