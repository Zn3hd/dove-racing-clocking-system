import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'api.dart';

class Session {
  static const _storage = FlutterSecureStorage();
  static const _tokenKey = 'access_token';
  static const _expiresKey = 'expires_at';
  final RacingApi api;
  Session(this.api);

  Future<String?> token() async {
    final value = await _storage.read(key: _tokenKey);
    final expires = await _storage.read(key: _expiresKey);
    final expiry = int.tryParse(expires ?? '');
    if (value == null || expiry == null ||
        DateTime.now().toUtc().millisecondsSinceEpoch >= expiry) {
      await logout();
      return null;
    }
    return value;
  }

  Future<void> login(String email, String password) async {
    final result = await api.login(email, password);
    final token = result['access_token'];
    final seconds = result['expires_in'];
    if (token is! String || token.isEmpty || seconds is! int || seconds <= 0) {
      throw ApiException('Login returned an invalid session.');
    }
    final expiry = DateTime.now().toUtc()
        .add(Duration(seconds: seconds > 30 ? seconds - 30 : seconds))
        .millisecondsSinceEpoch;
    await _storage.write(key: _tokenKey, value: token);
    await _storage.write(key: _expiresKey, value: expiry.toString());
  }

  Future<void> logout() async {
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _expiresKey);
  }
}
