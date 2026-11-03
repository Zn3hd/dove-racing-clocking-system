import 'package:flutter/material.dart';
import 'api.dart';

/// Only used by the isolated WEB_PREVIEW sandbox, never the live Android API.
class PreviewParticipantEditPage extends StatefulWidget {
  final RacingApi api;
  final String token;
  final Map<String, dynamic> participant;
  const PreviewParticipantEditPage({super.key, required this.api,
    required this.token, required this.participant});

  @override
  State<PreviewParticipantEditPage> createState() => _PreviewParticipantEditPageState();
}

class _PreviewParticipantEditPageState extends State<PreviewParticipantEditPage> {
  final key = GlobalKey<FormState>();
  late final TextEditingController name;
  late final TextEditingController email;
  late String role;
  bool saving = false;
  String? error;

  @override
  void initState() {
    super.initState();
    name = TextEditingController(text: widget.participant['full_name']?.toString() ?? '');
    email = TextEditingController(text: widget.participant['email']?.toString() ?? '');
    role = widget.participant['role_code'] == 'guest' ? 'guest' : 'member';
  }

  @override
  void dispose() {
    name.dispose();
    email.dispose();
    super.dispose();
  }

  Future<void> save() async {
    if (saving || !(key.currentState?.validate() ?? false)) return;
    final approved = await showDialog<bool>(context: context, builder: (context) =>
      AlertDialog(
        title: const Text('Save demo changes?'),
        content: const Text('This changes temporary preview data only. Reloading the browser resets it.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Save')),
        ],
      ));
    if (approved != true || !mounted) return;
    setState(() { saving = true; error = null; });
    try {
      await widget.api.updatePreviewParticipant(widget.token,
        widget.participant['id'].toString(), {
          'full_name': name.text.trim(), 'email': email.text.trim(), 'role': role,
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
    appBar: AppBar(title: const Text('Edit demo participant')),
    body: Form(key: key, child: ListView(padding: const EdgeInsets.all(20), children: [
      const Text('Sandbox only — no production records are changed.'),
      const SizedBox(height: 16),
      TextFormField(controller: name, decoration: const InputDecoration(
        labelText: 'Full name', border: OutlineInputBorder()),
        validator: (v) => v == null || v.trim().isEmpty ? 'Name is required' : null),
      const SizedBox(height: 12),
      TextFormField(controller: email, keyboardType: TextInputType.emailAddress,
        decoration: const InputDecoration(labelText: 'Email', border: OutlineInputBorder()),
        validator: (v) => v == null || !v.trim().contains('@') ? 'Enter a valid email' : null),
      const SizedBox(height: 12),
      DropdownButtonFormField<String>(initialValue: role,
        decoration: const InputDecoration(labelText: 'Role', border: OutlineInputBorder()),
        items: const [
          DropdownMenuItem(value: 'member', child: Text('Member')),
          DropdownMenuItem(value: 'guest', child: Text('Guest')),
        ],
        onChanged: saving ? null : (v) => setState(() => role = v ?? 'member')),
      if (error != null) Padding(padding: const EdgeInsets.only(top: 12),
        child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
      const SizedBox(height: 20),
      FilledButton(onPressed: saving ? null : save,
        child: Text(saving ? 'Saving…' : 'Save demo changes')),
    ])),
  );
}
