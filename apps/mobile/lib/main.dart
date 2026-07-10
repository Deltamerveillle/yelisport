import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:yelisport/app/app.dart';
import 'package:yelisport/app/config/app_config.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final config = AppConfig.fromEnvironment();
  await Supabase.initialize(
    url: config.supabaseUrl.toString(),
    anonKey: config.supabaseAnonKey,
  );
  runApp(const ProviderScope(child: YeliSportApp()));
}
