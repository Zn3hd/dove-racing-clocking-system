import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:dove_racing_mobile/api.dart';
import 'package:dove_racing_mobile/main.dart';

void main() {
  test('chairman and president can manage clubs, members cannot', () {
    expect(canManageClub('chairman'), isTrue);
    expect(canManageClub('president'), isTrue);
    expect(canManageClub('member'), isFalse);
    expect(canManageClub('guest'), isFalse);
    expect(canManageClub(null), isFalse);
  });

  test('club listing requests include club scope and bearer token', () async {
    final paths = <String>[];
    final api = RacingApi(MockClient((request) async {
      paths.add(request.url.toString());
      expect(request.headers['Authorization'], 'Bearer test-token');
      return http.Response(jsonEncode([]), 200);
    }));
    await api.participants('test-token', 'club-123');
    await api.pigeons('test-token', 'club-123');
    await api.races('test-token');
    expect(paths[0], contains('/participants?club_id=club-123'));
    expect(paths[1], contains('/pigeons?club_id=club-123'));
    expect(paths[2], endsWith('/races'));
  });
}
