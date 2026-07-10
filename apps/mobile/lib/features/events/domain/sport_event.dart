class SportEvent {
  const SportEvent({
    required this.id,
    required this.sportId,
    required this.organizerId,
    required this.title,
    this.description,
    required this.location,
    required this.startsAt,
    required this.endsAt,
    required this.capacity,
  });

  factory SportEvent.fromJson(Map<String, dynamic> json) {
    return SportEvent(
      id: json['id'] as String,
      sportId: json['sport_id'] as String,
      organizerId: json['organizer_id'] as String,
      title: json['title'] as String,
      description: json['description'] as String?,
      location: json['location'] as String,
      startsAt: DateTime.parse(json['starts_at'] as String),
      endsAt: DateTime.parse(json['ends_at'] as String),
      capacity: json['capacity'] as int,
    );
  }

  final String id;
  final String sportId;
  final String organizerId;
  final String title;
  final String? description;
  final String location;
  final DateTime startsAt;
  final DateTime endsAt;
  final int capacity;
}

class EventDraft {
  const EventDraft({
    required this.sportId,
    required this.title,
    this.description,
    required this.location,
    required this.startsAt,
    required this.endsAt,
    required this.capacity,
  });

  final String sportId;
  final String title;
  final String? description;
  final String location;
  final DateTime startsAt;
  final DateTime endsAt;
  final int capacity;

  Map<String, dynamic> toJson() => {
        'sport_id': sportId,
        'title': title,
        'description': description,
        'location': location,
        'starts_at': startsAt.toUtc().toIso8601String(),
        'ends_at': endsAt.toUtc().toIso8601String(),
        'capacity': capacity,
      };
}
