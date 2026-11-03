import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// Local, read-only demonstration data for PR browser previews.
/// This client never makes network requests to the production API.
http.Client previewClient() => MockClient((request) async {
  final path = request.url.path;
  if (request.method != 'GET') {
    return http.Response(jsonEncode({'detail': 'Preview is read-only'}), 403,
        headers: {'content-type': 'application/json'});
  }
  final clubId = '00000000-0000-4000-8000-000000000001';
  final data = switch (path) {
    '/auth/me' => <String, dynamic>{
      'id': 'preview-user', 'role': 'chairman', 'full_name': 'Demo Chairman',
      'email': 'demo@example.invalid',
    },
    '/clubs' => [
      {'id': clubId, 'name': 'Dove Racing Demo Club',
       'description': 'Preview data only — no live records'},
    ],
    '/participants' => [
      {'id': 'demo-member', 'full_name': 'Sample Member',
       'role_code': 'member', 'email': 'sample@example.invalid'},
    ],
    '/pigeons' => [
      {'id': 'demo-pigeon', 'official_ring_number': 'DEMO-2026-001',
       'name': 'Demo Pigeon', 'status': 'active'},
    ],
    '/races' => [
      {'id': 'demo-race', 'club_id': clubId, 'name': 'Demo Draft Race',
       'status': 'draft'},
    ],
    '/lofts' => [
      {'id': 'demo-loft', 'name': 'Demo Loft',
       'verified_at': '2026-01-01T00:00:00Z'},
    ],
    _ => null,
  };
  if (data == null) {
    return http.Response(jsonEncode({'detail': 'Not found'}), 404,
        headers: {'content-type': 'application/json'});
  }
  return http.Response(jsonEncode(data), 200,
      headers: {'content-type': 'application/json'});
});
