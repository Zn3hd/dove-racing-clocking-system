import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:dove_racing_mobile/api.dart';
import 'package:dove_racing_mobile/rfid/owner_setup_page.dart';
import 'package:dove_racing_mobile/rfid/queue.dart';

void main() {
  testWidgets(
      'owner enrollment stores a separate device credential without displaying it',
      (tester) async {
    FlutterSecureStorage.setMockInitialValues({});
    const owner = '00000000-0000-4000-8000-000000000001';
    const device = '00000000-0000-4000-8000-000000000002';
    const race = '00000000-0000-4000-8000-000000000003';
    var redemptions = 0;
    final api = RacingApi(MockClient((request) async {
      expect(request.headers['Authorization'], 'Bearer account-jwt');
      if (request.url.path == '/member/readers') {
        return http.Response(
            jsonEncode([
              {
                'id': device,
                'device_identifier': 'Loft reader',
                'race_id': null,
                'race_name': null,
                'reader_adapter': 'usb_hid',
                'reader_protocol': 'ascii-newline-v1'
              }
            ]),
            200);
      }
      expect(request.url.path, '/member/reader-enrollments/redeem');
      expect(jsonDecode(request.body), {'code': 'private-one-use-invitation'});
      redemptions++;
      return http.Response(
          jsonEncode(
              {'device_id': device, 'device_token': 'separate-device-secret'}),
          200);
    }));
    await tester.pumpWidget(MaterialApp(
        home: OwnerReaderSetupPage(
            api: api,
            token: 'account-jwt',
            ownerId: owner,
            onUnauthorized: () async {})));
    await tester.pumpAndSettle();
    await tester.enterText(
        find.byType(TextField), 'private-one-use-invitation');
    await tester.tap(find.text('Enroll reader'));
    await tester.pumpAndSettle();
    expect(redemptions, 1);
    expect(find.text('separate-device-secret'), findsNothing);
    expect(
        find.text(
            'Reader enrolled securely. The earlier gateway credential has been rotated.'),
        findsOneWidget);
    final b = ReaderBinding(
        ownerId: owner, origin: api.baseUrl, deviceId: device, raceId: race);
    expect(await const FlutterSecureStorage().read(key: b.credentialKey),
        'separate-device-secret');
    expect((tester.widget<TextField>(find.byType(TextField))).controller!.text,
        '');
    api.client.close();
  });
}
