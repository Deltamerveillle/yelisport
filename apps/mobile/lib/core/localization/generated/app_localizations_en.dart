// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get smsConnectTitle => 'My opportunities';

  @override
  String get smsConnectReview => 'To review';

  @override
  String get smsConnectOngoing => 'Ongoing';

  @override
  String get smsConnectFinished => 'Completed';

  @override
  String get smsConnectIntermediary =>
      'SMS remains your intermediary. An opportunity does not guarantee a contract.';

  @override
  String get smsConnectInterested => 'I am interested';

  @override
  String get smsConnectDecline => 'Decline';

  @override
  String get smsConnectDecisionSaved => 'Your response has been sent to SMS.';

  @override
  String get smsConnectDecisionError =>
      'Unable to send your response. Please try again.';

  @override
  String get smsConnectLoadError => 'Unable to load your opportunities.';

  @override
  String get smsConnectRetry => 'Retry';

  @override
  String get smsConnectEmptyReview => 'No requests to review.';

  @override
  String get smsConnectEmptyOngoing => 'No ongoing opportunities.';

  @override
  String get smsConnectEmptyFinished => 'No completed opportunities.';

  @override
  String get smsConnectHistory => 'Reviewed requests';

  @override
  String get smsConnectAccepted => 'Interest expressed';

  @override
  String get smsConnectDeclined => 'Request declined';

  @override
  String get smsConnectPending => 'Awaiting your response';

  @override
  String get smsConnectActive => 'Open opportunity';

  @override
  String get smsConnectProgressing => 'In progress';

  @override
  String get smsConnectSuccessful => 'Successful';

  @override
  String get smsConnectUnsuccessful => 'Unsuccessful';

  @override
  String get smsConnectWithdrawn => 'Withdrawn';

  @override
  String get smsConnectOrigin =>
      'Created after you expressed interest in this request';

  @override
  String get smsConnectTrial => 'Sports trial';

  @override
  String get smsConnectRecruitment => 'Recruitment';

  @override
  String get smsConnectContract => 'Contract proposal';

  @override
  String get smsConnectPartnership => 'Partnership';

  @override
  String get smsConnectInformation => 'Information request';

  @override
  String get smsConnectOpened => 'Opened on';

  @override
  String get smsConnectClosed => 'Completed on';

  @override
  String get smsConnectReceived => 'Received on';

  @override
  String get smsConnectCreated => 'Request created on';
}
