import 'dart:async';

/// Serializes complete keyboard frames so a second Enter cannot overwrite a
/// scan still being committed. Accepted frames drain before closing storage.
class KeyboardCapture {
  final Future<String> Function(String) persist;
  final int capacity;
  Future<void> _tail = Future.value();
  int pending = 0;
  bool stopped = false;
  KeyboardCapture(this.persist, {this.capacity = 100});

  Future<String> capture(String raw) {
    if (stopped || pending >= capacity) {
      stopped = true;
      return Future.error(
          StateError('Keyboard capture stopped; a frame could not be saved.'));
    }
    final reply = Completer<String>();
    final previous = _tail;
    pending++;
    _tail = () async {
      await previous;
      try {
        reply.complete(await persist(raw));
      } catch (error, stack) {
        if (error is! FormatException) stopped = true;
        reply.completeError(error, stack);
      } finally {
        pending--;
      }
    }();
    return reply.future;
  }

  void stop() {
    stopped = true;
  }

  Future<void> get drained => _tail;
}
