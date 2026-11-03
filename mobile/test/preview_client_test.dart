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

  test('edit demo pigeon ring and name with duplicate checks', () async {
    final client = previewClient();
    final endpoint = base.resolve('/pigeons/demo-pigeon');
    final updated = await client.patch(endpoint, body: jsonEncode({
      'official_ring_number': 'DEMO-2026-UPDATED',
      'name': 'Updated Pigeon',
    }));
    expect(updated.statusCode, 200);
    expect(jsonDecode(updated.body)['name'], 'Updated Pigeon');
    final list = await client.get(base.resolve('/pigeons?club_id=$demoClubId'));
    expect((jsonDecode(list.body) as List).single['official_ring_number'],
      'DEMO-2026-UPDATED');
    expect((await client.patch(endpoint, body: jsonEncode({
      'official_ring_number': '', 'name': 'Invalid',
    }))).statusCode, 400);
    expect((await client.patch(endpoint, body: jsonEncode({
      'official_ring_number': 'DEMO-2026-003', 'loft_id': 'another-loft',
    }))).statusCode, 400);
    expect((await client.patch(base.resolve('/pigeons/unknown'),
      body: jsonEncode({'official_ring_number': 'DEMO-X', 'name': ''}))).statusCode, 404);
    client.close();
  });

  test('pigeon edit rejects duplicate ring and resets on new client', () async {
    final client = previewClient();
    await client.post(base.resolve('/pigeons'), body: jsonEncode({
      'loft_id': 'demo-loft', 'official_ring_number': 'DEMO-2026-002',
      'name': 'Another Pigeon',
    }));
    final conflict = await client.patch(base.resolve('/pigeons/demo-pigeon'),
      body: jsonEncode({'official_ring_number': 'DEMO-2026-002', 'name': 'Bad'}));
    expect(conflict.statusCode, 409);
    final fresh = previewClient();
    final list = await fresh.get(base.resolve('/pigeons?club_id=$demoClubId'));
    expect((jsonDecode(list.body) as List).single['official_ring_number'],
      'DEMO-2026-001');
    client.close();
    fresh.close();
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

  test('participant edit updates only demo record and rejects duplicate email', () async {
    final client = previewClient();
    final endpoint = base.resolve('/participants/demo-member');
    final updated = await client.patch(endpoint, body: jsonEncode({
      'full_name': 'Edited Demo', 'email': 'edited@example.invalid',
      'role': 'guest',
    }));
    expect(updated.statusCode, 200);
    expect(jsonDecode(updated.body)['role_code'], 'guest');
    final list = await client.get(base.resolve('/participants?club_id=$demoClubId'));
    expect((jsonDecode(list.body) as List).single['full_name'], 'Edited Demo');
    expect((await client.patch(base.resolve('/participants/unknown'),
      body: jsonEncode({'full_name': 'Test', 'email': 'x@y.test', 'role': 'member'}))).statusCode, 404);
    expect((await client.patch(endpoint, body: jsonEncode({
      'full_name': 'Test', 'email': 'x@y.test', 'role': 'admin',
    }))).statusCode, 400);
    expect((await client.patch(endpoint, body: jsonEncode({
      'full_name': 'Test', 'email': 'x@y.test', 'role': 'member',
      'club_id': 'another-club',
    }))).statusCode, 400);
    client.close();
  });

  test('participant edits reject duplicate email and reset in a new client', () async {
    final client = previewClient();
    await client.post(base.resolve('/participants'), body: jsonEncode({
      'club_id': demoClubId, 'full_name': 'Other',
      'email': 'other@example.invalid', 'password': 'password-12345',
      'role': 'member',
    }));
    final conflict = await client.patch(base.resolve('/participants/demo-member'),
      body: jsonEncode({'full_name': 'Changed',
        'email': 'other@example.invalid', 'role': 'member'}));
    expect(conflict.statusCode, 409);
    final fresh = previewClient();
    final list = await fresh.get(base.resolve('/participants?club_id=$demoClubId'));
    expect((jsonDecode(list.body) as List).single['full_name'], 'Sample Member');
    client.close();
    fresh.close();
  });

  test('draft race settings edit validates and resets', () async {
    final client = previewClient();
    final endpoint = base.resolve('/races/demo-race');
    final settings = {
      'name': 'Updated Draft', 'release_latitude': 15.0,
      'release_longitude': 122.0, 'minimum_speed_mpm': 500,
      'maximum_speed_mpm': 2500, 'display_speed_unit': 'km/h',
      'guest_ranking_mode': 'combined',
    };
    final saved = await client.patch(endpoint, body: jsonEncode(settings));
    expect(saved.statusCode, 200);
    expect(jsonDecode(saved.body)['status'], 'draft');
    expect(jsonDecode(saved.body)['guest_ranking_mode'], 'combined');
    expect((await client.patch(endpoint, body: jsonEncode({
      ...settings, 'maximum_speed_mpm': 400,
    }))).statusCode, 400);
    expect((await client.patch(endpoint, body: jsonEncode({
      ...settings, 'release_latitude': 100,
    }))).statusCode, 400);
    expect((await client.patch(endpoint, body: jsonEncode({
      ...settings, 'status': 'active',
    }))).statusCode, 400);
    expect((await client.patch(base.resolve('/races/unknown'),
      body: jsonEncode(settings))).statusCode, 404);
    final fresh = previewClient();
    final list = await fresh.get(base.resolve('/races'));
    expect((jsonDecode(list.body) as List).single['name'], 'Demo Draft Race');
    client.close();
    fresh.close();
  });

  test('draft race names are unique within demo club', () async {
    final client = previewClient();
    final settings = {
      'club_id': demoClubId, 'name': 'Demo Draft Race',
      'release_latitude': 14.5, 'release_longitude': 121.0,
      'minimum_speed_mpm': 500, 'maximum_speed_mpm': 3000,
      'display_speed_unit': 'm/min', 'guest_ranking_mode': 'separate',
    };
    expect((await client.post(base.resolve('/races'),
      body: jsonEncode(settings))).statusCode, 409);
    final created = await client.post(base.resolve('/races'),
      body: jsonEncode({...settings, 'name': 'Second Race'}));
    expect(created.statusCode, 201);
    expect((await client.patch(base.resolve('/races/demo-race'),
      body: jsonEncode({...settings, 'name': 'second race'}))).statusCode, 409);
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
