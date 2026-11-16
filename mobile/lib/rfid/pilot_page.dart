import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'queue.dart';
import 'sync.dart';
import 'keyboard_capture.dart';

/// Administrator-only, foreground simulator. No physical-reader claim or adapter.
class RfidPilotPage extends StatefulWidget {
  final String ownerId, origin;
  final String? assignedDevice, assignedRace;
  final bool keyboardMode, resumeEnrolledCredential;
  const RfidPilotPage(
      {super.key,
      required this.ownerId,
      required this.origin,
      this.assignedDevice,
      this.assignedRace,
      this.keyboardMode = false,
      this.resumeEnrolledCredential = false});
  @override
  State<RfidPilotPage> createState() => _RfidPilotPageState();
}

class _RfidPilotPageState extends State<RfidPilotPage>
    with WidgetsBindingObserver {
  static const vault = FlutterSecureStorage();
  final device = TextEditingController(), race = TextEditingController();
  final secret = TextEditingController(), ring = TextEditingController();
  final form = GlobalKey<FormState>();
  final scanFocus = FocusNode();
  RfidQueue? queue;
  ReaderBinding? binding;
  DeviceSync? sync;
  KeyboardCapture? keyboard;
  http.Client? client;
  Timer? timer;
  Future<void>? worker;
  Map<String, int> counts = {};
  List<Map<String, Object?>> recent = [];
  bool confirmed = false, busy = false, enabled = false, fault = false;
  bool foreground = true;
  DateTime? lastHeartbeat;
  String heartbeat = 'not sent';
  String? deviceToken;
  String notice =
      'Configure a separately provisioned simulator reader and a test race.';

  @override
  void initState() {
    super.initState();
    device.text = widget.assignedDevice ?? '';
    race.text = widget.assignedRace ?? '';
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    if (state != AppLifecycleState.resumed && mounted) {
      timer?.cancel();
      setState(() {
        enabled = false;
        notice = 'Foreground synchronization stopped. Resume here when ready.';
      });
    }
  }

  Future<void> refresh() async {
    final q = queue, b = binding;
    if (q == null || b == null) return;
    final totals = await q.counts(b);
    final records = await q.recent(b);
    if (mounted) {
      setState(() {
        counts = totals;
        recent = records;
      });
    }
  }

  Future<void> configure() async {
    if (busy || !(form.currentState?.validate() ?? false)) return;
    if (!confirmed) {
      setState(() => notice = widget.keyboardMode
          ? 'Confirm operator scanning and review requirements.'
          : 'Confirm that this is a simulator reader and test race.');
      return;
    }
    setState(() => busy = true);
    RfidQueue? opened;
    try {
      final b = ReaderBinding(
          ownerId: widget.ownerId,
          origin: widget.origin,
          deviceId: device.text.trim(),
          raceId: race.text.trim());
      final entered = secret.text;
      final token =
          entered.isEmpty ? await vault.read(key: b.credentialKey) : entered;
      validateDeviceToken(token ?? '');
      opened = await RfidQueue.open();
      if (entered.isNotEmpty) {
        await vault.write(key: b.credentialKey, value: token);
        await opened.resumeAuthorization(b);
      }
      if (widget.resumeEnrolledCredential) await opened.resumeAuthorization(b);
      if (!mounted) {
        await opened.close();
        return;
      }
      queue = opened;
      opened = null;
      binding = b;
      deviceToken = token;
      client = http.Client();
      sync = DeviceSync(queue!, client!);
      if (widget.keyboardMode) {
        keyboard = KeyboardCapture((raw) => queue!.captureKeyboard(b, raw));
      }
      secret.clear();
      await refresh();
      if (mounted) {
        setState(() => notice = widget.keyboardMode
            ? 'Focused keyboard session configured. Reader connection is not independently probed.'
            : 'Simulator configured. No physical reader connected.');
      }
    } on FormatException catch (error) {
      if (mounted) setState(() => notice = error.message.toString());
    } catch (_) {
      if (mounted) {
        setState(() => notice =
            'Could not open storage or save the credential. Capture is unavailable.');
      }
    } finally {
      await opened?.close();
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> capture() async {
    if (widget.keyboardMode) {
      await captureKeyboard(ring.text);
      return;
    }
    if (busy || fault || !foreground || queue == null || binding == null) {
      return;
    }
    setState(() => busy = true);
    try {
      if (widget.keyboardMode) {
        await queue!.captureKeyboard(binding!, ring.text);
      } else {
        await queue!.captureSimulation(binding!, ring.text);
      }
      ring.clear();
      await refresh();
      if (mounted) {
        setState(() => notice = widget.keyboardMode
            ? 'Operator scan saved. Review is required before ranking.'
            : 'Simulated scan saved on this phone. It is not an official arrival.');
      }
    } on FormatException catch (error) {
      if (mounted) setState(() => notice = error.message.toString());
    } catch (_) {
      if (mounted) {
        setState(() {
          fault = true;
          enabled = false;
          timer?.cancel();
          notice =
              'Storage failed or is full. Capture stopped; retained evidence has not been deleted.';
        });
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
    if (mounted && widget.keyboardMode && foreground) scanFocus.requestFocus();
    if (enabled && !fault) launchSync();
  }

  Future<void> captureKeyboard(String raw) async {
    if (!foreground || fault || keyboard == null) return;
    // Clear immediately, before awaiting SQLite; the next frame has its own string.
    ring.clear();
    try {
      await keyboard!.capture(raw);
      await refresh();
      if (mounted) {
        setState(() => notice = 'Operator scan saved; review required.');
        if (foreground) scanFocus.requestFocus();
        if (enabled) launchSync();
      }
    } on FormatException catch (error) {
      if (mounted) setState(() => notice = error.message.toString());
    } catch (_) {
      if (mounted) {
        setState(() {
          fault = true;
          enabled = false;
          timer?.cancel();
          notice =
              'Keyboard capture stopped. A frame could not be saved. Inspect the reader and retained evidence before continuing.';
        });
      }
    }
  }

  void launchSync() {
    if (worker != null || !mounted || queue == null || deviceToken == null) {
      return;
    }
    worker = synchronize().whenComplete(() => worker = null);
  }

  Future<void> synchronize() async {
    try {
      final result = await sync!.synchronize(binding!, deviceToken!,
          shouldStop: () => !mounted || !enabled);
      if (mounted &&
          enabled &&
          !result.paused &&
          (lastHeartbeat == null ||
              DateTime.now().difference(lastHeartbeat!).inSeconds >= 30)) {
        lastHeartbeat = DateTime.now();
        heartbeat = await sync!.heartbeat(binding!, deviceToken!);
      }
      await refresh();
      if (mounted) {
        setState(() {
          notice =
              '${result.toString()}. Heartbeat: $heartbeat (gateway reachability only).';
          if (result.paused) {
            enabled = false;
            timer?.cancel();
          }
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          fault = true;
          enabled = false;
          timer?.cancel();
          notice =
              'Synchronization/storage unavailable. Capture stopped; pending evidence is retained.';
        });
      }
    }
  }

  Future<void> start() async {
    if (busy || fault || worker != null || !foreground) return;
    setState(() => busy = true);
    try {
      // Rate limits survive restarts. A new credential can clear only auth pauses.
      if (await queue!
          .paused(binding!, DateTime.now().millisecondsSinceEpoch)) {
        if (mounted) {
          setState(() => notice =
              'Synchronization paused. Wait for rate limits, or close and reopen setup with a valid device credential.');
        }
        return;
      }
      if (!mounted) return;
      setState(() => enabled = true);
      timer?.cancel();
      timer = Timer.periodic(const Duration(seconds: 5), (_) => launchSync());
      launchSync();
    } catch (_) {
      if (mounted) {
        setState(() =>
            notice = 'Unable to inspect the stored synchronization state.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> forgetCredential() async {
    if (worker != null || busy || binding == null) return;
    setState(() => busy = true);
    timer?.cancel();
    enabled = false;
    try {
      await vault.delete(key: binding!.credentialKey);
      deviceToken = null;
      if (mounted) {
        setState(() => notice =
            'Local credential forgotten. Server credential is not revoked; queued evidence remains.');
      }
    } catch (_) {
      if (mounted) {
        setState(() =>
            notice = 'Could not remove the credential from secure storage.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> exportEvidence() async {
    if (busy || worker != null || (keyboard?.pending ?? 0) > 0 || queue == null) {
      return;
    }
    setState(() => busy = true);
    final wasEnabled = enabled;
    enabled = false;
    timer?.cancel();
    try {
      final exported = await queue!.exportEvidence(binding!);
      if (!mounted) return;
      final accepted = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
                  title: const Text('Copy private clocking evidence?'),
                  content: Text(
                      'Copies up to 500 records including ring IDs and timestamps. Save privately. '
                      '${exported.receivedCount} received records can be cleaned after backup confirmation.'),
                  actions: [
                    TextButton(
                        onPressed: () => Navigator.pop(context, false),
                        child: const Text('Cancel')),
                    FilledButton(
                        onPressed: () => Navigator.pop(context, true),
                        child: const Text('Copy export'))
                  ]));
      if (accepted != true) return;
      await Clipboard.setData(ClipboardData(text: exported.json));
      if (!mounted) return;
      final confirmed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
                  title: const Text('Save the export before cleanup'),
                  content: const Text(
                      'Paste and save the JSON in a private file first. The clipboard alone is not a backup. '
                      'Cleanup removes only received records from this export. Pending and rejected evidence is retained.'),
                  actions: [
                    TextButton(
                        onPressed: () => Navigator.pop(context, false),
                        child: const Text('Keep all records')),
                    FilledButton(
                        onPressed: () => Navigator.pop(context, true),
                        child: const Text('I saved a backup; clean received'))
                  ]));
      if (confirmed == true) {
        final removed = await queue!
            .pruneReceived(binding!, exported, backupConfirmed: true);
        if (mounted) {
          setState(() => notice =
              '$removed received records cleaned. Pending and rejected evidence retained.');
        }
        await refresh();
      }
    } catch (_) {
      if (mounted) {
        setState(() => notice =
            'Export/cleanup could not finish. Inspect retained evidence before proceeding.');
      }
    } finally {
      if (mounted) {
        setState(() {
          busy = false;
          if (wasEnabled) {
            notice += ' Upload is stopped; restart it when ready.';
          }
        });
      }
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    enabled = false;
    timer?.cancel();
    client?.close();
    deviceToken = null;
    scanFocus.dispose();
    keyboard?.stop();
    final pending = worker;
    final q = queue;
    unawaited(() async {
      await pending;
      await keyboard?.drained;
      await q?.close();
    }());
    for (final controller in [device, race, secret, ring]) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
            title: Text(widget.keyboardMode
                ? 'Loft keyboard reader'
                : 'RFID simulator pilot')),
        body: ListView(padding: const EdgeInsets.all(20), children: [
          if (widget.keyboardMode)
            const Card(
                child: ListTile(
                    leading: Icon(Icons.keyboard),
                    title: Text('FOREGROUND OPERATOR SCANS — review required'),
                    subtitle: Text(
                        'Keep the ring field focused for a compatible keyboard-style reader. '
                        'Typing/scanning cannot prove physical arrival. Screen lock stops uploads.'))),
          if (!widget.keyboardMode)
            const Card(
                child: ListTile(
                    leading: Icon(Icons.science_outlined),
                    title: Text('TEST EVENTS ONLY — no physical reader'),
                    subtitle: Text(
                        'Foreground pilot. Screen lock or leaving this app stops synchronization. '
                        'Use a separate simulator reader and test race. Server receipt time is used; results remain provisional.'))),
          Text('Backend: ${widget.origin}'),
          const SizedBox(height: 12),
          if (binding == null)
            Form(
                key: form,
                child: Column(children: [
                  TextFormField(
                      controller: device,
                      readOnly: widget.assignedDevice != null,
                      decoration: const InputDecoration(
                          labelText: 'Simulator device ID'),
                      validator: (v) => isUuid(v?.trim() ?? '')
                          ? null
                          : 'Enter a device UUID.'),
                  TextFormField(
                      controller: race,
                      readOnly: widget.assignedRace != null,
                      decoration:
                          const InputDecoration(labelText: 'Test race ID'),
                      validator: (v) => isUuid(v?.trim() ?? '')
                          ? null
                          : 'Enter a race UUID.'),
                  if (widget.assignedDevice == null)
                    TextFormField(
                        controller: secret,
                        obscureText: true,
                        enableSuggestions: false,
                        autocorrect: false,
                        decoration: const InputDecoration(
                            labelText: 'Device credential',
                            helperText:
                                'Leave empty to use the credential saved for this account and reader.')),
                  CheckboxListTile(
                      value: confirmed,
                      onChanged: busy
                          ? null
                          : (v) => setState(() => confirmed = v ?? false),
                      title: Text(widget.keyboardMode
                          ? 'I understand operator scans require review.'
                          : 'This is a separately registered simulator and a test race.'),
                      subtitle: Text(widget.keyboardMode
                          ? 'Adapter: usb_hid · Protocol: ascii-newline-v1'
                          : 'Adapter: simulator · Protocol: mobile-simulator-v1')),
                  FilledButton(
                      onPressed: busy ? null : configure,
                      child: const Text('Open pilot queue')),
                ]))
          else ...[
            Text('Reader: ${binding!.deviceId}\nRace: ${binding!.raceId}'),
            const SizedBox(height: 12),
            Text(
                'Saved on phone: ${counts['pending'] ?? 0} · Received: ${counts['received'] ?? 0} · '
                'Rejected: ${counts['rejected'] ?? 0}'),
            TextFormField(
                controller: ring,
                focusNode: scanFocus,
                onFieldSubmitted: widget.keyboardMode ? captureKeyboard : null,
                decoration: InputDecoration(
                    labelText: widget.keyboardMode
                        ? 'Ring ID — keep focused for keyboard scans'
                        : 'Synthetic ring ID',
                    helperText:
                        'Register this exact ID in the test setup; leading zeros are preserved.')),
            FilledButton.icon(
                onPressed: busy || fault ? null : capture,
                icon: const Icon(Icons.add),
                label: Text(widget.keyboardMode
                    ? 'Record operator scan'
                    : 'Save simulated scan')),
            if (!enabled)
              OutlinedButton(
                  onPressed:
                      busy || fault || deviceToken == null ? null : start,
                  child: const Text('Start foreground upload')),
            if (enabled)
              OutlinedButton(
                  onPressed: () => setState(() {
                        enabled = false;
                        timer?.cancel();
                        notice = 'Stopped. Pending events remain saved.';
                      }),
                  child: const Text('Stop upload')),
            TextButton(
                onPressed: busy || worker != null ? null : forgetCredential,
                child: const Text('Forget local device credential')),
            TextButton(
                onPressed: busy || worker != null ? null : exportEvidence,
                child:
                    const Text('Export evidence / clean backed-up receipts')),
          ],
          const SizedBox(height: 12),
          Semantics(liveRegion: true, child: Text(notice)),
          for (final row in recent)
            ListTile(
                title: Text('${row['state']} · ${row['message_id']}'),
                subtitle: Text(row['error']?.toString() ??
                    (row['event_id'] == null
                        ? 'Saved evidence; no server receipt yet.'
                        : 'Server receipt recorded; eligibility is determined by the backend.'))),
        ]),
      );
}
