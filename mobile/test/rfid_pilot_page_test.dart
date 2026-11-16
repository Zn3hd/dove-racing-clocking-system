import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:dove_racing_mobile/rfid/pilot_page.dart';

void main() {
  testWidgets(
      'pilot requires explicit simulator confirmation before storage or upload',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(
        home: RfidPilotPage(
            ownerId: '00000000-0000-4000-8000-000000000001',
            origin: 'https://test.example')));
    expect(find.text('TEST EVENTS ONLY — no physical reader'), findsOneWidget);
    await tester.enterText(find.byType(TextFormField).at(0),
        '00000000-0000-4000-8000-000000000002');
    await tester.enterText(find.byType(TextFormField).at(1),
        '00000000-0000-4000-8000-000000000003');
    await tester.tap(find.text('Open pilot queue'));
    await tester.pump();
    expect(find.text('Confirm that this is a simulator reader and test race.'),
        findsOneWidget);
    expect(find.text('Save simulated scan'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
