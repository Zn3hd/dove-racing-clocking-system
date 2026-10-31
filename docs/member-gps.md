# Member and loft GPS coordinates

The racing location belongs to a member's **loft**, not to their phone's current
position or municipality. Migration `011_loft_gps.sql` adds source, reported GPS
accuracy in meters, and capture time to the existing loft latitude/longitude.
Existing locations retain the `manual` source and their verification state.

## Dashboard workflow

1. Sign in and open **Members**. Select **GPS** next to the member or guest.
2. Enter the loft name and exact decimal latitude/longitude, or select **Use
   this device's location** while physically at that member's loft.
3. The browser requests location permission after the click. The capture fills
   the fields and displays reported accuracy; it does not save automatically.
4. Review and save the location. Reopen **GPS**, independently check the saved
   coordinates at the loft, confirm the checkbox, and verify it.
5. Verified coordinates are used during pigeon/race registration. Existing
   entry snapshots continue to hold their original loft coordinates/distance.

Capture requires a secure origin (the Render HTTPS dashboard or supported local
development browser). It can use GPS/Wi-Fi/network estimates depending on the
device; reported accuracy is not attestation. Denying permission or not having
location support leaves manual entry available. No background tracking is used,
and private coordinates are not sent to a third-party map/geocoding service by
the dashboard. Loft records remain visible only through authorized club APIs.
Registering another member does not imply the administrator's phone is at their
loft: use capture only at the actual loft.

## Sison example

The **Sison town example** fills latitude `9.6588`, longitude `125.5286`, from
[PhilAtlas's municipal reference](https://www.philatlas.com/mindanao/caraga/surigao-del-norte/sison.html).
It is explicitly approximate and does not identify a person's exact loft.
Saving it uses `coordinate_source=town_reference`; API and database constraints
prevent verification until an exact manual/device location is recorded. A town
name alone must never assign every member the same racing coordinates.

## API and integrity

`POST /lofts` and `PUT /lofts/{id}` accept `coordinate_source` (`manual`,
`browser_gps`, `town_reference`), `gps_accuracy_m`, and `gps_captured_at`.
Browser GPS requires finite nonnegative accuracy and a timezone-aware capture
time. Other sources do not accept GPS evidence. The source is declared by the
client and is not proof of physical position. `GET /lofts` includes the fields.
Manual clients that omit these optional fields remain compatible.

Changing coordinates or GPS/source evidence clears verification; changes are
blocked while the loft has registered entries in open/active/closed races.
Coordinates must be finite and within legal latitude/longitude bounds. Captured
coordinates are reviewed separately from saving. Club authorization, audits,
one-loft-per-account, and independent verification remain enforced. Locations
are not assigned to existing production accounts automatically.

Browser capture and visual layout need a physical-device acceptance check.
PostgreSQL tests cover source restrictions, saved accuracy/time, authorization,
verification reset, race-distance calculation, and immutable entry snapshots.
