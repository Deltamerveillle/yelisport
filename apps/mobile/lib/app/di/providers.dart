import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/app/config/app_config.dart';

final appConfigProvider = Provider<AppConfig>(
  (ref) => AppConfig.fromEnvironment(),
);
