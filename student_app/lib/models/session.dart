class Session {
  final int id;
  final String subject;
  final String topic;
  final String scheduledDate;
  final String facultyName;
  final String status;

  Session({
    required this.id,
    required this.subject,
    required this.topic,
    required this.scheduledDate,
    required this.facultyName,
    required this.status,
  });

  factory Session.fromJson(Map<String, dynamic> json) {
    return Session(
      id: json['id'],
      subject: json['subject'] ?? '',
      topic: json['topic'] ?? '',
      scheduledDate: json['scheduled_date'] ?? '',
      facultyName: json['faculty_name'] ?? 'Faculty',
      status: json['status'] ?? 'scheduled',
    );
  }

  bool get isActive => status == 'active' || status == 'scheduled';
}