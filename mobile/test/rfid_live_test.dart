// Opt-in: real Flutter queue -> local FastAPI -> disposable PostgreSQL.
import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:dove_racing_mobile/rfid/queue.dart';
import 'package:dove_racing_mobile/rfid/sync.dart';

class LoseFirstAck extends http.BaseClient {
  final http.Client inner;
  bool lost = false;
  LoseFirstAck(this.inner);
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final response = await inner.send(request);
    if (!lost && response.statusCode == 202) {
      lost = true;
      await response.stream.drain<void>();
      throw http.ClientException(
          'Synthetic lost acknowledgement after real commit');
    }
    return response;
  }

  @override
  void close() => inner.close();
}

void main() {
  final env = Platform.environment;
  test(
      'mobile simulator replays one real server event after lost acknowledgement',
      () async {
    final origin = Uri.parse(env['MOBILE_RFID_TEST_ORIGIN']!);
    if (origin.scheme != 'http' ||
        origin.host != '127.0.0.1' ||
        origin.path.isNotEmpty ||
        origin.hasQuery ||
        origin.hasFragment) {
      fail('Refusing a non-loopback test backend');
    }
    sqfliteFfiInit();
    final directory =
        await Directory.systemTemp.createTemp('pigeon-mobile-live-');
    final path = '${directory.path}/queue.db';
    var queue = await RfidQueue.open(path: path, factory: databaseFactoryFfi);
    final transport =
        LoseFirstAck(IOClient(HttpClient()..findProxy = (_) => 'DIRECT'));
    final b = ReaderBinding(
        ownerId: env['MOBILE_RFID_TEST_OWNER']!,
        origin: origin.origin,
        deviceId: env['MOBILE_RFID_TEST_DEVICE']!,
        raceId: env['MOBILE_RFID_TEST_RACE']!,
        allowLocalHttp: true);
    try {
      final mode = env['MOBILE_RFID_TEST_MODE'] ?? 'simulated';
      if (mode == 'operator') {
        await queue.captureKeyboard(b, '000012340056');
      } else {
        await queue.captureSimulation(b, '000012340056');
      }
      final now = DateTime.now();
      final before =
          (await queue.due(b, now.millisecondsSinceEpoch)).single.payload;
      final token = env['MOBILE_RFID_TEST_TOKEN']!;
      expect(
          (await DeviceSync(queue, transport).synchronize(b, token, now: now))
              .retry,
          1);
      await queue.close();
      queue = await RfidQueue.open(path: path, factory: databaseFactoryFfi);
      final later = now.add(const Duration(seconds: 10));
      expect((await queue.due(b, later.millisecondsSinceEpoch)).single.payload,
          before);
      expect(
          (await DeviceSync(queue, transport).synchronize(b, token, now: later))
              .received,
          1);
      expect((await queue.counts(b))['received'], 1);
      expect(jsonDecode(before)['capture_mode'], mode);
      expect((await queue.recent(b)).single['event_id'], isNotNull);
      expect(
          await DeviceSync(queue, transport).heartbeat(b, token), 'received');
    } finally {
      transport.close();
      await queue.close();
      await directory.delete(recursive: true);
    }
  },
      skip: env['MOBILE_RFID_TEST_ORIGIN'] == null
          ? 'Requires disposable backend harness'
          : false);
}
