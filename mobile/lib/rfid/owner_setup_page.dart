import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../api.dart';
import 'pilot_page.dart';
import 'queue.dart';
import 'sync.dart';

class OwnerReaderSetupPage extends StatefulWidget {
  final RacingApi api;
  final String token, ownerId;
  final Future<void> Function() onUnauthorized;
  const OwnerReaderSetupPage(
      {super.key,
      required this.api,
      required this.token,
      required this.ownerId,
      required this.onUnauthorized});
  @override
  State<OwnerReaderSetupPage> createState() => _OwnerReaderSetupPageState();
}

class _OwnerReaderSetupPageState extends State<OwnerReaderSetupPage> {
  static const vault = FlutterSecureStorage();
  final code = TextEditingController();
  final newlyEnrolled = <String>{};
  List<Map<String, dynamic>> readers = [];
  bool busy = false;
  String? selected;
  String notice =
      'Get a private one-use reader invitation from your club administrator.';

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> run(Future<void> Function() action) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      await action();
    } on ApiException catch (error) {
      if (error.status == 401 && mounted) {
        Navigator.of(context).pop();
        await widget.onUnauthorized();
      } else if (mounted) {
        setState(() => notice = error.message);
      }
    } catch (_) {
      if (mounted) {
        setState(() => notice =
            'Setup could not finish. Retained evidence is unchanged. If an invitation was consumed, request a fresh one.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> load() => run(() async {
        final response =
            await widget.api.request('/member/readers', token: widget.token);
        if (response is! List) throw const FormatException();
        final values = response
            .map((row) => Map<String, dynamic>.from(row as Map))
            .toList();
        if (mounted) {
          setState(() {
            readers = values;
            selected = null;
            notice = readers.isEmpty
                ? 'No assigned readers. Ask your administrator to register your verified loft and reader.'
                : 'Choose your reader and an active RFID race. You can enroll before the race starts.';
          });
        }
      });

  Future<void> enroll() => run(() async {
        final response = await widget.api.request(
            '/member/reader-enrollments/redeem',
            method: 'POST',
            token: widget.token,
            body: {'code': code.text.trim()});
        code.clear();
        if (response is! Map ||
            response['device_id'] is! String ||
            response['device_token'] is! String) {
          throw const FormatException();
        }
        final token = response['device_token'] as String;
        validateDeviceToken(token);
        // Race is not part of the credential key. No event is created by enrollment.
        final identity = ReaderBinding(
            ownerId: widget.ownerId,
            origin: widget.api.baseUrl,
            deviceId: response['device_id'],
            raceId: '00000000-0000-0000-0000-000000000000');
        await vault.write(key: identity.credentialKey, value: token);
        newlyEnrolled.add(identity.deviceId);
        if (mounted) {
          setState(() => notice =
              'Reader enrolled securely. The earlier gateway credential has been rotated.');
        }
      });

  Future<void> open() => run(() async {
        final index = int.tryParse(selected ?? '');
        if (index == null || index < 0 || index >= readers.length) return;
        final row = readers[index];
        if (row['race_id'] == null) {
          setState(() => notice =
              'No active RFID race for this loft. Enrollment can still be completed above.');
          return;
        }
        final simulated = row['reader_adapter'] == 'simulator' &&
            row['reader_protocol'] == 'mobile-simulator-v1';
        final keyboard = row['reader_adapter'] == 'usb_hid' &&
            row['reader_protocol'] == 'ascii-newline-v1';
        if (!simulated && !keyboard) {
          setState(() => notice =
              'This reader protocol is not supported on the phone yet. Ask the administrator to verify compatibility.');
          return;
        }
        final identity = ReaderBinding(
            ownerId: widget.ownerId,
            origin: widget.api.baseUrl,
            deviceId: row['id'],
            raceId: row['race_id']);
        final saved = await vault.read(key: identity.credentialKey);
        if (saved == null) {
          setState(() =>
              notice = 'Enroll this reader with a private invitation first.');
          return;
        }
        validateDeviceToken(saved);
        if (mounted) {
          await Navigator.of(context).push(MaterialPageRoute<void>(
              builder: (_) => RfidPilotPage(
                  ownerId: widget.ownerId,
                  origin: widget.api.baseUrl,
                  assignedDevice: identity.deviceId,
                  assignedRace: identity.raceId,
                  keyboardMode: keyboard,
                  resumeEnrolledCredential:
                      newlyEnrolled.remove(identity.deviceId))));
        }
      });

  @override
  void dispose() {
    code.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('My loft reader')),
        body: ListView(padding: const EdgeInsets.all(20), children: [
          const Text(
              'Foreground pilot. Keyboard scans are operator evidence and require review. '
              'Automatic physical arrival detection is not certified.'),
          const SizedBox(height: 16),
          TextField(
              controller: code,
              obscureText: true,
              autocorrect: false,
              enableSuggestions: false,
              decoration: const InputDecoration(
                  labelText: 'Private owner invitation',
                  helperText:
                      'One use, expires after 10 minutes. It is not a pigeon arrival QR code.')),
          FilledButton(
              onPressed: busy ? null : enroll,
              child: const Text('Enroll reader')),
          const SizedBox(height: 16),
          DropdownButtonFormField<String>(
              initialValue: selected,
              key: ObjectKey(readers),
              isExpanded: true,
              decoration:
                  const InputDecoration(labelText: 'Reader / active race'),
              items: [
                for (var i = 0; i < readers.length; i++)
                  DropdownMenuItem(
                      value: '$i',
                      child: Text(
                          '${readers[i]['device_identifier']} · ${readers[i]['race_name'] ?? 'No active race'}',
                          overflow: TextOverflow.ellipsis))
              ],
              onChanged:
                  busy ? null : (value) => setState(() => selected = value)),
          FilledButton(
              onPressed: busy || selected == null ? null : open,
              child: const Text('Open reader session')),
          TextButton(
              onPressed: busy ? null : load,
              child: const Text('Refresh assignments')),
          const SizedBox(height: 12),
          Semantics(liveRegion: true, child: Text(notice)),
        ]),
      );
}
