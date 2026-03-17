class Session {
  final int id;
  final String subject;
  final String topic;
  final String scheduledDate;
  final String facultyName;
  final String status;
  final String? startTime;
  final String? endTime;

  Session({
    required this.id,
    required this.subject,
    required this.topic,
    required this.scheduledDate,
    required this.facultyName,
    required this.status,
    this.startTime,
    this.endTime,
  });

  factory Session.fromJson(Map<String, dynamic> json) {
    return Session(
      id: json['id'],
      subject: json['subject'] ?? '',
      topic: json['topic'] ?? '',
      scheduledDate: json['scheduled_date'] ?? '',
      facultyName: json['faculty_name'] ?? 'Faculty',
      status: json['status'] ?? 'scheduled',
      startTime: json['start_time'],
      endTime: json['end_time'],
    );
  }

  bool get isCompleted {
    if (endTime != null && scheduledDate.isNotEmpty) {
      try {
        final endDt = DateTime.parse('$scheduledDate $endTime');
        return DateTime.now().isAfter(endDt);
      } catch (e) {
        return false;
      }
    }
    return false;
  }

  bool get isActive {
    if (status != 'active' && status != 'scheduled') return false;
    return !isCompleted;
  }
}