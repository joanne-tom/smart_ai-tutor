import 'package:flutter/material.dart';
import 'dart:html' as html;
import '../services/api_service.dart';

class FacultyDashboardScreen extends StatefulWidget {
  final String facultyName;
  const FacultyDashboardScreen({super.key, required this.facultyName});

  @override
  State<FacultyDashboardScreen> createState() => _FacultyDashboardScreenState();
}

class _FacultyDashboardScreenState extends State<FacultyDashboardScreen> {
  final _subjectController = TextEditingController();
  final _topicController = TextEditingController();
  final _dateController = TextEditingController();
  bool _isScheduling = false;
  String? _scheduleMessage;
  List<dynamic> _sessions = [];

  @override
  void initState() {
    super.initState();
    _dateController.text = DateTime.now().toString().split(' ')[0];
    _loadSessions();
  }

  Future<void> _loadSessions() async {
    try {
      final sessions = await ApiService.getSessions();
      setState(() => _sessions = sessions);
    } catch (e) {}
  }

  Future<void> _scheduleSession() async {
    final subject = _subjectController.text.trim();
    final topic = _topicController.text.trim();
    final date = _dateController.text.trim();

    if (subject.isEmpty || topic.isEmpty) {
      setState(() => _scheduleMessage = 'Please fill in subject and topic.');
      return;
    }

    setState(() {
      _isScheduling = true;
      _scheduleMessage = null;
    });

    try {
      await ApiService.seedSession(
        subject: subject,
        topic: topic,
        date: date,
        faculty: widget.facultyName,
      );
      setState(() {
        _scheduleMessage = '✅ Session scheduled! Students can now see it.';
        _subjectController.clear();
        _topicController.clear();
        _isScheduling = false;
      });
      _loadSessions();
      // Replace the catch block in _scheduleSession()
    } catch (e) {
      setState(() {
        _scheduleMessage = '❌ Failed: ${e.toString()}'; // ✅ shows actual error
        _isScheduling = false;
      });
    }
  }

  void _openFacultyPortal() {
    html.window.open('http://localhost:5001', '_blank');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F1B2D),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0F1B2D),
        elevation: 0,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Faculty Dashboard',
              style: TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            Text(
              'Welcome, ${widget.facultyName}',
              style: TextStyle(
                color: Colors.white.withOpacity(0.5),
                fontSize: 12,
              ),
            ),
          ],
        ),
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Upload Notes button
            _buildCard(
              icon: Icons.upload_file,
              title: 'Upload Notes & Syllabus',
              subtitle: 'Opens the RAG faculty portal to upload PDFs',
              child: SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _openFacultyPortal,
                  icon: const Icon(Icons.open_in_new, size: 18),
                  label: const Text('Open Upload Portal'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1E88E5),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                    elevation: 0,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Schedule Session
            _buildCard(
              icon: Icons.calendar_today,
              title: 'Schedule Session',
              subtitle: 'Students will be notified immediately',
              child: Column(
                children: [
                  _buildField(
                    _subjectController,
                    'Subject (e.g. Computer Networks)',
                    Icons.book_outlined,
                  ),
                  const SizedBox(height: 12),
                  _buildField(
                    _topicController,
                    'Topic (e.g. OSI Model)',
                    Icons.topic_outlined,
                  ),
                  const SizedBox(height: 12),
                  _buildField(
                    _dateController,
                    'Date (YYYY-MM-DD)',
                    Icons.date_range_outlined,
                  ),
                  const SizedBox(height: 16),
                  if (_scheduleMessage != null)
                    Container(
                      padding: const EdgeInsets.all(10),
                      margin: const EdgeInsets.only(bottom: 12),
                      decoration: BoxDecoration(
                        color: _scheduleMessage!.startsWith('✅')
                            ? Colors.green.withOpacity(0.1)
                            : Colors.red.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        _scheduleMessage!,
                        style: TextStyle(
                          color: _scheduleMessage!.startsWith('✅')
                              ? Colors.greenAccent
                              : Colors.redAccent,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: _isScheduling ? null : _scheduleSession,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.greenAccent.withOpacity(0.2),
                        foregroundColor: Colors.greenAccent,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10),
                          side: const BorderSide(
                            color: Colors.greenAccent,
                            width: 1,
                          ),
                        ),
                        elevation: 0,
                      ),
                      child: _isScheduling
                          ? const CircularProgressIndicator(
                              color: Colors.greenAccent,
                              strokeWidth: 2,
                            )
                          : const Text(
                              'Schedule Session',
                              style: TextStyle(fontWeight: FontWeight.w600),
                            ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Scheduled sessions list
            _buildCard(
              icon: Icons.list_alt,
              title: 'Scheduled Sessions',
              subtitle: '${_sessions.length} session(s)',
              child: _sessions.isEmpty
                  ? Center(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Text(
                          'No sessions yet.',
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.3),
                          ),
                        ),
                      ),
                    )
                  : Column(
                      children: _sessions
                          .map(
                            (s) => Container(
                              margin: const EdgeInsets.only(bottom: 8),
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: const Color(0xFF0F1B2D),
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(
                                  color: Colors.white.withOpacity(0.05),
                                ),
                              ),
                              child: Row(
                                children: [
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 8,
                                      vertical: 3,
                                    ),
                                    decoration: BoxDecoration(
                                      color: Colors.greenAccent.withOpacity(
                                        0.1,
                                      ),
                                      borderRadius: BorderRadius.circular(10),
                                    ),
                                    child: Text(
                                      (s['status'] ?? 'scheduled')
                                          .toUpperCase(),
                                      style: const TextStyle(
                                        color: Colors.greenAccent,
                                        fontSize: 10,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          s['topic'] ?? '',
                                          style: const TextStyle(
                                            color: Colors.white,
                                            fontWeight: FontWeight.bold,
                                            fontSize: 13,
                                          ),
                                        ),
                                        Text(
                                          s['subject'] ?? '',
                                          style: TextStyle(
                                            color: Colors.white.withOpacity(
                                              0.4,
                                            ),
                                            fontSize: 11,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  Text(
                                    s['scheduled_date'] ?? '',
                                    style: TextStyle(
                                      color: Colors.white.withOpacity(0.3),
                                      fontSize: 11,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          )
                          .toList(),
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCard({
    required IconData icon,
    required String title,
    required String subtitle,
    required Widget child,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A2840),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withOpacity(0.07)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: const Color(0xFF1E88E5), size: 20),
              const SizedBox(width: 8),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                    ),
                  ),
                  Text(
                    subtitle,
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.4),
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 16),
          child,
        ],
      ),
    );
  }

  Widget _buildField(
    TextEditingController controller,
    String hint,
    IconData icon,
  ) {
    return TextField(
      controller: controller,
      style: const TextStyle(color: Colors.white, fontSize: 14),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: TextStyle(
          color: Colors.white.withOpacity(0.3),
          fontSize: 13,
        ),
        prefixIcon: Icon(icon, color: const Color(0xFF1E88E5), size: 18),
        filled: true,
        fillColor: const Color(0xFF0F1B2D),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFF1E88E5), width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 14,
          vertical: 12,
        ),
      ),
    );
  }

  @override
  void dispose() {
    _subjectController.dispose();
    _topicController.dispose();
    _dateController.dispose();
    super.dispose();
  }
}
