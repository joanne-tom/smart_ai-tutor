import 'package:flutter/material.dart';
import '../models/message.dart';
import '../models/session.dart';
import '../services/api_service.dart';
import '../services/tts_service.dart';

class ChatScreen extends StatefulWidget {
  final int studentId;
  final String studentName;
  final Session session;

  const ChatScreen({
    super.key,
    required this.studentId,
    required this.studentName,
    required this.session,
  });

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> with WidgetsBindingObserver {
  final TtsService _tts = TtsService();
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<Message> _messages = [];

  bool _isLoadingLecture = true;
  bool _isAskingQuestion = false;
  bool _isSpeaking = false;
  bool _showDoubtInput = false;
  bool _showStillConfused = false;
  bool _sessionActive = true;

  String _currentLectureText = '';
  List<String> _lectureChunks = [];
  int _currentChunkIndex = 0;
  bool _isLecturePlaying = false;

  int _doubtCount = 0;
  String _lastQuestion = '';
  String _lastAnswer = '';

  // Teaching modes — adapts based on how many doubts student has asked
  String get _teachingMode {
    if (_doubtCount >= 3) return 'simplified';
    if (_doubtCount == 2) return 'example';
    return 'explanation';
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _tts.init();
    _loadLecture();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    super.didChangeAppLifecycleState(state);
    if (state == AppLifecycleState.paused) {
      ApiService.logEngagement(
        studentId: widget.studentId,
        sessionId: widget.session.id,
        eventType: 'app_exit',
      );
      _tts.pause();
    } else if (state == AppLifecycleState.resumed) {
      ApiService.logEngagement(
        studentId: widget.studentId,
        sessionId: widget.session.id,
        eventType: 'app_return',
      );
    }
  }

  Future<void> _loadLecture() async {
    setState(() => _isLoadingLecture = true);
    _addMessage(
      Message(
        text: 'Loading lecture for "${widget.session.topic}"...',
        role: MessageRole.tutor,
        isLoading: true,
      ),
    );

    try {
      final data = await ApiService.startLecture(
        sessionId: widget.session.id,
        studentId: widget.studentId,
      );
      final lectureText =
          data['lecture_text'] ?? 'Lecture content not available.';
          
      final rawImages = data['images'] as List<dynamic>?;
      final images = rawImages?.map((e) => e.toString()).toList() ?? [];

      _currentLectureText = lectureText;

      setState(() {
        _messages.clear();
        _isLoadingLecture = false;
      });

      _addMessage(
        Message(
          text:
              '📚 ${widget.session.topic} — ${widget.session.subject}\n\n$lectureText',
          role: MessageRole.tutor,
          imageUrls: images,
        ),
      );

      _lectureChunks = _splitIntoSentences(lectureText);
      _currentChunkIndex = 0;
      _playLectureChunks();
    } catch (e) {
      setState(() => _isLoadingLecture = false);
      _addMessage(
        Message(
          text: 'Could not load lecture. Please check your connection.',
          role: MessageRole.tutor,
        ),
      );
    }
  }

  List<String> _splitIntoSentences(String text) {
    return text
        .split(RegExp(r'(?<=[.!?])\s+'))
        .where((s) => s.trim().isNotEmpty)
        .toList();
  }

  Future<void> _playLectureChunks() async {
    if (_isLecturePlaying) return;
    setState(() {
      _isSpeaking = true;
      _isLecturePlaying = true;
    });

    while (_currentChunkIndex < _lectureChunks.length && _isLecturePlaying) {
      await _tts.speak(_lectureChunks[_currentChunkIndex]);
      if (_isLecturePlaying) {
        _currentChunkIndex++;
      }
    }

    if (mounted && _currentChunkIndex >= _lectureChunks.length) {
      setState(() {
        _isSpeaking = false;
        _isLecturePlaying = false;
        _currentChunkIndex = 0;
      });
    }
  }

  Future<void> _speakText(String text) async {
    setState(() => _isSpeaking = true);
    await _tts.speak(text);
    if (mounted) setState(() => _isSpeaking = false);
  }

  void _toggleSpeech() {
    if (_isSpeaking) {
      _tts.stop();
      setState(() {
        _isSpeaking = false;
        _isLecturePlaying = false;
      });
    } else {
      if (_currentChunkIndex < _lectureChunks.length) {
        _playLectureChunks();
      } else {
        _currentChunkIndex = 0;
        _playLectureChunks();
      }
    }
  }

  void _interruptLecture() {
    _tts.stop();
    setState(() {
      _isSpeaking = false;
      _isLecturePlaying = false;
      _showDoubtInput = true;
      _showStillConfused = false;
    });
    _addMessage(
      Message(
        text: '⏸ Lecture paused. Type your doubt below.',
        role: MessageRole.tutor,
      ),
    );
  }

  Future<void> _askQuestion() async {
    final question = _inputController.text.trim();
    if (question.isEmpty || _isAskingQuestion) return;

    _inputController.clear();
    _lastQuestion = question;
    _doubtCount++;

    setState(() {
      _showDoubtInput = false;
      _isAskingQuestion = true;
      _showStillConfused = false;
    });

    _addMessage(Message(text: question, role: MessageRole.student));

    // ✅ Better loading message — student knows to wait
    _addMessage(
      Message(
        text: '🤔 Thinking... (this may take 1-2 minutes)',
        role: MessageRole.tutor,
        isLoading: true,
      ),
    );

    try {
      // ✅ Uses updated askQuestionWithMode with 600s timeout
      final data = await ApiService.askQuestionWithMode(
        studentId: widget.studentId,
        sessionId: widget.session.id,
        question: question,
        mode: _teachingMode,
      );

      final answer = data['answer'] ?? 'Could not find an answer.';
      _lastAnswer = answer;

      setState(() {
        _messages.removeWhere((m) => m.isLoading);
        _isAskingQuestion = false;
        _showStillConfused = true;
      });

      // Show teaching mode label
      String modeLabel = '';
      if (_teachingMode == 'simplified')
        modeLabel = '💡 Simplified explanation:';
      if (_teachingMode == 'example')
        modeLabel = '📖 Example-based explanation:';

      _addMessage(
        Message(
          text: modeLabel.isEmpty ? answer : '$modeLabel\n\n$answer',
          role: MessageRole.tutor,
        ),
      );

      await _speakText(answer);
    } catch (e) {
      setState(() {
        _messages.removeWhere((m) => m.isLoading);
        _isAskingQuestion = false;
        _showDoubtInput = true; // ✅ Re-show input so student can retry
      });
      _addMessage(
        Message(
          text: '⚠️ Could not process your question. Please try again.',
          role: MessageRole.tutor,
        ),
      );
    }
  }

  Future<void> _stillConfused() async {
    setState(() {
      _showStillConfused = false;
      _isAskingQuestion = true;
    });

    _addMessage(
      Message(
        text: '😕 Still confused — let me explain more simply...',
        role: MessageRole.tutor,
        isLoading: true,
      ),
    );

    try {
      final data = await ApiService.askQuestionWithMode(
        studentId: widget.studentId,
        sessionId: widget.session.id,
        question: _lastQuestion,
        mode: 'simplified',
      );

      final answer = data['answer'] ?? 'Let me try a different approach.';

      setState(() {
        _messages.removeWhere((m) => m.isLoading);
        _isAskingQuestion = false;
      });

      _addMessage(
        Message(
          text: '🔄 Simpler explanation:\n\n$answer',
          role: MessageRole.tutor,
        ),
      );

      await _speakText(answer);
      _resumeLecture();
    } catch (e) {
      setState(() {
        _messages.removeWhere((m) => m.isLoading);
        _isAskingQuestion = false;
      });
      _addMessage(
        Message(
          text: '⚠️ Could not get a simpler explanation. Please try again.',
          role: MessageRole.tutor,
        ),
      );
    }
  }

  void _resumeLecture() {
    setState(() => _showStillConfused = false);
    _addMessage(
      Message(text: '▶ Resuming lecture...', role: MessageRole.tutor),
    );
    Future.delayed(const Duration(seconds: 1), () {
      _playLectureChunks();
    });
  }

  void _addMessage(Message msg) {
    setState(() => _messages.add(msg));
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<bool> _onWillPop() async {
    if (_sessionActive) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Cannot leave during an active session!'),
          backgroundColor: Colors.redAccent,
        ),
      );
      return false;
    }
    return true;
  }

  Future<void> _leaveSession() async {
    _tts.stop();
    setState(() => _sessionActive = false);
    await ApiService.leaveSession(
      studentId: widget.studentId,
      sessionId: widget.session.id,
    );
    if (mounted) Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return WillPopScope(
      onWillPop: _onWillPop,
      child: Scaffold(
        backgroundColor: const Color(0xFF0F1B2D),
        appBar: _buildAppBar(),
        body: Column(
          children: [
            _buildSessionInfoBanner(),
            Expanded(child: _buildMessageList()),
            if (_showStillConfused) _buildStillConfusedBar(),
            if (_showDoubtInput) _buildDoubtInputBar(),
            if (!_showDoubtInput) _buildBottomBar(),
          ],
        ),
      ),
    );
  }

  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      backgroundColor: const Color(0xFF0F1B2D),
      elevation: 0,
      automaticallyImplyLeading: false,
      title: Text(
        widget.session.topic,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 16,
          fontWeight: FontWeight.bold,
        ),
      ),
      actions: [
        IconButton(
          icon: Icon(
            _isSpeaking ? Icons.volume_up : Icons.volume_off,
            color: _isSpeaking ? const Color(0xFF1E88E5) : Colors.white38,
          ),
          onPressed: _isLoadingLecture ? null : _toggleSpeech,
        ),
        IconButton(
          icon: const Icon(Icons.exit_to_app, color: Colors.redAccent),
          onPressed: () => _showLeaveDialog(),
        ),
      ],
    );
  }

  Widget _buildSessionInfoBanner() {
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 4, 12, 0),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFF1A2840),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF1E88E5).withOpacity(0.2)),
      ),
      child: Row(
        children: [
          const Icon(Icons.school, color: Color(0xFF1E88E5), size: 16),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '${widget.session.subject} • ${widget.session.facultyName}',
              style: TextStyle(
                color: Colors.white.withOpacity(0.6),
                fontSize: 12,
              ),
            ),
          ),
          if (_doubtCount > 0)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: Colors.orange.withOpacity(0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                'Mode: ${_teachingMode.toUpperCase()}',
                style: const TextStyle(color: Colors.orange, fontSize: 10),
              ),
            ),
          // ✅ Show processing indicator when asking question
          if (_isAskingQuestion) ...[
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: Colors.blueAccent.withOpacity(0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: 10,
                    height: 10,
                    child: CircularProgressIndicator(
                      strokeWidth: 1.5,
                      color: Colors.blueAccent,
                    ),
                  ),
                  SizedBox(width: 4),
                  Text(
                    'Processing',
                    style: TextStyle(color: Colors.blueAccent, fontSize: 11),
                  ),
                ],
              ),
            ),
          ],
          if (_isSpeaking && !_isAskingQuestion) ...[
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: Colors.greenAccent.withOpacity(0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.graphic_eq, size: 12, color: Colors.greenAccent),
                  SizedBox(width: 4),
                  Text(
                    'Speaking',
                    style: TextStyle(color: Colors.greenAccent, fontSize: 11),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildMessageList() {
    if (_isLoadingLecture && _messages.isEmpty) {
      return const Center(
        child: CircularProgressIndicator(color: Color(0xFF1E88E5)),
      );
    }
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
      itemCount: _messages.length,
      itemBuilder: (context, index) =>
          _MessageBubble(message: _messages[index]),
    );
  }

  Widget _buildBottomBar() {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 16),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1B2D),
        border: Border(top: BorderSide(color: Colors.white.withOpacity(0.05))),
      ),
      child: SizedBox(
        width: double.infinity,
        height: 50,
        child: ElevatedButton.icon(
          onPressed: _isLoadingLecture || _isAskingQuestion
              ? null
              : _interruptLecture,
          icon: const Icon(Icons.pan_tool, size: 18),
          label: const Text(
            'Ask Doubt',
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
          ),
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF1E3A5F),
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
            elevation: 0,
          ),
        ),
      ),
    );
  }

  Widget _buildDoubtInputBar() {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 16),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1B2D),
        border: Border(
          top: BorderSide(color: const Color(0xFF1E88E5).withOpacity(0.3)),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _inputController,
              style: const TextStyle(color: Colors.white, fontSize: 14),
              autofocus: true,
              onSubmitted: (_) => _askQuestion(),
              decoration: InputDecoration(
                hintText: 'Type your doubt...',
                hintStyle: TextStyle(
                  color: Colors.white.withOpacity(0.3),
                  fontSize: 14,
                ),
                filled: true,
                fillColor: const Color(0xFF1A2840),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: const BorderSide(color: Color(0xFF1E88E5)),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: const BorderSide(
                    color: Color(0xFF1E88E5),
                    width: 1,
                  ),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: const BorderSide(
                    color: Color(0xFF1E88E5),
                    width: 2,
                  ),
                ),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 18,
                  vertical: 12,
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: _isAskingQuestion ? null : _askQuestion,
            child: Container(
              width: 46,
              height: 46,
              decoration: BoxDecoration(
                color: _isAskingQuestion
                    ? Colors.white.withOpacity(0.1)
                    : const Color(0xFF1E88E5),
                shape: BoxShape.circle,
              ),
              child: _isAskingQuestion
                  ? const Padding(
                      padding: EdgeInsets.all(12),
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.send, color: Colors.white, size: 20),
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: () {
              _inputController.clear();
              setState(() => _showDoubtInput = false);
              _resumeLecture();
            },
            child: Container(
              width: 46,
              height: 46,
              decoration: BoxDecoration(
                color: Colors.redAccent.withOpacity(0.2),
                shape: BoxShape.circle,
                border: Border.all(color: Colors.redAccent.withOpacity(0.5)),
              ),
              child: const Icon(Icons.close, color: Colors.redAccent, size: 20),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStillConfusedBar() {
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 0, 12, 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF1A2840),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.orange.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.help_outline, color: Colors.orange, size: 18),
          const SizedBox(width: 8),
          const Expanded(
            child: Text(
              'Did this clarify your doubt?',
              style: TextStyle(color: Colors.white70, fontSize: 13),
            ),
          ),
          TextButton(
            onPressed: _resumeLecture,
            child: const Text(
              'Yes ✓',
              style: TextStyle(
                color: Colors.greenAccent,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          const SizedBox(width: 4),
          TextButton(
            onPressed: _stillConfused,
            child: const Text(
              'Still confused',
              style: TextStyle(
                color: Colors.orange,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showLeaveDialog() {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF1A2840),
        title: const Text(
          'Leave Session?',
          style: TextStyle(color: Colors.white),
        ),
        content: const Text(
          'Your attendance will be recorded.',
          style: TextStyle(color: Colors.white54),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Stay', style: TextStyle(color: Colors.white54)),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              _leaveSession();
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent),
            child: const Text('Leave'),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _tts.dispose();
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }
}

class _MessageBubble extends StatelessWidget {
  final Message message;
  const _MessageBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    final isTutor = message.isTutor;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        mainAxisAlignment: isTutor
            ? MainAxisAlignment.start
            : MainAxisAlignment.end,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (isTutor) ...[
            Container(
              width: 32,
              height: 32,
              decoration: const BoxDecoration(
                color: Color(0xFF1E88E5),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.smart_toy_outlined,
                color: Colors.white,
                size: 18,
              ),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: isTutor
                    ? const Color(0xFF1A2840)
                    : const Color(0xFF1E88E5),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  bottomLeft: Radius.circular(isTutor ? 4 : 16),
                  bottomRight: Radius.circular(isTutor ? 16 : 4),
                ),
              ),
              child: message.isLoading
                  ? Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // ✅ Show animated dots + loading text
                        const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white38,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          message.text == '...' ? 'Thinking...' : message.text,
                          style: const TextStyle(
                            color: Colors.white54,
                            fontSize: 13,
                          ),
                        ),
                      ],
                    )
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          message.text,
                          style: TextStyle(
                            color: Colors.white.withOpacity(isTutor ? 0.9 : 1.0),
                            fontSize: 14,
                            height: 1.5,
                          ),
                        ),
                        if (message.imageUrls != null && message.imageUrls!.isNotEmpty) ...[
                          const SizedBox(height: 12),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: message.imageUrls!.map((url) => ClipRRect(
                                  borderRadius: BorderRadius.circular(8),
                                  child: Image.network(
                                    url,
                                    width: 250,
                                    fit: BoxFit.contain,
                                    errorBuilder: (context, error, stackTrace) =>
                                        const SizedBox.shrink(),
                                  ),
                                )).toList(),
                          )
                        ],
                      ],
                    ),
            ),
          ),
          if (!isTutor) const SizedBox(width: 8),
        ],
      ),
    );
  }
}
