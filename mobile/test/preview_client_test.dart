import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:dove_racing_mobile/preview_client.dart';

void main() {
  test('preview returns a demo chairman and club without network', () async {
    final client = previewClient();
    final me = await client.get(Uri.parse('https://example.invalid/auth/me'));
    final clubs = await client.get(Uri.parse('https://example.invalid/clubs'));
    expect(jsonDecode(me.body)['role'], 'chairman');
    expect((jsonDecode(clubs.body) as List).single['name'], 'Dove Racing Demo Club');
    client.close();
  });

  test('preview never accepts writes', () async {
    final client = previewClient();
    for (final path in ['/participants', '/pigeons', '/races']) {
      final response = await client.post(Uri.parse('https://example.invalid$path'),
          body: jsonEncode({'name': 'must not be saved'}));
      expect(response.statusCode, 403);
    }
    client.close();
  });

  test('preview club records remain scoped to demo data', () async {
    final client = previewClient();
    final races = await client.get(Uri.parse('https://example.invalid/races'));
    expect((jsonDecode(races.body) as List).single['status'], 'draft');
    final unknown = await client.get(Uri.parse('https://example.invalid/clocking'));
    expect(unknown.statusCode, 404);
    client.close();
  });
}
