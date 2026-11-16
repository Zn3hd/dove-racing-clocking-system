import 'dart:convert';
import 'dart:math';
import 'package:sqflite/sqflite.dart';

bool isUuid(String value) => RegExp(
      r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
    ).hasMatch(value);

String newMessageId() {
  final random = Random.secure();
  final bytes = List.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-'
      '${hex.substring(16, 20)}-${hex.substring(20)}';
}

/// Immutable routing identity. Credentials never form part of a queued record.
class ReaderBinding {
  final String ownerId, origin, deviceId, raceId;
  ReaderBinding(
      {required String ownerId,
      required String origin,
      required String deviceId,
      required String raceId,
      bool allowLocalHttp = false})
      : ownerId = ownerId.toLowerCase(),
        deviceId = deviceId.toLowerCase(),
        raceId = raceId.toLowerCase(),
        origin = _origin(origin, allowLocalHttp) {
    if (![this.ownerId, this.deviceId, this.raceId].every(isUuid)) {
      throw const FormatException(
          'Account, reader and race IDs must be UUIDs.');
    }
  }
  static String _origin(String value, bool local) {
    final uri = Uri.tryParse(value);
    if (uri == null ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment ||
        (uri.path.isNotEmpty && uri.path != '/') ||
        (uri.scheme != 'https' &&
            !(local &&
                uri.scheme == 'http' &&
                ['localhost', '127.0.0.1'].contains(uri.host)))) {
      throw const FormatException(
          'Use an HTTPS server origin without credentials or a path.');
    }
    return uri.origin;
  }

  String get key => jsonEncode([ownerId, origin, deviceId, raceId]);
  String get credentialKey =>
      'rfid-device:${jsonEncode([ownerId, origin, deviceId])}';
}

abstract interface class ReaderAdapter {
  String get adapterType;
  String get protocol;
  String get captureMode;
  String normalize(String raw);
}

/// Deliberately cannot declare an operator or automatic hardware capture.
class SimulatorAdapter implements ReaderAdapter {
  const SimulatorAdapter();
  @override
  String get adapterType => 'simulator';
  @override
  String get protocol => 'mobile-simulator-v1';
  @override
  String get captureMode => 'simulated';
  @override
  String normalize(String raw) {
    final value = raw.trim();
    if (raw.length > 1024 ||
        value.isEmpty ||
        value.length > 200 ||
        value.codeUnits.any((c) => c < 32 || c == 127)) {
      throw const FormatException(
          'Enter a printable ring ID of 1–200 characters.');
    }
    return value; // Never convert decimal/hex or discard leading zeros.
  }
}

class QueuedEvent {
  final String messageId, payload;
  final int attempts;
  QueuedEvent(Map<String, Object?> row)
      : messageId = row['message_id'] as String,
        payload = row['payload'] as String,
        attempts = row['attempts'] as int;
}

/// Focused keyboard-style input is operator evidence, never automatic capture.
class KeyboardAdapter implements ReaderAdapter {
  const KeyboardAdapter();
  @override
  String get adapterType => 'usb_hid';
  @override
  String get protocol => 'ascii-newline-v1';
  @override
  String get captureMode => 'operator';
  @override
  String normalize(String raw) => const SimulatorAdapter().normalize(raw);
}

class EvidenceExport {
  final String scope;
  final List<Map<String, Object?>> records;
  EvidenceExport._(this.scope, List<Map<String, Object?>> rows)
      : records = List.unmodifiable(
            rows.map((row) => Map<String, Object?>.unmodifiable(row)));
  String get json => jsonEncode({
        'format': 'pigeon-evidence-v1',
        'scope': jsonDecode(scope),
        'records': records
      });
  int get receivedCount =>
      records.where((row) => row['state'] == 'received').length;
}

class RfidQueue {
  final Database _db;
  final int capacity;
  RfidQueue._(this._db, this.capacity);

  static Future<RfidQueue> open(
      {String? path, DatabaseFactory? factory, int capacity = 10000}) async {
    if (capacity < 1) throw ArgumentError('Queue capacity must be positive.');
    final driver = factory ?? databaseFactory;
    final location =
        path ?? '${await driver.getDatabasesPath()}/pigeon-rfid-v1.db';
    final db = await driver.openDatabase(location,
        options: OpenDatabaseOptions(
          version: 1,
          singleInstance: false,
          onConfigure: (db) async {
            await db.rawQuery('PRAGMA journal_mode=WAL');
            await db.execute('PRAGMA synchronous=FULL');
          },
          onCreate: (db, _) async {
            await db.execute('''CREATE TABLE events (
          message_id TEXT PRIMARY KEY, scope TEXT NOT NULL, payload TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','received','rejected')),
          attempts INTEGER NOT NULL DEFAULT 0, next_at INTEGER NOT NULL DEFAULT 0,
          error TEXT, event_id TEXT)''');
            await db.execute(
                'CREATE INDEX due_events ON events(scope,state,next_at)');
            await db.execute('''CREATE TABLE pauses (
          scope TEXT PRIMARY KEY, until_at INTEGER NOT NULL, auth INTEGER NOT NULL)''');
            await db
                .execute('''CREATE TRIGGER immutable_envelope BEFORE UPDATE OF
          message_id,scope,payload ON events BEGIN
          SELECT RAISE(ABORT,'Clocking envelope is immutable'); END''');
          },
        ));
    return RfidQueue._(db, capacity);
  }

  Future<String> captureSimulation(ReaderBinding binding, String raw,
      {DateTime? observedAt}) async {
    return _capture(binding, raw, const SimulatorAdapter(),
        observedAt: observedAt);
  }

  Future<String> captureKeyboard(ReaderBinding binding, String raw,
          {DateTime? observedAt}) =>
      _capture(binding, raw, const KeyboardAdapter(), observedAt: observedAt);

  Future<String> _capture(
      ReaderBinding binding, String raw, ReaderAdapter adapter,
      {DateTime? observedAt}) async {
    final uid = adapter.normalize(raw);
    final id = newMessageId();
    final payload = jsonEncode({
      'message_id': id,
      'race_id': binding.raceId,
      'ring_uid': uid,
      'offline_buffered': true,
      'device_recorded_at':
          (observedAt ?? DateTime.now()).toUtc().toIso8601String(),
      'adapter_type': adapter.adapterType,
      'protocol': adapter.protocol,
      'capture_mode': adapter.captureMode,
      'original_scan': raw,
    });
    await _db.transaction((txn) async {
      final count = Sqflite.firstIntValue(
          await txn.rawQuery('SELECT count(*) FROM events'))!;
      if (count >= capacity) {
        throw StateError('Queue storage limit reached. Capture stopped.');
      }
      await txn.insert('events',
          {'message_id': id, 'scope': binding.key, 'payload': payload});
    });
    return id; // Only returned after the database commit.
  }

  Future<Map<String, int>> counts(ReaderBinding binding) async {
    final rows = await _db.rawQuery(
        'SELECT state,count(*) AS n FROM events WHERE scope=? GROUP BY state',
        [binding.key]);
    return {for (final row in rows) row['state'] as String: row['n'] as int};
  }

  /// Bounded, scoped snapshot. The caller must save it before confirming pruning.
  Future<EvidenceExport> exportEvidence(ReaderBinding binding) async =>
      EvidenceExport._(
          binding.key,
          await _db.query('events',
              where: 'scope=?',
              whereArgs: [binding.key],
              orderBy: "CASE WHEN state='received' THEN 0 ELSE 1 END,rowid",
              limit: 500));

  Future<int> pruneReceived(ReaderBinding binding, EvidenceExport exported,
      {required bool backupConfirmed}) async {
    if (!backupConfirmed || exported.scope != binding.key) {
      throw StateError(
          'Confirm a saved export for this exact queue before pruning.');
    }
    return _db.transaction((txn) async {
      var deleted = 0;
      for (final row
          in exported.records.where((r) => r['state'] == 'received')) {
        deleted += await txn.delete('events',
            where:
                'scope=? AND message_id=? AND state=? AND event_id=? AND payload=?',
            whereArgs: [
              binding.key,
              row['message_id'],
              'received',
              row['event_id'],
              row['payload']
            ]);
      }
      return deleted;
    });
  }

  Future<List<Map<String, Object?>>> recent(ReaderBinding binding) =>
      _db.query('events',
          columns: ['message_id', 'state', 'error', 'event_id'],
          where: 'scope=?',
          whereArgs: [binding.key],
          orderBy: 'rowid DESC',
          limit: 20);

  Future<bool> paused(ReaderBinding binding, int now) async {
    final rows =
        await _db.query('pauses', where: 'scope=?', whereArgs: [binding.key]);
    return rows.isNotEmpty &&
        (rows.first['auth'] == 1 || (rows.first['until_at'] as int) > now);
  }

  Future<void> pause(ReaderBinding binding, int until, {bool auth = false}) =>
      _db
          .insert('pauses',
              {'scope': binding.key, 'until_at': until, 'auth': auth ? 1 : 0},
              conflictAlgorithm: ConflictAlgorithm.replace)
          .then((_) {});

  Future<void> resumeAuthorization(ReaderBinding binding) async {
    await _db.transaction((txn) async {
      final paused = await txn.query('pauses',
          where: 'scope=? AND auth=1', whereArgs: [binding.key]);
      if (paused.isEmpty) {
        return; // Never bypass a persisted rate-limit deadline.
      }
      await txn.delete('pauses', where: 'scope=?', whereArgs: [binding.key]);
      await txn.update('events', {'next_at': 0},
          where: 'scope=? AND state=?', whereArgs: [binding.key, 'pending']);
    });
  }

  Future<List<QueuedEvent>> due(ReaderBinding binding, int now) async {
    if (await paused(binding, now)) return [];
    return (await _db.query('events',
            where: 'scope=? AND state=? AND next_at<=?',
            whereArgs: [binding.key, 'pending', now],
            orderBy: 'rowid',
            limit: 100))
        .map(QueuedEvent.new)
        .toList();
  }

  Future<void> acknowledge(QueuedEvent row, String eventId) =>
      _update(row, {'state': 'received', 'event_id': eventId, 'error': null});
  Future<void> reject(QueuedEvent row, int status) => _update(row, {
        'state': 'rejected',
        'error': 'Server rejected evidence (HTTP $status).'
      });
  Future<void> retry(QueuedEvent row, int now, String reason) => _update(row, {
        'attempts': row.attempts + 1,
        'next_at': now + min(300, 5 * (1 << min(row.attempts, 6))) * 1000,
        'error': reason,
      });
  Future<void> _update(QueuedEvent row, Map<String, Object?> values) =>
      _db.update('events', values,
          where: 'message_id=? AND state=?',
          whereArgs: [row.messageId, 'pending']).then((_) {});
  Future<void> close() => _db.close();
}
