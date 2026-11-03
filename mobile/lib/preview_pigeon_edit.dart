import 'package:flutter/material.dart';
import 'api.dart';

/// In-memory browser demo only; not enabled for production Android.
class PreviewPigeonEditPage extends StatefulWidget {
  final RacingApi api;
  final String token;
  final Map<String, dynamic> pigeon;
  const PreviewPigeonEditPage({super.key, required this.api,
    required this.token, required this.pigeon});

  @override
  State<PreviewPigeonEditPage> createState() => _PreviewPigeonEditPageState();
}

class _PreviewPigeonEditPageState extends State<PreviewPigeonEditPage> {
  final formKey = GlobalKey<FormState>();
  late final TextEditingController ring;
  late final TextEditingController name;
  bool saving = false;
  String? error;

  @override
  void initState() {
    super.initState();
    ring = TextEditingController(
      text: widget.pigeon['official_ring_number']?.toString() ?? '');
    name = TextEditingController(text: widget.pigeon['name']?.toString() ?? '');
  }

  @override
  void dispose() {
    ring.dispose();
    name.dispose();
    super.dispose();
  }

  Future<void> save() async {
    if (saving || !(formKey.currentState?.validate() ?? false)) return;
    final approved = await showDialog<bool>(context: context, builder: (context) =>
      AlertDialog(
        title: const Text('Save demo pigeon changes?'),
        content: const Text('Only temporary browser data will change. Reloading resets the demo.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true),
            child: const Text('Save')),
        ],
      ));
    if (approved != true || !mounted) return;
    setState(() { saving = true; error = null; });
    try {
      await widget.api.updatePreviewPigeon(widget.token,
        widget.pigeon['id'].toString(), {
          'official_ring_number': ring.text.trim(),
          'name': name.text.trim(),
        });
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } catch (_) {
      if (mounted) setState(() => error = 'Could not save demo changes.');
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Edit demo pigeon')),
    body: Form(key: formKey, child: ListView(
      padding: const EdgeInsets.all(20), children: [
        const Text('Sandbox only — no real pigeons or RFID rings are changed.'),
        const SizedBox(height: 16),
        TextFormField(controller: ring,
          decoration: const InputDecoration(
            labelText: 'Official ring number', border: OutlineInputBorder()),
          validator: (v) => v == null || v.trim().isEmpty
              ? 'Official ring number is required' : null),
        const SizedBox(height: 12),
        TextFormField(controller: name,
          decoration: const InputDecoration(
            labelText: 'Pigeon name (optional)', border: OutlineInputBorder())),
        if (error != null) Padding(padding: const EdgeInsets.only(top: 12),
          child: Text(error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error))),
        const SizedBox(height: 20),
        FilledButton(onPressed: saving ? null : save,
          child: Text(saving ? 'Saving…' : 'Save demo changes')),
      ],
    )),
  );
}
