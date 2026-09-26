// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for French (`fr`).
class AppLocalizationsFr extends AppLocalizations {
  AppLocalizationsFr([String locale = 'fr']) : super(locale);

  @override
  String get smsConnectTitle => 'Mes opportunités';

  @override
  String get smsConnectReview => 'À examiner';

  @override
  String get smsConnectOngoing => 'En cours';

  @override
  String get smsConnectFinished => 'Terminées';

  @override
  String get smsConnectIntermediary =>
      'SMS reste votre intermédiaire. Une opportunité ne garantit pas un contrat.';

  @override
  String get smsConnectInterested => 'Je suis intéressé';

  @override
  String get smsConnectDecline => 'Décliner';

  @override
  String get smsConnectDecisionSaved => 'Votre réponse a été transmise à SMS.';

  @override
  String get smsConnectDecisionError =>
      'Impossible de transmettre votre réponse. Réessayez.';

  @override
  String get smsConnectLoadError => 'Impossible de charger vos opportunités.';

  @override
  String get smsConnectRetry => 'Réessayer';

  @override
  String get smsConnectEmptyReview => 'Aucune demande à examiner.';

  @override
  String get smsConnectEmptyOngoing => 'Aucune opportunité en cours.';

  @override
  String get smsConnectEmptyFinished => 'Aucune opportunité terminée.';

  @override
  String get smsConnectHistory => 'Demandes traitées';

  @override
  String get smsConnectAccepted => 'Intérêt manifesté';

  @override
  String get smsConnectDeclined => 'Demande déclinée';

  @override
  String get smsConnectPending => 'En attente de votre réponse';

  @override
  String get smsConnectActive => 'Opportunité ouverte';

  @override
  String get smsConnectProgressing => 'En progression';

  @override
  String get smsConnectSuccessful => 'Aboutie';

  @override
  String get smsConnectUnsuccessful => 'Non aboutie';

  @override
  String get smsConnectWithdrawn => 'Retirée';

  @override
  String get smsConnectOrigin => 'Issue de votre intérêt pour cette demande';

  @override
  String get smsConnectTrial => 'Essai sportif';

  @override
  String get smsConnectRecruitment => 'Recrutement';

  @override
  String get smsConnectContract => 'Proposition de contrat';

  @override
  String get smsConnectPartnership => 'Partenariat';

  @override
  String get smsConnectInformation => 'Demande d’informations';

  @override
  String get smsConnectOpened => 'Ouverte le';

  @override
  String get smsConnectClosed => 'Terminée le';

  @override
  String get smsConnectReceived => 'Reçue le';

  @override
  String get smsConnectCreated => 'Demande créée le';
}
