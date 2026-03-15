import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'http://localhost:5000'; // Your student backend

  static Future<Map<String, dynamic>> _post(
    String endpoint,
    Map<String, dynamic> body,
  ) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl$endpoint'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body),
        )
        .timeout(const Duration(seconds: 30));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('API error ${response.statusCode}: ${response.body}');
    }
  }

  static Future<Map<String, dynamic>> _get(
    String endpoint, {
    Map<String, String>? params,
  }) async {
    final uri = Uri.parse('$baseUrl$endpoint').replace(queryParameters: params);
    final response = await http.get(uri).timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('API error ${response.statusCode}');
    }
  }

  static Future<Map<String, dynamic>> studentLogin({
    required String name,
    required String rollNumber,
  }) async {
    final res = await _post('/mcp/student_login', {
      'name': name,
      'roll_number': rollNumber,
    });
    return res['data'];
  }

  static Future<List<dynamic>> getSessions() async {
    final res = await _get('/mcp/get_sessions');
    return res['data']['sessions'] ?? [];
  }

  static Future<Map<String, dynamic>> joinSession({
    required int studentId,
    required int sessionId,
  }) async {
    final res = await _post('/mcp/join_session', {
      'student_id': studentId,
      'session_id': sessionId,
    });
    return res['data'];
  }

  static Future<Map<String, dynamic>> startLecture({
    required int sessionId,
    required int studentId,
  }) async {
    final res = await _post('/mcp/start_lecture', {
      'session_id': sessionId,
      'student_id': studentId,
    });
    return res['data'];
  }

  static Future<Map<String, dynamic>> askQuestion({
    required int studentId,
    required int sessionId,
    required String question,
  }) async {
    final res = await _post('/mcp/ask_question', {
      'student_id': studentId,
      'session_id': sessionId,
      'question': question,
    });
    return res['data'];
  }

  static Future<void> logEngagement({
    required int studentId,
    required int sessionId,
    required String eventType,
  }) async {
    try {
      await _post('/mcp/log_engagement', {
        'student_id': studentId,
        'session_id': sessionId,
        'event_type': eventType,
      });
    } catch (_) {}
  }

  static Future<void> leaveSession({
    required int studentId,
    required int sessionId,
  }) async {
    await _post('/mcp/leave_session', {
      'student_id': studentId,
      'session_id': sessionId,
    });
  }

  // api_service.dart — replace seedSession method
  static Future<void> seedSession({
    required String subject,
    required String topic,
    required String date,
    required String faculty,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/admin/seed_session'),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: jsonEncode({
        'subject': subject,
        'topic': topic,
        'scheduled_date': date,
        'faculty': faculty,
      }),
    );

    if (response.statusCode != 200 && response.statusCode != 201) {
      throw Exception('Failed: ${response.statusCode} ${response.body}');
    }
  }

  static Future<Map<String, dynamic>> askQuestionWithMode({
    required int studentId,
    required int sessionId,
    required String question,
    required String mode,
  }) async {
    final res = await _post('/mcp/ask_question', {
      'student_id': studentId,
      'session_id': sessionId,
      'question': question,
      'mode': mode,
    });
    return res['data'];
  }
}
