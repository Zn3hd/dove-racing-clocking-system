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
  RacingApi(this.client);

  Future<dynamic> request(String path,
      {String method = 'GET', String? token, Object? body}) async {
    final base = Uri.parse(apiBaseUrl);
    if (base.scheme != 'https' && base.host != 'localhost' &&
        base.host != '127.0.0.1') {
      throw ApiException('API endpoint must use HTTPS.');
    }
    final uri = base.resolve(path);
    http.Response response;
    try {
      response = await client
          .send(http.Request(method, uri)
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
            : detail is String ? detail : 'Request failed (' + response.statusCode.toString() + ').',
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

  Future<List<Map<String, dynamic>>> clubs(String token) async =>
      (await request('/clubs', token: token) as List)
          .map((item) => Map<String, dynamic>.from(item as Map)).toList();
}
