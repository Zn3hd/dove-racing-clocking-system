import 'dart:async';
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
const alternate = '00000000-0000-4000-8000-000000000005';
final time = DateTime.utc(2026, 11, 16, 12);

ReaderBinding binding(
        {String who = owner,
        String reader = device,
        String raceId = race,
        String origin = 'https://test.example'}) =>
    ReaderBinding(
        ownerId: who, origin: origin, deviceId: reader, raceId: raceId);
http.Response ack() => http.Response(
    jsonEncode({
      'event_id': event,
      'status': 'pending',
      'official_result_created': false
    }),
    202);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  sqfliteFfiInit();
  late Directory directory;
  late String path;
  late RfidQueue queue;
  setUp(() async {
    directory = await Directory.systemTemp.createTemp('pigeon-mobile-test-');
    path = '${directory.path}/queue.db';
    queue = await RfidQueue.open(path: path, factory: databaseFactoryFfi);
  });
  tearDown(() async {
    await queue.close();
    await directory.delete(recursive: true);
  });

  test('committed simulator envelope survives reopen with immutable routing',
      () async {
    final b = binding();
    final id =
        await queue.captureSimulation(b, '00001234\r\n', observedAt: time);
    await queue.close();
    queue = await RfidQueue.open(path: path, factory: databaseFactoryFfi);
    final rows = await queue.due(b, time.millisecondsSinceEpoch);
    expect(rows.single.messageId, id);
    final payload = jsonDecode(rows.single.payload);
    expect(payload['ring_uid'], '00001234');
    expect(payload['original_scan'], '00001234\r\n');
    expect(payload['race_id'], race);
    expect(payload['capture_mode'], 'simulated');
    expect(payload['adapter_type'], 'simulator');
    expect(payload['protocol'], 'mobile-simulator-v1');
    expect(payload['offline_buffered'], true);
    expect(payload['device_recorded_at'], time.toIso8601String());
    final db = await databaseFactoryFfi.openDatabase(path,
        options: OpenDatabaseOptions(singleInstance: false));
    await expectLater(db.rawUpdate('UPDATE events SET payload=?', ['{}']),
        throwsA(isA<DatabaseException>()));
    await db.close();
  });

  test('owner, origin, device and race each isolate retained evidence',
      () async {
    await queue.captureSimulation(binding(), '00001234');
    for (final other in [
      binding(who: alternate),
      binding(reader: alternate),
      binding(raceId: alternate),
      binding(origin: 'https://other.example')
    ]) {
      expect(await queue.counts(other), isEmpty);
      expect(await queue.due(other, time.millisecondsSinceEpoch), isEmpty);
      expect(await queue.recent(other), isEmpty);
    }
    expect((await queue.counts(binding()))['pending'], 1);
  });

  test('capacity exhaustion refuses new capture and retains the first event',
      () async {
    await queue.close();
    queue = await RfidQueue.open(
        path: path, factory: databaseFactoryFfi, capacity: 1);
    final first = await queue.captureSimulation(binding(), '00001');
    await expectLater(
        queue.captureSimulation(binding(), '00002'), throwsStateError);
    expect((await queue.recent(binding())).single['message_id'], first);
  });

  test('lost acknowledgement retries identical committed payload after restart',
      () async {
    final b = binding();
    await queue.captureSimulation(b, '00001234');
    String? committed;
    var calls = 0;
    final client = MockClient((request) async {
      expect(request.followRedirects, false);
      expect(request.headers['X-Device-Token'], 'device-secret');
      expect(request.headers.containsKey('Authorization'), false);
      expect(request.url.toString(),
          'https://test.example/devices/$device/arrivals');
      calls++;
      if (committed == null) {
        committed = request.body;
        throw http.ClientException(
            'Lost acknowledgement after simulated server commit');
      }
      expect(request.body, committed);
      return ack();
    });
    expect(
        (await DeviceSync(queue, client)
                .synchronize(b, 'device-secret', now: time))
            .retry,
        1);
    await queue.close();
    queue = await RfidQueue.open(path: path, factory: databaseFactoryFfi);
    final result = await DeviceSync(queue, client).synchronize(
        b, 'device-secret',
        now: time.add(const Duration(seconds: 10)));
    expect(result.received, 1);
    expect(calls, 2);
    expect((await queue.counts(b))['received'], 1);
    expect(
        await queue.due(
            b, time.add(const Duration(days: 1)).millisecondsSinceEpoch),
        isEmpty);
    client.close();
  });

  test(
      'authorization pause survives restart and requires credential correction',
      () async {
    final b = binding();
    await queue.captureSimulation(b, '00001234');
    final rejected = MockClient(
        (_) async => http.Response('secret must not enter queue', 401));
    expect(
        (await DeviceSync(queue, rejected)
                .synchronize(b, 'bad-secret', now: time))
            .paused,
        true);
    await queue.close();
    queue = await RfidQueue.open(path: path, factory: databaseFactoryFfi);
    var calls = 0;
    final corrected = MockClient((_) async {
      calls++;
      return ack();
    });
    final sync = DeviceSync(queue, corrected);
    expect(
        (await sync.synchronize(b, 'new-secret',
                now: time.add(const Duration(days: 1))))
            .paused,
        true);
    expect(calls, 0);
    expect((await queue.recent(b)).single['error'],
        'Device authorization blocked.');
    await queue.resumeAuthorization(b);
    expect((await sync.synchronize(b, 'new-secret', now: time)).received, 1);
    rejected.close();
    corrected.close();
  });

  test(
      'rate limit pauses all events and cannot be bypassed by credential reset',
      () async {
    final b = binding();
    await queue.captureSimulation(b, '00001234');
    await queue.captureSimulation(b, '00005678');
    var calls = 0;
    final limited = MockClient((_) async {
      calls++;
      return http.Response('{}', 429, headers: {'retry-after': '120'});
    });
    expect(
        (await DeviceSync(queue, limited).synchronize(b, 'secret', now: time))
            .paused,
        true);
    expect(calls, 1);
    await queue.close();
    queue = await RfidQueue.open(path: path, factory: databaseFactoryFfi);
    await queue.resumeAuthorization(b);
    final corrected = MockClient((_) async {
      calls++;
      return ack();
    });
    final sync = DeviceSync(queue, corrected);
    expect(
        (await sync.synchronize(b, 'secret',
                now: time.add(const Duration(seconds: 60))))
            .paused,
        true);
    expect(calls, 1);
    expect(
        (await sync.synchronize(b, 'secret',
                now: time.add(const Duration(seconds: 121))))
            .received,
        2);
    limited.close();
    corrected.close();
  });

  for (final status in [404, 409, 422]) {
    test('HTTP $status retains rejected evidence without resubmission',
        () async {
      final b = binding();
      await queue.captureSimulation(b, '00001234');
      final client = MockClient(
          (_) async => http.Response('sensitive server text', status));
      expect(
          (await DeviceSync(queue, client).synchronize(b, 'secret', now: time))
              .rejected,
          1);
      expect((await queue.counts(b))['rejected'], 1);
      expect((await queue.recent(b)).single['error'],
          'Server rejected evidence (HTTP $status).');
      expect(
          await queue.due(
              b, time.add(const Duration(days: 1)).millisecondsSinceEpoch),
          isEmpty);
      client.close();
    });
  }

  for (final body in [
    '{}',
    '<html>oops</html>',
    jsonEncode({
      'event_id': event,
      'status': 'pending',
      'official_result_created': true
    }),
    jsonEncode({
      'event_id': 'not-a-uuid',
      'status': 'pending',
      'official_result_created': false
    })
  ]) {
    test('malformed or official acknowledgement remains pending: $body',
        () async {
      final b = binding();
      await queue.captureSimulation(b, '00001234');
      final client = MockClient((_) async => http.Response(body, 202));
      expect(
          (await DeviceSync(queue, client).synchronize(b, 'secret', now: time))
              .retry,
          1);
      expect((await queue.counts(b))['pending'], 1);
      client.close();
    });
  }

  test('oversized acknowledgement is retained for retry', () async {
    await queue.captureSimulation(binding(), '00001234');
    final client = MockClient((_) async => http.Response('x' * 65537, 202));
    expect(
        (await DeviceSync(queue, client)
                .synchronize(binding(), 'secret', now: time))
            .retry,
        1);
    expect((await queue.counts(binding()))['pending'], 1);
    client.close();
  });

  test('redirect never forwards credentials or acknowledges evidence',
      () async {
    await queue.captureSimulation(binding(), '00001234');
    final client = MockClient((request) async {
      expect(request.followRedirects, false);
      return http.Response('', 302,
          headers: {'location': 'https://other.example'});
    });
    expect(
        (await DeviceSync(queue, client)
                .synchronize(binding(), 'secret', now: time))
            .retry,
        1);
    expect((await queue.counts(binding()))['pending'], 1);
    client.close();
  });

  test('parallel synchronization is blocked and stop prevents remaining sends',
      () async {
    final b = binding();
    await queue.captureSimulation(b, '00001234');
    await queue.captureSimulation(b, '00005678');
    final entered = Completer<void>(), release = Completer<void>();
    var stopped = false, calls = 0;
    final client = MockClient((_) async {
      calls++;
      entered.complete();
      await release.future;
      stopped = true;
      return ack();
    });
    final sync = DeviceSync(queue, client);
    final pending =
        sync.synchronize(b, 'secret', now: time, shouldStop: () => stopped);
    await entered.future;
    await expectLater(
        sync.synchronize(b, 'secret', now: time), throwsStateError);
    release.complete();
    final result = await pending;
    expect(result.cancelled, true);
    expect(calls, 1);
    expect((await queue.counts(b))['pending'], 1);
    client.close();
  });

  test('invalid origins and credentials are rejected before any request',
      () async {
    for (final url in [
      'http://example.com',
      'https://a:b@example.com',
      'https://example.com/api',
      'https://example.com?token=x',
      'ftp://localhost'
    ]) {
      expect(() => binding(origin: url), throwsFormatException);
    }
    final client = MockClient((_) async => throw StateError('Must not send'));
    final sync = DeviceSync(queue, client);
    for (final value in ['', 'a\nb', 'non-ascii-ñ', 'a' * 257]) {
      await expectLater(
          sync.synchronize(binding(), value), throwsFormatException);
    }
    client.close();
  });

  test('empty, oversized and control-filled scans cannot enter the queue',
      () async {
    for (final value in ['', ' ', 'a' * 201, '0000\n1234']) {
      await expectLater(
          queue.captureSimulation(binding(), value), throwsFormatException);
    }
    expect(await queue.counts(binding()), isEmpty);
  });
}
