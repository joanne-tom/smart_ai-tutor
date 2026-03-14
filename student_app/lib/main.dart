import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'screens/login_screen.dart';
import 'screens/role_selection_screen.dart';
import 'screens/session_list_screen.dart';

void main() {
  runApp(const SmartAiTutorApp());
}

class SmartAiTutorApp extends StatelessWidget {
  const SmartAiTutorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Smart AI Tutor',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF1E88E5),
          surface: Color(0xFF1A2840),
        ),
        scaffoldBackgroundColor: const Color(0xFF0F1B2D),
      ),
      home: const SplashRouter(),
    );
  }
}

class SplashRouter extends StatefulWidget {
  const SplashRouter({super.key});

  @override
  State<SplashRouter> createState() => _SplashRouterState();
}

class _SplashRouterState extends State<SplashRouter> {
  @override
  void initState() {
    super.initState();
    _checkSession();
  }

  Future<void> _checkSession() async {
    await Future.delayed(const Duration(milliseconds: 800));
    final prefs = await SharedPreferences.getInstance();
    final studentId = prefs.getInt('student_id');
    final studentName = prefs.getString('student_name');

    if (!mounted) return;

    if (studentId != null && studentName != null) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => SessionListScreen(
            studentId: studentId,
            studentName: studentName,
          ),
        ),
      );
    } else {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const RoleSelectionScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: Color(0xFF0F1B2D),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.school, color: Color(0xFF1E88E5), size: 64),
            SizedBox(height: 20),
            Text(
              'Smart AI Tutor',
              style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold),
            ),
            SizedBox(height: 8),
            Text(
              'Student App',
              style: TextStyle(color: Colors.white38, fontSize: 14),
            ),
            SizedBox(height: 40),
            CircularProgressIndicator(color: Color(0xFF1E88E5), strokeWidth: 2),
          ],
        ),
      ),
    );
  }
}