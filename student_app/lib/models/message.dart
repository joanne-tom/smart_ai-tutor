enum MessageRole { tutor, student }

class Message {
  final String text;
  final MessageRole role;
  final DateTime timestamp;
  final bool isLoading;

  Message({
    required this.text,
    required this.role,
    DateTime? timestamp,
    this.isLoading = false,
  }) : timestamp = timestamp ?? DateTime.now();

  bool get isTutor => role == MessageRole.tutor;
  bool get isStudent => role == MessageRole.student;
}