import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'api.dart';
import 'session.dart';
import 'preview_client.dart';
import 'preview_participant_edit.dart';

import 'management_form.dart';

const isWebPreview = bool.fromEnvironment('WEB_PREVIEW', defaultValue: false);

void main() => runApp(const DoveApp());

class DoveApp extends StatefulWidget {
  const DoveApp({super.key});
  @override
  State<DoveApp> createState() => _DoveAppState();
}

class _DoveAppState extends State<DoveApp> {
  final api = RacingApi(isWebPreview ? previewClient() : http.Client());
  late final session = Session(api);
  bool loading = true;
  String? accessToken;

  @override
  void initState() {
    super.initState();
    if (isWebPreview) {
      accessToken = 'demo-preview-token';
      loading = false;
    } else {
      _restore();
    }
  }

  Future<void> _restore() async {
    String? token;
    try {
      token = await session.token();
    } catch (_) {
      await session.logout();
    }
    if (token != null) {
      try {
        await api.me(token);
        if (mounted) setState(() { accessToken = token; loading = false; });
        return;
      } on ApiException catch (e) {
        if (e.status == 401 || e.status == 403) {
          await session.logout();
        } else {
          // Do not discard a valid session for transient connectivity failures.
          if (mounted) setState(() { accessToken = token; loading = false; });
          return;
        }
      }
    }
    if (mounted) setState(() { accessToken = null; loading = false; });
  }

  Future<void> _login(String email, String password) async {
    await session.login(email, password);
    final token = await session.token();
    if (token == null) throw ApiException('Could not save session.');
    try {
      await api.me(token);
    } catch (_) {
      await session.logout();
      rethrow;
    }
    if (mounted) setState(() => accessToken = token);
  }

  Future<void> _logout() async {
    try {
      await session.logout();
    } finally {
      if (mounted) setState(() => accessToken = null);
    }
  }

  @override
  void dispose() {
    api.client.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Dove Racing',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(colorSchemeSeed: const Color(0xff155e75), useMaterial3: true),
    home: loading
        ? const Scaffold(body: Center(child: CircularProgressIndicator()))
        : accessToken == null
            ? LoginPage(onLogin: _login)
            : HomePage(api: api, token: accessToken!, onLogout: _logout,
                onUnauthorized: _logout),
  );
}

class LoginPage extends StatefulWidget {
  final Future<void> Function(String, String) onLogin;
  const LoginPage({super.key, required this.onLogin});
  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final form = GlobalKey<FormState>();
  final email = TextEditingController();
  final password = TextEditingController();
  bool busy = false;
  String? error;

  @override
  void dispose() {
    email.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (!(form.currentState?.validate() ?? false) || busy) return;
    setState(() { busy = true; error = null; });
    try {
      await widget.onLogin(email.text, password.text);
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } catch (_) {
      if (mounted) setState(() => error = 'Unable to sign in.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Dove Racing')),
    body: Center(child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 420),
      child: SingleChildScrollView(padding: const EdgeInsets.all(24),
        child: Form(key: form, child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Icon(Icons.flutter_dash, size: 68),
            const SizedBox(height: 16),
            Text('Club sign in', style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 8),
            const Text('Use your existing Dove Racing administrator credentials.'),
            const SizedBox(height: 24),
            TextFormField(controller: email, keyboardType: TextInputType.emailAddress,
              autofillHints: const [AutofillHints.username], decoration: const InputDecoration(
                labelText: 'Email', border: OutlineInputBorder()),
              validator: (v) => v == null || !v.contains('@') ? 'Enter a valid email' : null),
            const SizedBox(height: 12),
            TextFormField(controller: password, obscureText: true,
              autofillHints: const [AutofillHints.password],
              decoration: const InputDecoration(labelText: 'Password',
                border: OutlineInputBorder()),
              validator: (v) => v == null || v.isEmpty ? 'Enter your password' : null),
            if (error != null) Padding(padding: const EdgeInsets.only(top: 12),
              child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
            const SizedBox(height: 20),
            FilledButton(onPressed: busy ? null : submit,
              child: Padding(padding: const EdgeInsets.all(12),
                child: busy ? const CircularProgressIndicator() : const Text('Sign in'))),
          ],
        )),
      ),
    )),
  );
}

bool canManageClub(String? role) => role == 'chairman' || role == 'president';

class HomePage extends StatefulWidget {
  final RacingApi api;
  final String token;
  final Future<void> Function() onLogout;
  final Future<void> Function() onUnauthorized;
  const HomePage({super.key, required this.api, required this.token,
    required this.onLogout, required this.onUnauthorized});
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  late Future<(Map<String, dynamic>, List<Map<String, dynamic>>)> data;

  @override
  void initState() {
    super.initState();
    refresh();
  }

  Future<T> guarded<T>(Future<T> Function() action) async {
    try {
      return await action();
    } on ApiException catch (e) {
      if (e.status == 401) await widget.onUnauthorized();
      rethrow;
    }
  }

  void refresh() {
    data = guarded(() async {
      final me = await widget.api.me(widget.token);
      final clubs = canManageClub(me['role'] as String?)
          ? await widget.api.clubs(widget.token)
          : <Map<String, dynamic>>[];
      return (me, clubs);
    });
  }

  void openClub(Map<String, dynamic> club) {
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => ClubDetailsPage(
        api: widget.api, token: widget.token, club: club,
        onUnauthorized: widget.onUnauthorized,
      ),
    ));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Dove Racing'),
      actions: [if (!isWebPreview) IconButton(tooltip: 'Sign out', icon: const Icon(Icons.logout),
        onPressed: widget.onLogout)]),
    body: FutureBuilder<(Map<String, dynamic>, List<Map<String, dynamic>>)>(
      future: data,
      builder: (context, snapshot) {
        if (!snapshot.hasData && !snapshot.hasError) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('Could not load account details.'),
            TextButton(onPressed: () => setState(refresh), child: const Text('Retry')),
          ]));
        }
        final (me, clubs) = snapshot.data!;
        return RefreshIndicator(
          onRefresh: () async { setState(refresh); await data; },
          child: ListView(padding: const EdgeInsets.all(20), children: [
            if (isWebPreview) const Card(child: ListTile(
              leading: Icon(Icons.visibility_outlined),
              title: Text('Web preview — demonstration mode'),
              subtitle: Text('No login or live API connection required.'),
            )),
            Text('Welcome, ${me['full_name'] ?? 'Member'}',
              style: Theme.of(context).textTheme.headlineSmall),
            Text('Account role: ${me['role'] ?? 'unknown'}'),
            const SizedBox(height: 24),
            Text('My clubs', style: Theme.of(context).textTheme.titleLarge),
            if (!canManageClub(me['role'] as String?))
              const ListTile(title: Text('Club management requires chairman or president access.'))
            else if (clubs.isEmpty)
              const ListTile(title: Text('No clubs assigned to this administrator.'))
            else
              ...clubs.map((club) => Card(child: ListTile(
                leading: const Icon(Icons.groups),
                title: Text(club['name']?.toString() ?? 'Unnamed club'),
                subtitle: Text(club['description']?.toString() ?? ''),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => openClub(club),
              ))),
            const SizedBox(height: 16),
            const Text('Prototype only — official clocking is not enabled.'),
          ]),
        );
      },
    ),
  );
}

class ClubDetailsPage extends StatefulWidget {
  final RacingApi api;
  final String token;
  final Map<String, dynamic> club;
  final Future<void> Function() onUnauthorized;
  const ClubDetailsPage({super.key, required this.api, required this.token,
    required this.club, required this.onUnauthorized});

  @override
  State<ClubDetailsPage> createState() => _ClubDetailsPageState();
}

class _ClubDetailsPageState extends State<ClubDetailsPage> {
  late Future<(List<Map<String, dynamic>>, List<Map<String, dynamic>>,
      List<Map<String, dynamic>>)> data;

  @override
  void initState() {
    super.initState();
    refresh();
  }

  void refresh() {
    data = () async {
      try {
        final clubId = widget.club['id'].toString();
        final participants = await widget.api.participants(widget.token, clubId);
        final pigeons = await widget.api.pigeons(widget.token, clubId);
        final allRaces = await widget.api.races(widget.token);
        final races = allRaces.where((race) => race['club_id']?.toString() == clubId).toList();
        return (participants, pigeons, races);
      } on ApiException catch (e) {
        if (e.status == 401) await widget.onUnauthorized();
        rethrow;
      }
    }();
  }

  Future<void> openCreate(ManagementKind kind) async {
    final created = await Navigator.of(context).push<bool>(MaterialPageRoute(
      builder: (_) => ManagementForm(
        api: widget.api, token: widget.token,
        clubId: widget.club['id'].toString(), kind: kind,
      ),
    ));
    if (created == true && mounted) setState(refresh);
  }

  Future<void> editParticipant(Map<String, dynamic> participant) async {
    if (!isWebPreview) return;
    final saved = await Navigator.of(context).push<bool>(MaterialPageRoute(
      builder: (_) => PreviewParticipantEditPage(
        api: widget.api, token: widget.token, participant: participant,
      ),
    ));
    if (saved == true && mounted) setState(refresh);
  }

  Widget section(String heading, List<Map<String, dynamic>> items,
      String Function(Map<String, dynamic>) title,
      String Function(Map<String, dynamic>) subtitle,
      {bool editableParticipants = false}) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SizedBox(height: 24),
      Text('$heading (${items.length})',
        style: Theme.of(context).textTheme.titleLarge),
      if (items.isEmpty)
        const ListTile(title: Text('No records yet.'))
      else
        ...items.map((item) => ListTile(
          title: Text(title(item)),
          subtitle: Text(subtitle(item)),
          trailing: editableParticipants && isWebPreview
              ? const Icon(Icons.edit_outlined) : null,
          onTap: editableParticipants && isWebPreview
              ? () => editParticipant(item) : null,
        )),
    ]);
  }

  Widget action(String label, IconData icon, ManagementKind kind) =>
      Align(alignment: Alignment.centerLeft, child: OutlinedButton.icon(
        onPressed: () => openCreate(kind), icon: Icon(icon), label: Text(label)));

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.club['name']?.toString() ?? 'Club')),
    body: FutureBuilder<(List<Map<String, dynamic>>, List<Map<String, dynamic>>,
        List<Map<String, dynamic>>)>(
      future: data,
      builder: (context, snapshot) {
        if (!snapshot.hasData && !snapshot.hasError) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('Could not load club records.'),
            TextButton(onPressed: () => setState(refresh), child: const Text('Retry')),
          ]));
        }
        final (participants, pigeons, races) = snapshot.data!;
        return RefreshIndicator(
          onRefresh: () async { setState(refresh); await data; },
          child: ListView(padding: const EdgeInsets.all(20), children: [
            Text(widget.club['description']?.toString() ?? 'Club overview'),
            if (isWebPreview) const Card(child: ListTile(
              leading: Icon(Icons.visibility_outlined),
              title: Text('Browser preview — interactive sandbox'),
              subtitle: Text('Try registration forms with temporary demo records. No production access. Reloading resets changes.'),
            )),
            action('Register participant', Icons.person_add, ManagementKind.participant),
            section('Participants', participants,
              (item) => item['full_name']?.toString() ?? 'Unnamed participant',
              (item) => item['role_code']?.toString() ?? '',
              editableParticipants: true),
            action('Register pigeon', Icons.add_circle_outline, ManagementKind.pigeon),
            section('Pigeons', pigeons,
              (item) => item['official_ring_number']?.toString() ?? 'Unknown ring',
              (item) => item['name']?.toString() ?? ''),
            action('Create draft race', Icons.flag_outlined, ManagementKind.race),
            section('Races', races,
              (item) => item['name']?.toString() ?? 'Unnamed race',
              (item) => item['status']?.toString() ?? ''),
            const SizedBox(height: 24),
            Text(isWebPreview
                ? 'Sandbox only — changes reset on reload. Official clocking is not enabled.'
                : 'Prototype only — official clocking is not enabled.'),
          ]),
        );
      },
    ),
  );
}
