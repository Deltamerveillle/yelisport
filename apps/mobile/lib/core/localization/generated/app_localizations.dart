import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_fr.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'generated/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('fr')
  ];

  /// No description provided for @smsConnectTitle.
  ///
  /// In fr, this message translates to:
  /// **'Mes opportunités'**
  String get smsConnectTitle;

  /// No description provided for @smsConnectReview.
  ///
  /// In fr, this message translates to:
  /// **'À examiner'**
  String get smsConnectReview;

  /// No description provided for @smsConnectOngoing.
  ///
  /// In fr, this message translates to:
  /// **'En cours'**
  String get smsConnectOngoing;

  /// No description provided for @smsConnectFinished.
  ///
  /// In fr, this message translates to:
  /// **'Terminées'**
  String get smsConnectFinished;

  /// No description provided for @smsConnectIntermediary.
  ///
  /// In fr, this message translates to:
  /// **'SMS reste votre intermédiaire. Une opportunité ne garantit pas un contrat.'**
  String get smsConnectIntermediary;

  /// No description provided for @smsConnectInterested.
  ///
  /// In fr, this message translates to:
  /// **'Je suis intéressé'**
  String get smsConnectInterested;

  /// No description provided for @smsConnectDecline.
  ///
  /// In fr, this message translates to:
  /// **'Décliner'**
  String get smsConnectDecline;

  /// No description provided for @smsConnectDecisionSaved.
  ///
  /// In fr, this message translates to:
  /// **'Votre réponse a été transmise à SMS.'**
  String get smsConnectDecisionSaved;

  /// No description provided for @smsConnectDecisionError.
  ///
  /// In fr, this message translates to:
  /// **'Impossible de transmettre votre réponse. Réessayez.'**
  String get smsConnectDecisionError;

  /// No description provided for @smsConnectLoadError.
  ///
  /// In fr, this message translates to:
  /// **'Impossible de charger vos opportunités.'**
  String get smsConnectLoadError;

  /// No description provided for @smsConnectRetry.
  ///
  /// In fr, this message translates to:
  /// **'Réessayer'**
  String get smsConnectRetry;

  /// No description provided for @smsConnectEmptyReview.
  ///
  /// In fr, this message translates to:
  /// **'Aucune demande à examiner.'**
  String get smsConnectEmptyReview;

  /// No description provided for @smsConnectEmptyOngoing.
  ///
  /// In fr, this message translates to:
  /// **'Aucune opportunité en cours.'**
  String get smsConnectEmptyOngoing;

  /// No description provided for @smsConnectEmptyFinished.
  ///
  /// In fr, this message translates to:
  /// **'Aucune opportunité terminée.'**
  String get smsConnectEmptyFinished;

  /// No description provided for @smsConnectHistory.
  ///
  /// In fr, this message translates to:
  /// **'Demandes traitées'**
  String get smsConnectHistory;

  /// No description provided for @smsConnectAccepted.
  ///
  /// In fr, this message translates to:
  /// **'Intérêt manifesté'**
  String get smsConnectAccepted;

  /// No description provided for @smsConnectDeclined.
  ///
  /// In fr, this message translates to:
  /// **'Demande déclinée'**
  String get smsConnectDeclined;

  /// No description provided for @smsConnectPending.
  ///
  /// In fr, this message translates to:
  /// **'En attente de votre réponse'**
  String get smsConnectPending;

  /// No description provided for @smsConnectActive.
  ///
  /// In fr, this message translates to:
  /// **'Opportunité ouverte'**
  String get smsConnectActive;

  /// No description provided for @smsConnectProgressing.
  ///
  /// In fr, this message translates to:
  /// **'En progression'**
  String get smsConnectProgressing;

  /// No description provided for @smsConnectSuccessful.
  ///
  /// In fr, this message translates to:
  /// **'Aboutie'**
  String get smsConnectSuccessful;

  /// No description provided for @smsConnectUnsuccessful.
  ///
  /// In fr, this message translates to:
  /// **'Non aboutie'**
  String get smsConnectUnsuccessful;

  /// No description provided for @smsConnectWithdrawn.
  ///
  /// In fr, this message translates to:
  /// **'Retirée'**
  String get smsConnectWithdrawn;

  /// No description provided for @smsConnectOrigin.
  ///
  /// In fr, this message translates to:
  /// **'Issue de votre intérêt pour cette demande'**
  String get smsConnectOrigin;

  /// No description provided for @smsConnectTrial.
  ///
  /// In fr, this message translates to:
  /// **'Essai sportif'**
  String get smsConnectTrial;

  /// No description provided for @smsConnectRecruitment.
  ///
  /// In fr, this message translates to:
  /// **'Recrutement'**
  String get smsConnectRecruitment;

  /// No description provided for @smsConnectContract.
  ///
  /// In fr, this message translates to:
  /// **'Proposition de contrat'**
  String get smsConnectContract;

  /// No description provided for @smsConnectPartnership.
  ///
  /// In fr, this message translates to:
  /// **'Partenariat'**
  String get smsConnectPartnership;

  /// No description provided for @smsConnectInformation.
  ///
  /// In fr, this message translates to:
  /// **'Demande d’informations'**
  String get smsConnectInformation;

  /// No description provided for @smsConnectOpened.
  ///
  /// In fr, this message translates to:
  /// **'Ouverte le'**
  String get smsConnectOpened;

  /// No description provided for @smsConnectClosed.
  ///
  /// In fr, this message translates to:
  /// **'Terminée le'**
  String get smsConnectClosed;

  /// No description provided for @smsConnectReceived.
  ///
  /// In fr, this message translates to:
  /// **'Reçue le'**
  String get smsConnectReceived;

  /// No description provided for @smsConnectCreated.
  ///
  /// In fr, this message translates to:
  /// **'Demande créée le'**
  String get smsConnectCreated;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'fr'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'fr':
      return AppLocalizationsFr();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
