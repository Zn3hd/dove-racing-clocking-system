import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:dove_racing_mobile/api.dart';

void main() {
  test('participant registration sends club scoped POST', () async {
    final api = RacingApi(MockClient((request) async {
      expect(request.method, 'POST');
      expect(request.url.path, '/participants');
      expect(request.headers['Authorization'], 'Bearer test-token');
      final body = jsonDecode(request.body) as Map<String, dynamic>;
      expect(body['club_id'], 'club-1');
      expect(body['role'], 'member');
      return http.Response(jsonEncode({'id': 'participant-1'}), 201);
    }));
    final result = await api.createParticipant('test-token', {
      'club_id': 'club-1', 'role': 'member', 'full_name': 'Test Member',
      'email': 'test@example.com', 'password': 'secure-password',
    });
    expect(result['id'], 'participant-1');
  });

  test('pigeon registration sends verified loft ID', () async {
    final api = RacingApi(MockClient((request) async {
      expect(request.url.path, '/pigeons');
      expect(jsonDecode(request.body)['loft_id'], 'loft-1');
      return http.Response(jsonEncode({'id': 'pigeon-1'}), 201);
    }));
    expect((await api.createPigeon('token', {
      'loft_id': 'loft-1', 'official_ring_number': 'PH-001',
    }))['id'], 'pigeon-1');
  });

  test('race creation sends draft settings', () async {
    final api = RacingApi(MockClient((request) async {
      expect(request.url.path, '/races');
      final body = jsonDecode(request.body) as Map<String, dynamic>;
      expect(body['minimum_speed_mpm'], 500);
      expect(body['guest_ranking_mode'], 'separate');
      return http.Response(jsonEncode({'status': 'draft'}), 201);
    }));
    expect((await api.createRace('token', {
      'club_id': 'club-1', 'name': 'Test race',
      'minimum_speed_mpm': 500, 'guest_ranking_mode': 'separate',
    }))['status'], 'draft');
  });

  test('loft listing includes club filter', () async {
    final api = RacingApi(MockClient((request) async {
      expect(request.url.queryParameters['club_id'], 'club-1');
      return http.Response(jsonEncode([{'id': 'loft-1', 'verified_at': '2026-01-01'}]), 200);
    }));
    expect((await api.lofts('token', 'club-1')).length, 1);
  });
}
