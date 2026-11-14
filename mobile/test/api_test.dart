import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:dove_racing_mobile/api.dart';

void main() {
  test('credentials are never sent to an absolute or foreign request path', () async {
    var calls = 0;
    final api = RacingApi(MockClient((_) async { calls++; return http.Response('{}', 200); }));
    for (final path in ['https://other.example/auth/me', '//other.example/auth/me',
        'auth/me', '/auth/me#secret']) {
      await expectLater(api.request(path, token: 'private-token'), throwsA(isA<ApiException>()));
    }
    expect(calls, 0);
  });

  test('invalid API origins are rejected before sending credentials', () async {
    var calls = 0;
    final client = MockClient((_) async { calls++; return http.Response('{}', 200); });
    for (final origin in ['http://example.com', 'ftp://localhost',
        'https://user:password@example.com', 'https://example.com/api',
        'https://example.com?secret=value', 'https://example.com#fragment', 'not a URL']) {
      final api = RacingApi(client, baseUrl: origin);
      await expectLater(api.me('private-token'), throwsA(isA<ApiException>()));
    }
    expect(calls, 0);
  });

  test('redirects are disabled and HTML redirects produce a safe error', () async {
    final api = RacingApi(MockClient((request) async {
      expect(request.followRedirects, isFalse);
      return http.Response('<html>private data</html>', 302,
          headers: {'location': 'https://other.example'});
    }));
    await expectLater(api.me('private-token'), throwsA(isA<ApiException>()
        .having((e) => e.status, 'status', 302)
        .having((e) => e.message, 'message', isNot(contains('private data')))));
  });

  test('explicit loopback HTTP and normal query paths are supported', () async {
    final api = RacingApi(MockClient((request) async {
      expect(request.url.origin, 'http://127.0.0.1:8000');
      expect(request.url.queryParameters['club_id'], 'test-club');
      return http.Response('[]', 200);
    }), baseUrl: 'http://127.0.0.1:8000/');
    expect(await api.participants('token', 'test-club'), isEmpty);
  });

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
