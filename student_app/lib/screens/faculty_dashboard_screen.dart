import 'package:flutter/material.dart';
import 'dart:html' as html;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:file_picker/file_picker.dart';
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
  final _startTimeController = TextEditingController(text: '10:00');
  final _endTimeController = TextEditingController(text: '11:00');

  bool _isScheduling = false;
  String? _scheduleMessage;
  List<dynamic> _sessions = [];

  // File picker variables
  PlatformFile? _selectedFile;
  dynamic _fileBytes;
  String? _fileName;

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

  Future<void> _pickFile() async {
    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf'],
        withData: true, // Needed for web
      );

      if (result != null) {
        setState(() {
          _selectedFile = result.files.first;
          _fileName = _selectedFile!.name;
          _fileBytes = _selectedFile!.bytes;
        });
      }
    } catch (e) {
      setState(() => _scheduleMessage = 'Error picking file: $e');
    }
  }

  Future<void> _scheduleSession() async {
    final subject = _subjectController.text.trim();
    final topic = _topicController.text.trim();
    final date = _dateController.text.trim();
    final startTime = _startTimeController.text.trim();
    final endTime = _endTimeController.text.trim();

    if (subject.isEmpty ||
        topic.isEmpty ||
        startTime.isEmpty ||
        endTime.isEmpty) {
      setState(() => _scheduleMessage = 'Please fill in all details.');
      return;
    }

    if (_fileBytes == null) {
      setState(() => _scheduleMessage = 'Please upload a notes PDF.');
      return;
    }

    setState(() {
      _isScheduling = true;
      _scheduleMessage = null;
    });

    try {
      int sessionId = await ApiService.seedSession(
        subject: subject,
        topic: topic,
        date: date,
        faculty: widget.facultyName,
        startTime: startTime,
        endTime: endTime,
      );

      setState(() {
        _scheduleMessage =
            '✅ Session scheduled! Waiting for lecture to be generated...';
        _subjectController.clear();
        _topicController.clear();
      });
      _loadSessions();

      await ApiService.uploadAndGenerateLecture(
        sessionId: sessionId,
        subject: subject,
        topic: topic,
        fileBytes: _fileBytes,
        fileName: _fileName!,
      );

      setState(() {
        _scheduleMessage = 'Lecture has been generated for $topic!';
        _selectedFile = null;
        _fileName = null;
        _fileBytes = null;
        _isScheduling = false;
      });
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

  Future<void> _deleteSession(int sessionId) async {
    bool confirm =
        await showDialog(
          context: context,
          builder: (context) => AlertDialog(
            backgroundColor: const Color(0xFF1A2840),
            title: const Text(
              'Delete Session',
              style: TextStyle(color: Colors.white),
            ),
            content: const Text(
              'Are you sure you want to delete this session?',
              style: TextStyle(color: Colors.white70),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text(
                  'Cancel',
                  style: TextStyle(color: Colors.white54),
                ),
              ),
              TextButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text(
                  'Delete',
                  style: TextStyle(color: Colors.redAccent),
                ),
              ),
            ],
          ),
        ) ??
        false;

    if (!confirm) return;

    try {
      await ApiService.deleteSession(sessionId);
      _loadSessions();
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Session deleted')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Delete failed: $e')));
      }
    }
  }

  bool _isSessionCompleted(Map<String, dynamic> s) {
    final date = s['scheduled_date'];
    final end = s['end_time'];
    if (date != null && end != null && date.isNotEmpty && end.isNotEmpty) {
      try {
        final endDt = DateTime.parse('$date $end');
        return DateTime.now().isAfter(endDt);
      } catch (e) {
        return false;
      }
    }
    return false;
  }

  Future<void> _showAttendanceReport(int sessionId, String topic) async {
    try {
      final report = await ApiService.getAttendanceReport(sessionId);
      if (!mounted) return;

      showDialog(
        context: context,
        builder: (context) => AlertDialog(
          backgroundColor: const Color(0xFF1A2840),
          title: Text(
            'Attendance: $topic',
            style: const TextStyle(color: Colors.white),
          ),
          content: SizedBox(
            width: double.maxFinite,
            child: report.isEmpty
                ? const Text(
                    'No students attended.',
                    style: TextStyle(color: Colors.white70),
                  )
                : ListView.builder(
                    shrinkWrap: true,
                    itemCount: report.length,
                    itemBuilder: (context, index) {
                      final r = report[index];
                      final isLate = r['is_late'] == 1 || r['is_late'] == true;
                      return ListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text(
                          r['name'],
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 14,
                          ),
                        ),
                        subtitle: Text(
                          'Joined: ${r['joined_at']?.split('.').first ?? 'N/A'}\nLeft: ${r['left_at']?.split('.').first ?? 'Still Active'}',
                          style: const TextStyle(
                            color: Colors.white54,
                            fontSize: 12,
                          ),
                        ),
                        trailing: isLate
                            ? const Text(
                                'LATE',
                                style: TextStyle(
                                  color: Colors.redAccent,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 12,
                                ),
                              )
                            : const Text(
                                'ON TIME',
                                style: TextStyle(
                                  color: Colors.greenAccent,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 12,
                                ),
                              ),
                      );
                    },
                  ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close'),
            ),
          ],
        ),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Failed to load report: $e')));
      }
    }
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
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildField(
                          _startTimeController,
                          'Start (HH:MM)',
                          Icons.access_time,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildField(
                          _endTimeController,
                          'End (HH:MM)',
                          Icons.access_time,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  // New file picker row
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0F1B2D),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.picture_as_pdf,
                          color: Color(0xFF1E88E5),
                          size: 18,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            _fileName ?? 'No notes attached (Required)',
                            style: TextStyle(
                              color: _fileName != null
                                  ? Colors.white
                                  : Colors.white.withOpacity(0.3),
                              fontSize: 13,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        TextButton(
                          onPressed: _pickFile,
                          style: TextButton.styleFrom(
                            foregroundColor: const Color(0xFF1E88E5),
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 8,
                            ),
                            minimumSize: Size.zero,
                            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          ),
                          child: Text(
                            _fileName == null ? 'Browse' : 'Change',
                            style: const TextStyle(fontSize: 12),
                          ),
                        ),
                      ],
                    ),
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
                                      color: _isSessionCompleted(s)
                                          ? Colors.orangeAccent.withOpacity(0.1)
                                          : Colors.greenAccent.withOpacity(0.1),
                                      borderRadius: BorderRadius.circular(10),
                                    ),
                                    child: Text(
                                      _isSessionCompleted(s)
                                          ? 'PAST'
                                          : (s['status'] ?? 'scheduled')
                                                .toUpperCase(),
                                      style: TextStyle(
                                        color: _isSessionCompleted(s)
                                            ? Colors.orangeAccent
                                            : Colors.greenAccent,
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
                                  Column(
                                    crossAxisAlignment: CrossAxisAlignment.end,
                                    children: [
                                      Text(
                                        '${s['scheduled_date']} ${s['start_time'] ?? ''}',
                                        style: TextStyle(
                                          color: Colors.white.withOpacity(0.3),
                                          fontSize: 11,
                                        ),
                                      ),
                                      if (_isSessionCompleted(s))
                                        TextButton(
                                          onPressed: () =>
                                              _showAttendanceReport(
                                                s['id'],
                                                s['topic'],
                                              ),
                                          style: TextButton.styleFrom(
                                            padding: const EdgeInsets.symmetric(
                                              horizontal: 4,
                                              vertical: 0,
                                            ),
                                            minimumSize: const Size(0, 24),
                                            tapTargetSize: MaterialTapTargetSize
                                                .shrinkWrap,
                                          ),
                                          child: const Text(
                                            'View Report',
                                            style: TextStyle(
                                              color: Colors.orangeAccent,
                                              fontSize: 11,
                                            ),
                                          ),
                                        ),
                                    ],
                                  ),
                                  IconButton(
                                    icon: const Icon(
                                      Icons.delete_outline,
                                      color: Colors.redAccent,
                                      size: 20,
                                    ),
                                    onPressed: () => _deleteSession(s['id']),
                                    padding: EdgeInsets.zero,
                                    constraints: const BoxConstraints(),
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
