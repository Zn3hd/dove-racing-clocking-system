import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:dove_racing_mobile/rfid/keyboard_capture.dart';

void main() {
  test('rapid keyboard frames commit in order and drain after stopping input',
      () async {
    final release = Completer<void>();
    final values = <String>[];
    final capture = KeyboardCapture((raw) async {
      if (values.isEmpty) await release.future;
      values.add(raw);
      return raw;
    });
    final a = capture.capture('00001'),
        b = capture.capture('00002'),
        c = capture.capture('00003');
    expect(capture.pending, 3);
    capture.stop();
    await expectLater(capture.capture('00004'), throwsStateError);
    release.complete();
    expect(await Future.wait([a, b, c]), ['00001', '00002', '00003']);
    await capture.drained;
    expect(values, ['00001', '00002', '00003']);
    expect(capture.pending, 0);
  });

  test(
      'buffer exhaustion visibly refuses a frame and preserves accepted frames',
      () async {
    final release = Completer<void>();
    final values = <String>[];
    final capture = KeyboardCapture((raw) async {
      await release.future;
      values.add(raw);
      return raw;
    }, capacity: 2);
    final a = capture.capture('a'), b = capture.capture('b');
    await expectLater(capture.capture('overflow'), throwsStateError);
    release.complete();
    await Future.wait([a, b]);
    expect(values, ['a', 'b']);
    expect(capture.stopped, true);
  });

  test(
      'storage failure latches stop while malformed frame does not poison input',
      () async {
    var failures = 0;
    final capture = KeyboardCapture((raw) async {
      if (raw == 'invalid') throw const FormatException('Invalid frame');
      if (raw == 'disk-full') {
        failures++;
        throw StateError('No storage');
      }
      return raw;
    });
    await expectLater(capture.capture('invalid'), throwsFormatException);
    expect(await capture.capture('valid'), 'valid');
    await expectLater(capture.capture('disk-full'), throwsStateError);
    await expectLater(capture.capture('later'), throwsStateError);
    expect(failures, 1);
  });
}
