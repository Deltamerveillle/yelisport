enum InterestType { trial, recruitment, contract, partnership, information }

enum InterestStatus {
  submitted,
  underReview,
  approved,
  rejected,
  delivered,
  closed
}

enum AthleteResponse { pending, interested, declined }

enum AthleteDecision { interested, declined }

enum OpportunityStatus {
  active,
  progressing,
  successful,
  unsuccessful,
  withdrawn
}

String _text(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! String || value.trim().isEmpty) {
    throw FormatException('Invalid SMS Connect field: $key');
  }
  return value;
}

DateTime? _optionalDate(Map<String, dynamic> json, String key) =>
    json[key] == null ? null : DateTime.parse(_text(json, key));

class SMSConnectInterest {
  const SMSConnectInterest(
      {required this.id,
      required this.organizationName,
      required this.type,
      required this.subject,
      required this.message,
      required this.status,
      required this.athleteResponse,
      required this.createdAt,
      this.deliveredAt,
      this.athleteRespondedAt});

  factory SMSConnectInterest.fromJson(Map<String, dynamic> json) =>
      SMSConnectInterest(
        id: _text(json, 'id'),
        organizationName: _text(json, 'organization_name'),
        type: InterestType.values.byName(_text(json, 'interest_type')),
        subject: _text(json, 'subject'),
        message: _text(json, 'message'),
        status: switch (_text(json, 'status')) {
          'under_review' => InterestStatus.underReview,
          final value => InterestStatus.values.byName(value),
        },
        athleteResponse:
            AthleteResponse.values.byName(_text(json, 'athlete_response')),
        createdAt: DateTime.parse(_text(json, 'created_at')),
        deliveredAt: _optionalDate(json, 'delivered_at'),
        athleteRespondedAt: _optionalDate(json, 'athlete_responded_at'),
      );

  final String id;
  final String organizationName;
  final InterestType type;
  final String subject;
  final String message;
  final InterestStatus status;
  final AthleteResponse athleteResponse;
  final DateTime createdAt;
  final DateTime? deliveredAt;
  final DateTime? athleteRespondedAt;
  bool get needsResponse =>
      status == InterestStatus.delivered &&
      athleteResponse == AthleteResponse.pending;
}

class SMSConnectOpportunity {
  const SMSConnectOpportunity(
      {required this.id,
      required this.interestId,
      required this.organizationName,
      required this.type,
      required this.subject,
      required this.message,
      required this.status,
      required this.openedAt,
      this.closedAt});

  factory SMSConnectOpportunity.fromJson(Map<String, dynamic> json) =>
      SMSConnectOpportunity(
        id: _text(json, 'id'),
        interestId: _text(json, 'interest_id'),
        organizationName: _text(json, 'organization_name'),
        type: InterestType.values.byName(_text(json, 'interest_type')),
        subject: _text(json, 'subject'),
        message: _text(json, 'message'),
        status: OpportunityStatus.values.byName(_text(json, 'status')),
        openedAt: DateTime.parse(_text(json, 'opened_at')),
        closedAt: _optionalDate(json, 'closed_at'),
      );

  final String id;
  final String interestId;
  final String organizationName;
  final InterestType type;
  final String subject;
  final String message;
  final OpportunityStatus status;
  final DateTime openedAt;
  final DateTime? closedAt;
  bool get isOngoing =>
      status == OpportunityStatus.active ||
      status == OpportunityStatus.progressing;
}
