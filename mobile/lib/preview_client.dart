import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const demoClubId = '00000000-0000-4000-8000-000000000001';

/// Isolated, in-memory preview API. No request ever reaches the network.
/// Changes last only until the browser tab reloads.
http.Client previewClient() {
  final participants = <Map<String, dynamic>>[
    {'id': 'demo-member', 'club_id': demoClubId, 'full_name': 'Sample Member',
     'role_code': 'member', 'email': 'sample@example.invalid'},
  ];
  final pigeons = <Map<String, dynamic>>[
    {'id': 'demo-pigeon', 'loft_id': 'demo-loft',
     'official_ring_number': 'DEMO-2026-001', 'name': 'Demo Pigeon'},
  ];
  final races = <Map<String, dynamic>>[
    {'id': 'demo-race', 'club_id': demoClubId,
     'name': 'Demo Draft Race', 'status': 'draft'},
  ];
  final lofts = <Map<String, dynamic>>[
    {'id': 'demo-loft', 'club_id': demoClubId, 'name': 'Demo Loft',
     'verified_at': '2026-01-01T00:00:00Z'},
  ];
  var sequence = 0;
  http.Response response(Object value, [int status = 200]) =>
      http.Response(jsonEncode(value), status,
          headers: {'content-type': 'application/json'});
  http.Response bad(String detail, [int status = 400]) =>
      response({'detail': detail}, status);
  String? string(Map<String, dynamic> data, String key) {
    final v = data[key];
    return v is String ? v.trim() : null;
  }

  return MockClient((request) async {
    final path = request.url.path;
    if (request.method == 'GET') {
      final clubFilter = request.url.queryParameters['club_id'];
      List<Map<String, dynamic>> scoped(List<Map<String, dynamic>> items) =>
          clubFilter == null
              ? items
              : items.where((e) => e['club_id'] == clubFilter).toList();
      final data = switch (path) {
        '/auth/me' => <String, dynamic>{
          'id': 'preview-user', 'role': 'chairman',
          'full_name': 'Demo Chairman', 'email': 'demo@example.invalid',
        },
        '/clubs' => [
          {'id': demoClubId, 'name': 'Dove Racing Demo Club',
           'description': 'Preview data only — no live records'},
        ],
        '/participants' => scoped(participants),
        '/pigeons' => clubFilter == null || clubFilter == demoClubId
            ? pigeons : <Map<String, dynamic>>[],
        '/races' => scoped(races),
        '/lofts' => scoped(lofts),
        _ => null,
      };
      return data == null ? bad('Not found', 404) : response(data);
    }
    if (request.method == 'PATCH' && path.startsWith('/pigeons/')) {
      final id = Uri.decodeComponent(path.substring('/pigeons/'.length));
      final index = pigeons.indexWhere((p) => p['id'] == id &&
          lofts.any((l) => l['id'] == p['loft_id'] &&
              l['club_id'] == demoClubId && l['verified_at'] != null));
      if (index < 0) return bad('Pigeon not found', 404);
      Map<String, dynamic> updates;
      try {
        final decoded = jsonDecode(request.body);
        if (decoded is! Map<String, dynamic>) return bad('Invalid request');
        updates = decoded;
      } catch (_) {
        return bad('Invalid JSON');
      }
      if (updates.keys.any((key) => !['official_ring_number', 'name'].contains(key))) {
        return bad('Only ring number and name can be edited in preview');
      }
      final ring = string(updates, 'official_ring_number');
      final name = updates['name'];
      if (ring == null || ring.isEmpty || (name != null && name is! String)) {
        return bad('Enter a valid ring number and pigeon name');
      }
      if (pigeons.any((p) => p['id'] != id && p['official_ring_number'] == ring)) {
        return bad('This demo ring is already registered', 409);
      }
      pigeons[index] = {...pigeons[index],
        'official_ring_number': ring,
        'name': name is String && name.trim().isNotEmpty ? name.trim() : null};
      return response(pigeons[index]);
    }
    if (request.method == 'PATCH' && path.startsWith('/participants/')) {
      final id = Uri.decodeComponent(path.substring('/participants/'.length));
      final index = participants.indexWhere((p) => p['id'] == id && p['club_id'] == demoClubId);
      if (index < 0) return bad('Participant not found', 404);
      Map<String, dynamic> updates;
      try {
        final decoded = jsonDecode(request.body);
        if (decoded is! Map<String, dynamic>) return bad('Invalid request');
        updates = decoded;
      } catch (_) {
        return bad('Invalid JSON');
      }
      if (updates.keys.any((key) => !['full_name', 'email', 'role'].contains(key))) {
        return bad('Only name, email and role can be edited in preview');
      }
      final name = string(updates, 'full_name');
      final email = string(updates, 'email');
      final role = string(updates, 'role');
      if (name == null || name.isEmpty || email == null || !email.contains('@') ||
          !['member', 'guest'].contains(role)) {
        return bad('Check participant name, email and role');
      }
      if (participants.any((p) => p['id'] != id && p['email'] == email)) {
        return bad('This demo email is already registered', 409);
      }
      participants[index] = {...participants[index],
        'full_name': name, 'email': email, 'role_code': role};
      return response(participants[index]);
    }
    if (request.method != 'POST' ||
        !['/participants', '/pigeons', '/races'].contains(path)) {
      return bad('This action is unavailable in the demo', 403);
    }
    Map<String, dynamic> body;
    try {
      final decoded = jsonDecode(request.body);
      if (decoded is! Map<String, dynamic>) return bad('Invalid request');
      body = decoded;
    } catch (_) {
      return bad('Invalid JSON');
    }
    if (path == '/participants') {
      final name = string(body, 'full_name');
      final email = string(body, 'email');
      final password = string(body, 'password');
      final role = string(body, 'role');
      if (body['club_id'] != demoClubId || name == null || name.isEmpty ||
          email == null || !email.contains('@') ||
          password == null || password.length < 12 ||
          !['member', 'guest'].contains(role)) {
        return bad('Check the participant fields and club');
      }
      if (participants.any((p) => p['email'] == email)) {
        return bad('This demo email is already registered', 409);
      }
      final record = <String, dynamic>{
        'id': 'demo-participant-${++sequence}', 'club_id': demoClubId,
        'full_name': name, 'email': email, 'role_code': role,
      };
      participants.add(record);
      return response(record, 201);
    }
    if (path == '/pigeons') {
      final loftId = string(body, 'loft_id');
      final ring = string(body, 'official_ring_number');
      if (!lofts.any((l) => l['id'] == loftId && l['verified_at'] != null) ||
          ring == null || ring.isEmpty) {
        return bad('A verified demo loft and official ring number are required');
      }
      if (pigeons.any((p) => p['official_ring_number'] == ring)) {
        return bad('This demo ring is already registered', 409);
      }
      final record = <String, dynamic>{
        'id': 'demo-pigeon-${++sequence}', 'loft_id': loftId,
        'official_ring_number': ring, 'name': string(body, 'name'),
      };
      pigeons.add(record);
      return response(record, 201);
    }
    final name = string(body, 'name');
    final lat = body['release_latitude'];
    final lng = body['release_longitude'];
    final min = body['minimum_speed_mpm'];
    final max = body['maximum_speed_mpm'];
    if (body['club_id'] != demoClubId || name == null || name.isEmpty ||
        lat is! num || !lat.isFinite || lat < -90 || lat > 90 ||
        lng is! num || !lng.isFinite || lng < -180 || lng > 180 ||
        min is! num || !min.isFinite || min <= 0 ||
        max is! num || !max.isFinite || max <= min ||
        !['m/min', 'm/s', 'km/h'].contains(body['display_speed_unit']) ||
        !['separate', 'combined'].contains(body['guest_ranking_mode'])) {
      return bad('Check the draft race settings');
    }
    final record = <String, dynamic>{
      'id': 'demo-race-${++sequence}', 'club_id': demoClubId,
      'name': name, 'status': 'draft',
      'release_latitude': lat, 'release_longitude': lng,
      'minimum_speed_mpm': min, 'maximum_speed_mpm': max,
      'display_speed_unit': body['display_speed_unit'],
      'guest_ranking_mode': body['guest_ranking_mode'],
    };
    races.add(record);
    return response(record, 201);
  });
}
