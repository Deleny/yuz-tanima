import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Platform,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { CameraView, useCameraPermissions } from "expo-camera";
import AsyncStorage from "@react-native-async-storage/async-storage";

// ==================== CONFIGURATION ====================
const API_BASE = "http://3.79.16.211:5000";

const COLORS = {
  background: "#f5f7fa",
  card: "#ffffff",
  accent: "#3b82f6",
  accentDark: "#2563eb",
  text: "#1f2937",
  muted: "#6b7280",
  border: "#e5e7eb",
  success: "#22c55e",
  error: "#ef4444",
  warning: "#f59e0b",
};

// ==================== API FUNCTIONS ====================

async function apiLogin(email, password) {
  const response = await fetch(`${API_BASE}/auth/giris`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, sifre: password }),
  });
  return await response.json();
}

async function apiGetMe(token) {
  const response = await fetch(`${API_BASE}/auth/ben`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return await response.json();
}

// Teacher APIs
async function apiGetTeacherCourses(token) {
  const response = await fetch(`${API_BASE}/ogretmen/derslerim`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return await response.json();
}

async function apiStartAttendance(token, courseId) {
  const response = await fetch(`${API_BASE}/ogretmen/yoklama/baslat`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ders_id: courseId }),
  });
  return await response.json();
}

async function apiEndAttendance(token, sessionId) {
  const response = await fetch(`${API_BASE}/ogretmen/yoklama/bitir`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ oturum_id: sessionId }),
  });
  return await response.json();
}

async function apiGetActiveAttendance(token) {
  const response = await fetch(`${API_BASE}/ogretmen/yoklama/aktif`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return await response.json();
}

// Student APIs
async function apiGetStudentActiveSessions(token) {
  const response = await fetch(`${API_BASE}/ogrenci/aktif-yoklamalar`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return await response.json();
}

async function apiJoinAttendance(token, sessionId, imageUri) {
  const formData = new FormData();
  formData.append("oturum_id", sessionId.toString());
  formData.append("image", {
    uri: imageUri,
    type: "image/jpeg",
    name: "face.jpg",
  });

  const response = await fetch(`${API_BASE}/ogrenci/yoklama/katil`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  return await response.json();
}

async function apiRegisterFace(token, imageUri) {
  const formData = new FormData();
  formData.append("image", {
    uri: imageUri,
    type: "image/jpeg",
    name: "face.jpg",
  });

  const response = await fetch(`${API_BASE}/yuz/kayit`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  return await response.json();
}

// ==================== SCREENS ====================

// Login Screen
function LoginScreen({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async () => {
    if (!email.trim() || !password.trim()) {
      setError("Email ve şifre gerekli");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const result = await apiLogin(email.trim(), password);
      if (result.basarili) {
        await AsyncStorage.setItem("token", result.token);
        onLogin(result.token, result.kullanici);
      } else {
        setError(result.hata || "Giriş başarısız");
      }
    } catch (err) {
      console.error("Login error:", err);
      setError("Sunucuya bağlanılamadı");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.loginContainer}>
      <View style={styles.loginCard}>
        <Text style={styles.loginTitle}>📋 Yoklama Sistemi</Text>
        <Text style={styles.loginSubtitle}>Yüz tanıma ile yoklama</Text>

        {error ? <Text style={styles.errorText}>{error}</Text> : null}

        <TextInput
          style={styles.input}
          placeholder="Email"
          placeholderTextColor={COLORS.muted}
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
        />

        <TextInput
          style={styles.input}
          placeholder="Şifre"
          placeholderTextColor={COLORS.muted}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
        />

        <TouchableOpacity
          style={[styles.loginButton, loading && styles.buttonDisabled]}
          onPress={handleLogin}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.loginButtonText}>Giriş Yap</Text>
          )}
        </TouchableOpacity>

        <Text style={styles.hintText}>
          Test: ogretmen@okul.com / 123456{"\n"}
          veya: ogrenci@okul.com / 123456
        </Text>
      </View>
    </View>
  );
}

// Teacher Dashboard
function TeacherDashboard({ user, token, onLogout }) {
  const [courses, setCourses] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [coursesRes, activeRes] = await Promise.all([
        apiGetTeacherCourses(token),
        apiGetActiveAttendance(token),
      ]);

      if (coursesRes.basarili) {
        setCourses(coursesRes.dersler);
      }
      if (activeRes.basarili) {
        setActiveSession(activeRes.aktif_oturum);
      }
    } catch (err) {
      console.error("Load error:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000); // Her 5 saniyede güncelle
    return () => clearInterval(interval);
  }, [loadData]);

  const handleStartAttendance = async (courseId) => {
    try {
      const result = await apiStartAttendance(token, courseId);
      if (result.basarili) {
        Alert.alert("Başarılı", result.mesaj);
        loadData();
      } else {
        Alert.alert("Hata", result.hata);
      }
    } catch (err) {
      Alert.alert("Hata", "İşlem başarısız");
    }
  };

  const handleEndAttendance = async () => {
    if (!activeSession) return;

    try {
      const result = await apiEndAttendance(token, activeSession.oturum_id);
      if (result.basarili) {
        Alert.alert("Başarılı", `${result.mesaj}\nKatılımcı: ${result.katilimci_sayisi}`);
        loadData();
      } else {
        Alert.alert("Hata", result.hata);
      }
    } catch (err) {
      Alert.alert("Hata", "İşlem başarısız");
    }
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={COLORS.accent} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>👨‍🏫 Merhaba, {user.ad_soyad}</Text>
        <TouchableOpacity onPress={onLogout}>
          <Text style={styles.logoutText}>Çıkış</Text>
        </TouchableOpacity>
      </View>

      {activeSession ? (
        <View style={styles.activeSessionCard}>
          <Text style={styles.activeSessionTitle}>🟢 Aktif Yoklama</Text>
          <Text style={styles.activeSessionCourse}>{activeSession.ders_adi}</Text>
          <Text style={styles.activeSessionCount}>
            Katılan: {activeSession.katilimci_sayisi} öğrenci
          </Text>

          {activeSession.katilimcilar?.length > 0 && (
            <View style={styles.participantsList}>
              {activeSession.katilimcilar.map((k, i) => (
                <Text key={i} style={styles.participantItem}>
                  ✓ {k.ad_soyad} - {k.saat}
                </Text>
              ))}
            </View>
          )}

          <TouchableOpacity style={styles.endButton} onPress={handleEndAttendance}>
            <Text style={styles.endButtonText}>Yoklamayı Bitir</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Derslerim</Text>
          {courses.length === 0 ? (
            <Text style={styles.emptyText}>Henüz ders atanmamış</Text>
          ) : (
            <FlatList
              data={courses}
              keyExtractor={(item) => item.id.toString()}
              refreshControl={
                <RefreshControl refreshing={refreshing} onRefresh={() => {
                  setRefreshing(true);
                  loadData();
                }} />
              }
              renderItem={({ item }) => (
                <View style={styles.courseCard}>
                  <View style={styles.courseInfo}>
                    <Text style={styles.courseName}>{item.ad}</Text>
                    <Text style={styles.courseCode}>{item.kod}</Text>
                    <Text style={styles.courseStudents}>{item.ogrenci_sayisi} öğrenci</Text>
                  </View>
                  <TouchableOpacity
                    style={styles.startButton}
                    onPress={() => handleStartAttendance(item.id)}
                  >
                    <Text style={styles.startButtonText}>Yoklama Başlat</Text>
                  </TouchableOpacity>
                </View>
              )}
            />
          )}
        </View>
      )}
    </View>
  );
}

// Student Dashboard
function StudentDashboard({ user, token, onLogout }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [joiningSession, setJoiningSession] = useState(null);
  const [cameraMode, setCameraMode] = useState(false);
  const [selectedSession, setSelectedSession] = useState(null);

  const loadData = useCallback(async () => {
    try {
      const result = await apiGetStudentActiveSessions(token);
      if (result.basarili) {
        setSessions(result.yoklamalar);
      }
    } catch (err) {
      console.error("Load error:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleJoinPress = (session) => {
    if (session.katildi) {
      Alert.alert("Bilgi", "Bu yoklamaya zaten katıldınız");
      return;
    }
    setSelectedSession(session);
    setCameraMode(true);
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={COLORS.accent} />
      </View>
    );
  }

  if (cameraMode && selectedSession) {
    return (
      <StudentCameraScreen
        token={token}
        session={selectedSession}
        onComplete={() => {
          setCameraMode(false);
          setSelectedSession(null);
          loadData();
        }}
        onBack={() => {
          setCameraMode(false);
          setSelectedSession(null);
        }}
      />
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>👨‍🎓 Merhaba, {user.ad_soyad}</Text>
        <TouchableOpacity onPress={onLogout}>
          <Text style={styles.logoutText}>Çıkış</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Aktif Yoklamalar</Text>

        {sessions.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyIcon}>📭</Text>
            <Text style={styles.emptyText}>Şu an aktif yoklama yok</Text>
            <Text style={styles.emptyHint}>Öğretmeniniz yoklama başlattığında burada görünecek</Text>
          </View>
        ) : (
          <FlatList
            data={sessions}
            keyExtractor={(item) => item.oturum_id.toString()}
            refreshControl={
              <RefreshControl refreshing={refreshing} onRefresh={() => {
                setRefreshing(true);
                loadData();
              }} />
            }
            renderItem={({ item }) => (
              <View style={[styles.sessionCard, item.katildi && styles.sessionCardJoined]}>
                <View style={styles.sessionInfo}>
                  <Text style={styles.sessionCourse}>{item.ders_adi}</Text>
                  <Text style={styles.sessionTeacher}>{item.ogretmen_adi}</Text>
                </View>
                <TouchableOpacity
                  style={[
                    styles.joinButton,
                    item.katildi && styles.joinButtonDone,
                  ]}
                  onPress={() => handleJoinPress(item)}
                  disabled={item.katildi}
                >
                  <Text style={styles.joinButtonText}>
                    {item.katildi ? "✓ Katıldın" : "Katıl"}
                  </Text>
                </TouchableOpacity>
              </View>
            )}
          />
        )}
      </View>
    </View>
  );
}

// Student Camera Screen
function StudentCameraScreen({ token, session, onComplete, onBack }) {
  const cameraRef = useRef(null);
  const [cameraReady, setCameraReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Kamera hazırlanıyor...");
  const [statusType, setStatusType] = useState("info");

  useEffect(() => {
    if (cameraReady) {
      setStatus("Yüzünüzü kameraya gösterin");
      setStatusType("info");
    }
  }, [cameraReady]);

  const handleCapture = useCallback(async () => {
    if (busy || !cameraReady || !cameraRef.current) return;

    setBusy(true);
    setStatus("Fotoğraf çekiliyor...");

    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.8 });

      if (!photo?.uri) {
        setStatus("Fotoğraf alınamadı");
        setStatusType("error");
        setBusy(false);
        return;
      }

      setStatus("Yüz doğrulanıyor...");

      const result = await apiJoinAttendance(token, session.oturum_id, photo.uri);

      if (result.basarili) {
        setStatus(`✅ ${result.mesaj}`);
        setStatusType("success");
        setTimeout(onComplete, 1500);
      } else {
        setStatus(`❌ ${result.hata}`);
        setStatusType("error");
        setBusy(false);
      }
    } catch (err) {
      console.error("Capture error:", err);
      setStatus("Bir hata oluştu");
      setStatusType("error");
      setBusy(false);
    }
  }, [busy, cameraReady, token, session, onComplete]);

  return (
    <View style={styles.cameraContainer}>
      <View style={styles.cameraHeader}>
        <TouchableOpacity onPress={onBack}>
          <Text style={styles.backText}>← Geri</Text>
        </TouchableOpacity>
        <Text style={styles.cameraTitle}>{session.ders_adi}</Text>
      </View>

      <View style={styles.cameraWrapper}>
        <CameraView
          ref={cameraRef}
          style={styles.camera}
          facing="front"
          onCameraReady={() => setCameraReady(true)}
        />
      </View>

      <View style={styles.cameraBottom}>
        <View
          style={[
            styles.statusBadge,
            statusType === "success" && styles.statusSuccess,
            statusType === "error" && styles.statusError,
          ]}
        >
          <Text style={styles.statusText}>{status}</Text>
        </View>

        <TouchableOpacity
          style={[styles.captureButton, busy && styles.buttonDisabled]}
          onPress={handleCapture}
          disabled={busy || !cameraReady}
        >
          <Text style={styles.captureButtonText}>
            {busy ? "İşleniyor..." : "📸 Yoklamaya Katıl"}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

// ==================== MAIN APP ====================

export default function App() {
  const [permission, requestPermission] = useCameraPermissions();
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Check for existing token on app start
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const savedToken = await AsyncStorage.getItem("token");
        if (savedToken) {
          const result = await apiGetMe(savedToken);
          if (result.basarili) {
            setToken(savedToken);
            setUser(result.kullanici);
          } else {
            await AsyncStorage.removeItem("token");
          }
        }
      } catch (err) {
        console.error("Auth check error:", err);
      } finally {
        setLoading(false);
      }
    };
    checkAuth();
  }, []);

  const handleLogin = (newToken, userData) => {
    setToken(newToken);
    setUser(userData);
  };

  const handleLogout = async () => {
    await AsyncStorage.removeItem("token");
    setToken(null);
    setUser(null);
  };

  // Show loading
  if (loading) {
    return (
      <SafeAreaProvider>
        <SafeAreaView style={styles.centered}>
          <ActivityIndicator size="large" color={COLORS.accent} />
          <Text style={styles.loadingText}>Yükleniyor...</Text>
        </SafeAreaView>
      </SafeAreaProvider>
    );
  }

  // Show login if not authenticated
  if (!token || !user) {
    return (
      <SafeAreaProvider>
        <SafeAreaView style={styles.container}>
          <LoginScreen onLogin={handleLogin} />
        </SafeAreaView>
      </SafeAreaProvider>
    );
  }

  // Camera permission check for students
  if (user.rol === "ogrenci" && !permission?.granted) {
    return (
      <SafeAreaProvider>
        <SafeAreaView style={styles.centered}>
          <Text style={styles.permissionText}>Yoklama için kamera izni gerekli</Text>
          <TouchableOpacity style={styles.permissionButton} onPress={requestPermission}>
            <Text style={styles.permissionButtonText}>İzin Ver</Text>
          </TouchableOpacity>
        </SafeAreaView>
      </SafeAreaProvider>
    );
  }

  // Show appropriate dashboard based on role
  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        {user.rol === "ogretmen" ? (
          <TeacherDashboard user={user} token={token} onLogout={handleLogout} />
        ) : user.rol === "ogrenci" ? (
          <StudentDashboard user={user} token={token} onLogout={handleLogout} />
        ) : (
          <View style={styles.centered}>
            <Text>Admin paneli yakında...</Text>
            <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
              <Text style={styles.logoutButtonText}>Çıkış Yap</Text>
            </TouchableOpacity>
          </View>
        )}
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

// ==================== STYLES ====================

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  loadingText: {
    marginTop: 12,
    color: COLORS.muted,
  },

  // Login
  loginContainer: {
    flex: 1,
    justifyContent: "center",
    padding: 20,
  },
  loginCard: {
    backgroundColor: COLORS.card,
    borderRadius: 20,
    padding: 24,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 5,
  },
  loginTitle: {
    fontSize: 28,
    fontWeight: "bold",
    textAlign: "center",
    color: COLORS.text,
  },
  loginSubtitle: {
    fontSize: 14,
    textAlign: "center",
    color: COLORS.muted,
    marginTop: 4,
    marginBottom: 24,
  },
  input: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 12,
    padding: 14,
    fontSize: 16,
    marginBottom: 12,
    backgroundColor: "#fff",
  },
  loginButton: {
    backgroundColor: COLORS.accent,
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    marginTop: 8,
  },
  loginButtonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  errorText: {
    color: COLORS.error,
    textAlign: "center",
    marginBottom: 12,
  },
  hintText: {
    marginTop: 16,
    textAlign: "center",
    color: COLORS.muted,
    fontSize: 12,
  },

  // Header
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 16,
    backgroundColor: COLORS.card,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: "600",
    color: COLORS.text,
  },
  logoutText: {
    color: COLORS.error,
    fontWeight: "500",
  },

  // Section
  section: {
    flex: 1,
    padding: 16,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: "600",
    color: COLORS.text,
    marginBottom: 16,
  },

  // Course Card
  courseCard: {
    flexDirection: "row",
    backgroundColor: COLORS.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  courseInfo: {
    flex: 1,
  },
  courseName: {
    fontSize: 16,
    fontWeight: "600",
    color: COLORS.text,
  },
  courseCode: {
    fontSize: 12,
    color: COLORS.muted,
    marginTop: 2,
  },
  courseStudents: {
    fontSize: 12,
    color: COLORS.muted,
    marginTop: 4,
  },
  startButton: {
    backgroundColor: COLORS.accent,
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  startButtonText: {
    color: "#fff",
    fontWeight: "600",
    fontSize: 14,
  },

  // Active Session
  activeSessionCard: {
    margin: 16,
    backgroundColor: COLORS.card,
    borderRadius: 16,
    padding: 20,
    borderWidth: 2,
    borderColor: COLORS.success,
  },
  activeSessionTitle: {
    fontSize: 16,
    fontWeight: "600",
    color: COLORS.success,
  },
  activeSessionCourse: {
    fontSize: 24,
    fontWeight: "bold",
    color: COLORS.text,
    marginTop: 8,
  },
  activeSessionCount: {
    fontSize: 16,
    color: COLORS.muted,
    marginTop: 4,
  },
  participantsList: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  participantItem: {
    fontSize: 14,
    color: COLORS.text,
    paddingVertical: 4,
  },
  endButton: {
    backgroundColor: COLORS.error,
    borderRadius: 10,
    padding: 14,
    alignItems: "center",
    marginTop: 16,
  },
  endButtonText: {
    color: "#fff",
    fontWeight: "600",
  },

  // Session Card (Student)
  sessionCard: {
    flexDirection: "row",
    backgroundColor: COLORS.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    alignItems: "center",
    borderWidth: 2,
    borderColor: COLORS.warning,
  },
  sessionCardJoined: {
    borderColor: COLORS.success,
    opacity: 0.7,
  },
  sessionInfo: {
    flex: 1,
  },
  sessionCourse: {
    fontSize: 16,
    fontWeight: "600",
    color: COLORS.text,
  },
  sessionTeacher: {
    fontSize: 13,
    color: COLORS.muted,
    marginTop: 2,
  },
  joinButton: {
    backgroundColor: COLORS.accent,
    borderRadius: 8,
    paddingHorizontal: 20,
    paddingVertical: 12,
  },
  joinButtonDone: {
    backgroundColor: COLORS.success,
  },
  joinButtonText: {
    color: "#fff",
    fontWeight: "600",
  },

  // Empty State
  emptyCard: {
    backgroundColor: COLORS.card,
    borderRadius: 16,
    padding: 32,
    alignItems: "center",
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: 12,
  },
  emptyText: {
    fontSize: 16,
    color: COLORS.text,
    fontWeight: "500",
  },
  emptyHint: {
    fontSize: 13,
    color: COLORS.muted,
    marginTop: 8,
    textAlign: "center",
  },

  // Camera
  cameraContainer: {
    flex: 1,
    backgroundColor: "#000",
  },
  cameraHeader: {
    flexDirection: "row",
    alignItems: "center",
    padding: 16,
    backgroundColor: "rgba(0,0,0,0.6)",
  },
  backText: {
    color: "#fff",
    fontSize: 16,
  },
  cameraTitle: {
    flex: 1,
    color: "#fff",
    fontSize: 18,
    fontWeight: "600",
    textAlign: "center",
    marginRight: 40,
  },
  cameraWrapper: {
    flex: 1,
  },
  camera: {
    flex: 1,
  },
  cameraBottom: {
    padding: 20,
    backgroundColor: "rgba(0,0,0,0.6)",
  },
  statusBadge: {
    backgroundColor: "rgba(255,255,255,0.2)",
    borderRadius: 10,
    padding: 12,
    marginBottom: 16,
  },
  statusSuccess: {
    backgroundColor: "rgba(34, 197, 94, 0.3)",
  },
  statusError: {
    backgroundColor: "rgba(239, 68, 68, 0.3)",
  },
  statusText: {
    color: "#fff",
    textAlign: "center",
    fontSize: 14,
  },
  captureButton: {
    backgroundColor: COLORS.accent,
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
  },
  captureButtonText: {
    color: "#fff",
    fontSize: 18,
    fontWeight: "600",
  },

  // Permission
  permissionText: {
    fontSize: 16,
    color: COLORS.text,
    marginBottom: 16,
    textAlign: "center",
  },
  permissionButton: {
    backgroundColor: COLORS.accent,
    borderRadius: 10,
    paddingHorizontal: 24,
    paddingVertical: 12,
  },
  permissionButtonText: {
    color: "#fff",
    fontWeight: "600",
  },

  // Logout
  logoutButton: {
    marginTop: 20,
    backgroundColor: COLORS.error,
    borderRadius: 10,
    paddingHorizontal: 24,
    paddingVertical: 12,
  },
  logoutButtonText: {
    color: "#fff",
    fontWeight: "600",
  },
});
