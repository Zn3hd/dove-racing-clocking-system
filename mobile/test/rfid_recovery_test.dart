import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:dove_racing_mobile/rfid/queue.dart';
import 'package:dove_racing_mobile/rfid/sync.dart';

const owner = '00000000-0000-4000-8000-000000000001';
const device = '00000000-0000-4000-8000-000000000002';
const race = '00000000-0000-4000-8000-000000000003';
const event = '00000000-0000-4000-8000-000000000004';
const other = '00000000-0000-4000-8000-000000000005';
ReaderBinding binding([String who = owner]) => ReaderBinding(
    ownerId: who,
    origin: 'https://test.example',
    deviceId: device,
    raceId: race);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  sqfliteFfiInit();
  late Directory directory;
  late RfidQueue queue;
  setUp(() async {
    directory = await Directory.systemTemp.createTemp('pigeon-recovery-');
    queue = await RfidQueue.open(
        path: '${directory.path}/queue.db', factory: databaseFactoryFfi);
  });
  tearDown(() async {
    await queue.close();
    await directory.delete(recursive: true);
  });

  test('keyboard input remains operator evidence with leading zeros', () async {
    await queue.captureKeyboard(binding(), '00001234\r\n');
    final payload = jsonDecode(
        (await queue.due(binding(), DateTime.now().millisecondsSinceEpoch))
            .single
            .payload);
    expect(payload['capture_mode'], 'operator');
    expect(payload['adapter_type'], 'usb_hid');
    expect(payload['protocol'], 'ascii-newline-v1');
    expect(payload['ring_uid'], '00001234');
  });

  test(
      'backup cleanup cannot delete pending, rejected, later receipts or another owner',
      () async {
    final b = binding();
    for (final uid in ['received', 'pending', 'rejected']) {
      await queue.captureSimulation(b, uid);
    }
    await queue.captureSimulation(binding(other), 'different owner');
    final rows = await queue.due(b, DateTime.now().millisecondsSinceEpoch);
    await queue.acknowledge(rows[0], event);
    await queue.reject(rows[2], 422);
    final exported = await queue.exportEvidence(b);
    expect(exported.receivedCount, 1);
    expect(jsonDecode(exported.json)['format'], 'pigeon-evidence-v1');
    expect(exported.json.contains('different owner'), false);
    await expectLater(queue.pruneReceived(b, exported, backupConfirmed: false),
        throwsStateError);
    await expectLater(
        queue.pruneReceived(binding(other), exported, backupConfirmed: true),
        throwsStateError);
    await queue.acknowledge(rows[1], event);
    expect(await queue.pruneReceived(b, exported, backupConfirmed: true), 1);
    expect(await queue.counts(b), {'received': 1, 'rejected': 1});
    expect((await queue.counts(binding(other)))['pending'], 1);
    expect(await queue.pruneReceived(b, exported, backupConfirmed: true), 0);
  });

  test(
      'heartbeat reports scoped counts without declaring physical reader health',
      () async {
    await queue.captureSimulation(binding(), '00001234');
    await queue.captureSimulation(binding(other), 'different owner');
    final client = MockClient((request) async {
      expect(request.followRedirects, false);
      expect(request.headers['X-Device-Token'], 'device-secret');
      expect(request.headers.containsKey('Authorization'), false);
      expect(jsonDecode(request.body), {
        'reader_state': 'not_probed',
        'pending_count': 1,
        'rejected_count': 0
      });
      return http.Response(
          jsonEncode({
            'device_id': device,
            'received_at': DateTime.now().toUtc().toIso8601String(),
            'official_result_created': false
          }),
          200);
    });
    expect(
        await DeviceSync(queue, client).heartbeat(binding(), 'device-secret'),
        'received');
    client.close();
  });

  test(
      'heartbeat revocation blocks subsequent uploads until credential correction',
      () async {
    await queue.captureSimulation(binding(), '00001234');
    var calls = 0;
    final client = MockClient((_) async {
      calls++;
      return http.Response('{}', 401);
    });
    final sync = DeviceSync(queue, client);
    expect(await sync.heartbeat(binding(), 'revoked-secret'),
        'authorization blocked');
    expect((await sync.synchronize(binding(), 'revoked-secret')).paused, true);
    expect(calls, 1);
    client.close();
  });
}
