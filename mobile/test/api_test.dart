import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:dove_racing_mobile/api.dart';

void main() {
  test('login posts JSON credentials and parses bearer token', () async {
    final api = RacingApi(MockClient((request) async {
      expect(request.method, 'POST');
      expect(request.url.path, '/auth/login');
      expect(request.headers['Content-Type'], 'application/json');
      expect(jsonDecode(request.body), {
        'email': 'admin@example.com', 'password': 'test-password',
      });
      return http.Response(jsonEncode({
        'access_token': 'fake-token', 'token_type': 'bearer', 'expires_in': 1800,
      }), 200);
    }));
    final result = await api.login(' admin@example.com ', 'test-password');
    expect(result['access_token'], 'fake-token');
  });

  test('me sends bearer authorization header', () async {
    final api = RacingApi(MockClient((request) async {
      expect(request.url.path, '/auth/me');
      expect(request.headers['Authorization'], 'Bearer fake-token');
      return http.Response(jsonEncode({'id': '1', 'role': 'admin'}), 200);
    }));
    expect((await api.me('fake-token'))['role'], 'admin');
  });

  test('clubs parses array of club objects', () async {
    final api = RacingApi(MockClient((request) async {
      expect(request.url.path, '/clubs');
      return http.Response(jsonEncode([{'id': '1', 'name': 'Dove Club'}]), 200);
    }));
    expect((await api.clubs('fake-token')).single['name'], 'Dove Club');
  });

  test('401 errors do not expose response credentials', () async {
    final api = RacingApi(MockClient((_) async =>
        http.Response(jsonEncode({'detail': 'sensitive backend detail'}), 401)));
    await expectLater(api.me('bad-token'), throwsA(
      isA<ApiException>().having((e) => e.status, 'status', 401)
          .having((e) => e.message, 'message', isNot(contains('sensitive'))),
    ));
  });

  test('malformed success payload returns API exception', () async {
    final api = RacingApi(MockClient((_) async => http.Response('<html>', 200)));
    await expectLater(api.me('token'), throwsA(isA<ApiException>()));
  });

  test('network failure maps to safe error', () async {
    final api = RacingApi(MockClient((_) async => throw Exception('private info')));
    await expectLater(api.me('token'), throwsA(
      isA<ApiException>().having((e) => e.message, 'message',
          isNot(contains('private info'))),
    ));
  });
}
