import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:dove_racing_mobile/preview_client.dart';

void main() {
  final base = Uri.parse('https://example.invalid');
  test('demo chairman and club load locally', () async {
    final client = previewClient();
    final me = await client.get(base.resolve('/auth/me'));
    final clubs = await client.get(base.resolve('/clubs'));
    expect(jsonDecode(me.body)['role'], 'chairman');
    expect((jsonDecode(clubs.body) as List).single['name'], 'Dove Racing Demo Club');
    client.close();
  });

  test('register participant, see it in club, reject duplicate', () async {
    final client = previewClient();
    final body = jsonEncode({
      'club_id': demoClubId, 'full_name': 'Test Participant',
      'email': 'test@example.invalid', 'password': 'demo-password-123',
      'role': 'member',
    });
    final first = await client.post(base.resolve('/participants'), body: body);
    expect(first.statusCode, 201);
    expect(jsonDecode(first.body).containsKey('password'), false);
    final duplicate = await client.post(base.resolve('/participants'), body: body);
    expect(duplicate.statusCode, 409);
    final list = await client.get(base.resolve('/participants?club_id=$demoClubId'));
    expect((jsonDecode(list.body) as List).length, 2);
    client.close();
  });

  test('register pigeon with verified loft and reject duplicate ring', () async {
    final client = previewClient();
    final lofts = await client.get(base.resolve('/lofts?club_id=$demoClubId'));
    expect((jsonDecode(lofts.body) as List).single['verified_at'], isNotNull);
    final body = jsonEncode({
      'loft_id': 'demo-loft', 'official_ring_number': 'DEMO-2026-002',
      'name': 'New Pigeon',
    });
    expect((await client.post(base.resolve('/pigeons'), body: body)).statusCode, 201);
    expect((await client.post(base.resolve('/pigeons'), body: body)).statusCode, 409);
    final list = await client.get(base.resolve('/pigeons?club_id=$demoClubId'));
    expect((jsonDecode(list.body) as List).length, 2);
    client.close();
  });

  test('create draft race; reject invalid speed and coordinates', () async {
    final client = previewClient();
    final race = {
      'club_id': demoClubId, 'name': 'New Demo Race',
      'release_latitude': 14.5, 'release_longitude': 121.0,
      'minimum_speed_mpm': 500, 'maximum_speed_mpm': 3000,
      'display_speed_unit': 'm/min', 'guest_ranking_mode': 'separate',
    };
    final created = await client.post(base.resolve('/races'), body: jsonEncode(race));
    expect(created.statusCode, 201);
    expect(jsonDecode(created.body)['status'], 'draft');
    final invalid = await client.post(base.resolve('/races'),
        body: jsonEncode({...race, 'release_latitude': 100}));
    expect(invalid.statusCode, 400);
    final list = await client.get(base.resolve('/races'));
    expect((jsonDecode(list.body) as List).length, 2);
    client.close();
  });

  test('sandbox never reaches network or accepts unknown writes', () async {
    final client = previewClient();
    expect((await client.post(base.resolve('/clocking'), body: '{}')).statusCode, 403);
    expect((await client.delete(base.resolve('/races/demo-race'))).statusCode, 403);
    expect((await client.get(base.resolve('/clocking'))).statusCode, 404);
    client.close();
  });

  test('sandbox data resets when new preview client is created', () async {
    final first = previewClient();
    await first.post(base.resolve('/participants'), body: jsonEncode({
      'club_id': demoClubId, 'full_name': 'Temporary Person',
      'email': 'temporary@example.invalid', 'password': 'demo-password-123',
      'role': 'member',
    }));
    final second = previewClient();
    final list = await second.get(base.resolve('/participants?club_id=$demoClubId'));
    expect((jsonDecode(list.body) as List).length, 1);
    first.close();
    second.close();
  });
}
