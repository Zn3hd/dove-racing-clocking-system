import 'dart:convert';
import 'package:http/http.dart' as http;

const apiBaseUrl = String.fromEnvironment('API_BASE_URL',
    defaultValue: 'https://dove-racing-clocking-system.onrender.com');

class ApiException implements Exception {
  final String message;
  final int? status;
  ApiException(this.message, [this.status]);
  @override
  String toString() => message;
}

class RacingApi {
  final http.Client client;
  final String baseUrl;
  RacingApi(this.client, {this.baseUrl = apiBaseUrl});

  Future<dynamic> request(String path,
      {String method = 'GET', String? token, Object? body}) async {
    final base = Uri.tryParse(baseUrl);
    if (base == null || base.host.isEmpty || base.userInfo.isNotEmpty ||
        base.hasQuery || base.hasFragment ||
        (base.path.isNotEmpty && base.path != '/') ||
        (base.scheme != 'https' && !(base.scheme == 'http' &&
            (base.host == 'localhost' || base.host == '127.0.0.1')))) {
      throw ApiException('Configure an HTTPS API origin without credentials or a path.');
    }
    final relative = Uri.tryParse(path);
    if (relative == null || !path.startsWith('/') || path.startsWith('//') ||
        relative.hasScheme || relative.hasAuthority || relative.hasFragment) {
      throw ApiException('API requests must use a path on the configured server.');
    }
    final uri = base.resolveUri(relative);
    if (uri.origin != base.origin) {
      throw ApiException('API requests must use the configured server.');
    }
    http.Response response;
    try {
      response = await client
          .send(http.Request(method, uri)
            ..followRedirects = false
            ..headers.addAll({
              'Accept': 'application/json',
              if (body != null) 'Content-Type': 'application/json',
              if (token != null) 'Authorization': 'Bearer $token',
            })
            ..body = body == null ? '' : jsonEncode(body))
          .then(http.Response.fromStream)
          .timeout(const Duration(seconds: 75));
    } catch (_) {
      throw ApiException('Cannot reach the server. Check your connection and retry.');
    }
    if (response.statusCode >= 300 && response.statusCode < 400) {
      throw ApiException('The API redirected the request. Check the configured server address.',
          response.statusCode);
    }
    dynamic data;
    try {
      data = jsonDecode(response.body);
    } catch (_) {
      throw ApiException('Unexpected server response.', response.statusCode);
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = data is Map ? data['detail'] : null;
      throw ApiException(
        response.statusCode == 401
            ? 'Your session has expired or your credentials are invalid.'
            : detail is String ? detail : 'Request failed (${response.statusCode}).',
        response.statusCode,
      );
    }
    return data;
  }

  Future<Map<String, dynamic>> login(String email, String password) async =>
      Map<String, dynamic>.from(await request('/auth/login', method: 'POST',
          body: {'email': email.trim(), 'password': password}));

  Future<Map<String, dynamic>> me(String token) async =>
      Map<String, dynamic>.from(await request('/auth/me', token: token));

  Future<List<Map<String, dynamic>>> participants(String token, String clubId) =>
      _list('/participants?club_id=$clubId', token);

  Future<List<Map<String, dynamic>>> pigeons(String token, String clubId) =>
      _list('/pigeons?club_id=$clubId', token);

  Future<List<Map<String, dynamic>>> lofts(String token, String clubId) =>
      _list('/lofts?club_id=$clubId', token);

  Future<Map<String, dynamic>> createParticipant(String token, Map<String, dynamic> body) async =>
      Map<String, dynamic>.from(await request('/participants', method: 'POST', token: token, body: body));

  Future<Map<String, dynamic>> updatePreviewParticipant(
      String token, String id, Map<String, dynamic> body) async =>
      Map<String, dynamic>.from(await request(
        '/participants/${Uri.encodeComponent(id)}',
        method: 'PATCH', token: token, body: body));

  Future<Map<String, dynamic>> createPigeon(String token, Map<String, dynamic> body) async =>
      Map<String, dynamic>.from(await request('/pigeons', method: 'POST', token: token, body: body));

  Future<Map<String, dynamic>> updatePreviewPigeon(
      String token, String id, Map<String, dynamic> body) async =>
      Map<String, dynamic>.from(await request(
        '/pigeons/${Uri.encodeComponent(id)}',
        method: 'PATCH', token: token, body: body));

  Future<Map<String, dynamic>> createRace(String token, Map<String, dynamic> body) async =>
      Map<String, dynamic>.from(await request('/races', method: 'POST', token: token, body: body));

  Future<Map<String, dynamic>> updatePreviewRace(String token, String id, Map<String, dynamic> body) async =>
      Map<String, dynamic>.from(await request('/races/${Uri.encodeComponent(id)}', method: 'PATCH', token: token, body: body));

  Future<List<Map<String, dynamic>>> races(String token) =>
      _list('/races', token);

  Future<List<Map<String, dynamic>>> _list(String path, String token) async =>
      (await request(path, token: token) as List)
          .map((item) => Map<String, dynamic>.from(item as Map)).toList();

  Future<List<Map<String, dynamic>>> clubs(String token) async =>
      (await request('/clubs', token: token) as List)
          .map((item) => Map<String, dynamic>.from(item as Map)).toList();
}
