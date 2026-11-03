import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:dove_racing_mobile/api.dart';
import 'package:dove_racing_mobile/session.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  FlutterSecureStorage.setMockInitialValues({});

  final api = RacingApi(MockClient((request) async =>
      http.Response(jsonEncode({
        'access_token': 'mock-jwt', 'token_type': 'bearer', 'expires_in': 1800,
      }), 200)));

  setUp(() async {
    FlutterSecureStorage.setMockInitialValues({});
    await Session(api).logout();
  });

  test('login stores token and logout clears it', () async {
    final session = Session(api);
    await session.login('admin@example.com', 'password');
    expect(await session.token(), 'mock-jwt');
    await session.logout();
    expect(await session.token(), isNull);
  });

  test('expired session is cleared', () async {
    const storage = FlutterSecureStorage();
    await storage.write(key: 'access_token', value: 'expired');
    await storage.write(key: 'expires_at', value: '1');
    expect(await Session(api).token(), isNull);
    expect(await storage.read(key: 'access_token'), isNull);
  });

  test('invalid login payload is rejected', () async {
    final invalidApi = RacingApi(MockClient((_) async =>
        http.Response(jsonEncode({'access_token': '', 'expires_in': 0}), 200)));
    await expectLater(Session(invalidApi).login('a', 'b'),
        throwsA(isA<ApiException>()));
    expect(await Session(invalidApi).token(), isNull);
  });
}
