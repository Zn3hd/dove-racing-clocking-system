import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'queue.dart';

void validateDeviceToken(String value) {
  if (value.isEmpty ||
      value.length > 256 ||
      value.codeUnits.any((c) => c < 33 || c > 126)) {
    throw const FormatException(
        'Enter the separately provisioned device credential.');
  }
}

class SyncResult {
  int received = 0, retry = 0, rejected = 0;
  bool paused = false, cancelled = false;
  @override
  String toString() => '$received received; $retry retrying; $rejected rejected'
      '${paused ? '; synchronization paused' : ''}${cancelled ? '; stopped' : ''}';
}

/// One worker per queue session; account JWTs are never sent to these endpoints.
class DeviceSync {
  final RfidQueue queue;
  final http.Client client;
  final Duration timeout;
  bool _busy = false;
  DeviceSync(this.queue, this.client,
      {this.timeout = const Duration(seconds: 15)});

  static Future<http.Response> _boundedResponse(
      http.StreamedResponse response) async {
    final bytes = <int>[];
    await for (final chunk in response.stream) {
      if (bytes.length + chunk.length > 65536) {
        throw const FormatException('Oversized acknowledgement');
      }
      bytes.addAll(chunk);
    }
    return http.Response.bytes(bytes, response.statusCode,
        headers: response.headers);
  }

  Future<String> heartbeat(ReaderBinding binding, String token,
      {String readerState = 'not_probed'}) async {
    validateDeviceToken(token);
    if (!['not_probed', 'waiting', 'error'].contains(readerState)) {
      throw const FormatException('Invalid reader state');
    }
    final now = DateTime.now().millisecondsSinceEpoch;
    if (await queue.paused(binding, now)) return 'paused';
    final counts = await queue.counts(binding);
    try {
      final request = http.Request('POST',
          Uri.parse('${binding.origin}/devices/${binding.deviceId}/heartbeat'))
        ..followRedirects = false
        ..headers.addAll(
            {'Content-Type': 'application/json', 'X-Device-Token': token})
        ..body = jsonEncode({
          'reader_state': readerState,
          'pending_count': counts['pending'] ?? 0,
          'rejected_count': counts['rejected'] ?? 0
        });
      final response =
          await client.send(request).then(_boundedResponse).timeout(timeout);
      if ([401, 403].contains(response.statusCode)) {
        await queue.pause(binding, now, auth: true);
        return 'authorization blocked';
      }
      if (response.statusCode == 429) {
        final delay =
            (int.tryParse(response.headers['retry-after'] ?? '') ?? 60)
                .clamp(1, 3600);
        await queue.pause(binding, now + delay * 1000);
        return 'rate limited';
      }
      if (response.statusCode != 200) return 'unconfirmed';
      final data = jsonDecode(response.body);
      if (data is! Map ||
          data['device_id'] != binding.deviceId ||
          data['received_at'] is! String ||
          DateTime.tryParse(data['received_at']) == null ||
          data['official_result_created'] != false) {
        return 'unconfirmed';
      }
      return 'received';
    } catch (_) {
      return 'unconfirmed';
    }
  }

  Future<SyncResult> synchronize(ReaderBinding binding, String token,
      {DateTime? now, bool Function()? shouldStop}) async {
    validateDeviceToken(token);
    if (_busy) throw StateError('Synchronization is already running.');
    _busy = true;
    final result = SyncResult();
    final clock = (now ?? DateTime.now()).millisecondsSinceEpoch;
    try {
      if (await queue.paused(binding, clock)) {
        result.paused = true;
        return result;
      }
      for (final row in await queue.due(binding, clock)) {
        if (shouldStop?.call() ?? false) {
          result.cancelled = true;
          break;
        }
        http.Response response;
        try {
          final request = http.Request(
              'POST',
              Uri.parse(
                  '${binding.origin}/devices/${binding.deviceId}/arrivals'))
            ..followRedirects = false
            ..headers.addAll(
                {'Content-Type': 'application/json', 'X-Device-Token': token})
            ..body = row.payload;
          response = await client
              .send(request)
              .then(_boundedResponse)
              .timeout(timeout);
        } catch (_) {
          await queue.retry(row, clock, 'Network or TLS failure.');
          result.retry++;
          continue;
        }
        if ([401, 403].contains(response.statusCode)) {
          await queue.retry(row, clock, 'Device authorization blocked.');
          await queue.pause(binding, clock, auth: true);
          result.paused = true;
          break;
        }
        if (response.statusCode == 429) {
          final seconds =
              (int.tryParse(response.headers['retry-after'] ?? '') ?? 60)
                  .clamp(1, 3600);
          await queue.retry(row, clock, 'Rate limited.');
          await queue.pause(binding, clock + seconds * 1000);
          result.paused = true;
          result.retry++;
          break;
        }
        if (response.statusCode == 202) {
          String? eventId;
          try {
            if (response.bodyBytes.length > 65536) {
              throw const FormatException();
            }
            final data = jsonDecode(response.body);
            if (data is! Map ||
                data['status'] != 'pending' ||
                data['official_result_created'] != false ||
                data['event_id'] is! String ||
                !isUuid(data['event_id'] as String)) {
              throw const FormatException();
            }
            eventId = data['event_id'] as String;
          } catch (_) {
            await queue.retry(row, clock, 'Invalid server acknowledgement.');
            result.retry++;
          }
          if (eventId != null) {
            await queue.acknowledge(row, eventId);
            result.received++;
          }
        } else if ([404, 409, 422].contains(response.statusCode)) {
          await queue.reject(row, response.statusCode);
          result.rejected++;
        } else {
          await queue.retry(row, clock,
              'Delivery unavailable (HTTP ${response.statusCode}).');
          result.retry++;
        }
      }
      return result;
    } finally {
      _busy = false;
    }
  }
}
