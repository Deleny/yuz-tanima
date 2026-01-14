import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  Alert,
} from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as FileSystem from "expo-file-system";

// ==================== CONFIGURATION ====================
// Sunucu adresi - kendi bilgisayarının IP adresini yaz
// Windows'ta: ipconfig komutu ile IPv4 adresini bul
// Örnek: const API_BASE = "http://192.168.1.100:5000";
const API_BASE = "http://192.168.1.197:5000";

const COLORS = {
  background: "#f7f1e8",
  card: "#ffffff",
  accent: "#14656b",
  accentDark: "#0f4c4f",
  text: "#1f2933",
  muted: "#667085",
  border: "#e5ddd4",
  success: "#22c55e",
  error: "#ef4444",
};

const TITLE_FONT = Platform.select({
  ios: "AvenirNext-DemiBold",
  android: "sans-serif-condensed",
  default: "System",
});

const BODY_FONT = Platform.select({
  ios: "AvenirNext-Regular",
  android: "sans-serif",
  default: "System",
});

// ==================== API FUNCTIONS ====================

async function apiRegister(name, imageUri) {
  const formData = new FormData();
  formData.append("name", name);
  formData.append("image", {
    uri: imageUri,
    type: "image/jpeg",
    name: "photo.jpg",
  });

  const response = await fetch(`${API_BASE}/register`, {
    method: "POST",
    body: formData,
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return await response.json();
}

async function apiRecognize(imageUri) {
  const formData = new FormData();
  formData.append("image", {
    uri: imageUri,
    type: "image/jpeg",
    name: "photo.jpg",
  });

  const response = await fetch(`${API_BASE}/recognize`, {
    method: "POST",
    body: formData,
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return await response.json();
}

async function apiGetStatus() {
  const response = await fetch(`${API_BASE}/`);
  return await response.json();
}

// ==================== SCREENS ====================

// Ana Menü Ekranı
function HomeScreen({ onRegister, onRecognize, stats }) {
  return (
    <View style={styles.homeContainer}>
      <View style={styles.bgCircle} />
      <View style={styles.bgCircleAlt} />

      <View style={styles.homeContent}>
        <Text style={styles.homeTitle}>Yuz Tanima</Text>
        <Text style={styles.homeSubtitle}>Python backend ile yuz tanima</Text>

        <View style={styles.statsCard}>
          <Text style={styles.statsText}>
            Kayitli yuz: {stats.samples} | Kisi: {stats.people}
          </Text>
          <Text style={[styles.statsText, { marginTop: 4, fontSize: 12 }]}>
            Sunucu: {stats.connected ? "✅ Bagli" : "❌ Bagli degil"}
          </Text>
        </View>

        <TouchableOpacity style={styles.bigButton} onPress={onRegister}>
          <Text style={styles.bigButtonIcon}>📷</Text>
          <Text style={styles.bigButtonText}>Yuz Kaydet</Text>
          <Text style={styles.bigButtonHint}>Yeni bir yuz kaydi olustur</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.bigButton, styles.bigButtonSecondary]}
          onPress={onRecognize}
        >
          <Text style={styles.bigButtonIcon}>🔍</Text>
          <Text style={[styles.bigButtonText, { color: COLORS.accent }]}>Yuz Tara</Text>
          <Text style={[styles.bigButtonHint, { color: COLORS.muted }]}>Kayitli yuzleri tani</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

// İsim Giriş Ekranı
function EnterNameScreen({ onSubmit, onBack }) {
  const [name, setName] = useState("");

  const handleSubmit = () => {
    const trimmed = name.trim();
    if (!trimmed) {
      Alert.alert("Hata", "Lutfen isminizi girin.");
      return;
    }
    onSubmit(trimmed);
  };

  return (
    <View style={styles.nameContainer}>
      <View style={styles.bgCircle} />
      <View style={styles.bgCircleAlt} />

      <View style={styles.nameContent}>
        <TouchableOpacity style={styles.backButton} onPress={onBack}>
          <Text style={styles.backButtonText}>← Geri</Text>
        </TouchableOpacity>

        <Text style={styles.nameTitle}>Isim Giriniz</Text>
        <Text style={styles.nameSubtitle}>
          Yuz kaydinda kullanilacak ismi girin
        </Text>

        <View style={styles.inputCard}>
          <TextInput
            value={name}
            onChangeText={setName}
            placeholder="Isminiz"
            placeholderTextColor={COLORS.muted}
            style={styles.nameInput}
            autoFocus={true}
            returnKeyType="next"
            onSubmitEditing={handleSubmit}
          />

          <TouchableOpacity
            style={[styles.submitButton, !name.trim() && styles.submitButtonDisabled]}
            onPress={handleSubmit}
            disabled={!name.trim()}
          >
            <Text style={styles.submitButtonText}>Devam →</Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

// Kayıt Kamera Ekranı
function RegisterCameraScreen({ personName, onComplete, onBack, refreshStats }) {
  const cameraRef = useRef(null);
  const [cameraReady, setCameraReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Kamera hazirlaniyor...");
  const [statusType, setStatusType] = useState("info");

  useEffect(() => {
    if (cameraReady) {
      setStatus("Hazir. Kameraya bakin ve Kaydet'e basin.");
      setStatusType("info");
    }
  }, [cameraReady]);

  const handleRegister = useCallback(async () => {
    if (busy) return;
    if (!cameraReady || !cameraRef.current) {
      setStatus("Kamera hazir degil, bekleyin.");
      setStatusType("error");
      return;
    }

    setBusy(true);
    setStatus("Fotograf cekiliyor...");
    setStatusType("info");

    try {
      // Fotoğraf çek
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.8 });
      console.log("Fotograf cekildi:", photo?.uri);

      if (!photo || !photo.uri) {
        setStatus("Fotograf alinamadi.");
        setStatusType("error");
        setBusy(false);
        return;
      }

      // Sunucuya gönder
      setStatus("Sunucuya gonderiliyor...");

      try {
        const result = await apiRegister(personName, photo.uri);
        console.log("API sonucu:", result);

        if (result.success) {
          setStatus(`✅ ${result.message}`);
          setStatusType("success");
          refreshStats();

          // 1.5 saniye sonra ana menüye dön
          setTimeout(() => {
            onComplete();
          }, 1500);
        } else {
          setStatus(`❌ ${result.error}`);
          setStatusType("error");
          setBusy(false);
        }
      } catch (apiErr) {
        console.error("API hatasi:", apiErr);
        setStatus(`Sunucu hatasi: ${apiErr.message}`);
        setStatusType("error");
        setBusy(false);
      }

    } catch (err) {
      console.error("Beklenmeyen hata:", err);
      setStatus(`Hata: ${err.message}`);
      setStatusType("error");
      setBusy(false);
    }
  }, [busy, cameraReady, personName, onComplete, refreshStats]);

  return (
    <View style={styles.cameraContainer}>
      <View style={styles.cameraHeader}>
        <TouchableOpacity style={styles.backButton} onPress={onBack}>
          <Text style={styles.backButtonText}>← Iptal</Text>
        </TouchableOpacity>
        <Text style={styles.cameraTitle}>Kayit: {personName}</Text>
      </View>

      <View style={styles.cameraWrapper}>
        <CameraView
          ref={cameraRef}
          style={styles.fullCamera}
          facing="front"
          onCameraReady={() => setCameraReady(true)}
        />
      </View>

      <View style={styles.cameraBottom}>
        <View style={[
          styles.statusBadge,
          statusType === "success" && styles.statusBadgeSuccess,
          statusType === "error" && styles.statusBadgeError,
        ]}>
          <Text style={styles.statusBadgeText}>{status}</Text>
        </View>

        <TouchableOpacity
          style={[styles.captureButton, busy && styles.captureButtonDisabled]}
          onPress={handleRegister}
          disabled={busy}
        >
          <Text style={styles.captureButtonText}>
            {busy ? "Kaydediliyor..." : "📸 Kaydet"}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

// Tanıma Kamera Ekranı
function RecognizeCameraScreen({ onBack }) {
  const cameraRef = useRef(null);
  const [cameraReady, setCameraReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Kamera hazirlaniyor...");
  const [statusType, setStatusType] = useState("info");
  const [recognized, setRecognized] = useState(null);
  const [confidence, setConfidence] = useState(null);

  useEffect(() => {
    if (cameraReady) {
      setStatus("Hazir. Kameraya bakin ve Tara'ya basin.");
      setStatusType("info");
    }
  }, [cameraReady]);

  const handleRecognize = useCallback(async () => {
    if (busy) return;
    if (!cameraReady || !cameraRef.current) {
      setStatus("Kamera hazir degil.");
      setStatusType("error");
      return;
    }

    setBusy(true);
    setStatus("Taraniyor...");
    setStatusType("info");
    setRecognized(null);
    setConfidence(null);

    try {
      // Fotoğraf çek
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.8 });

      if (!photo || !photo.uri) {
        setStatus("Fotograf alinamadi.");
        setStatusType("error");
        setBusy(false);
        return;
      }

      // Sunucuya gönder
      setStatus("Sunucu analiz ediyor...");

      try {
        const result = await apiRecognize(photo.uri);
        console.log("Tanima sonucu:", result);

        if (result.success) {
          if (result.recognized) {
            setRecognized(result.name);
            setConfidence(result.confidence);
            setStatus(`✅ ${result.message}`);
            setStatusType("success");
          } else {
            setRecognized(null);
            setStatus("❓ Yuz taninamadi");
            setStatusType("error");
          }
        } else {
          setStatus(`❌ ${result.error}`);
          setStatusType("error");
        }
      } catch (apiErr) {
        console.error("API hatasi:", apiErr);
        setStatus(`Sunucu hatasi: ${apiErr.message}`);
        setStatusType("error");
      }

    } catch (err) {
      console.error("Hata:", err);
      setStatus(`Hata: ${err.message}`);
      setStatusType("error");
    } finally {
      setBusy(false);
    }
  }, [busy, cameraReady]);

  return (
    <View style={styles.cameraContainer}>
      <View style={styles.cameraHeader}>
        <TouchableOpacity style={styles.backButton} onPress={onBack}>
          <Text style={styles.backButtonText}>← Geri</Text>
        </TouchableOpacity>
        <Text style={styles.cameraTitle}>Yuz Tarama</Text>
      </View>

      <View style={styles.cameraWrapper}>
        <CameraView
          ref={cameraRef}
          style={styles.fullCamera}
          facing="front"
          onCameraReady={() => setCameraReady(true)}
        />

        {recognized && (
          <View style={styles.recognizedOverlay}>
            <Text style={styles.recognizedName}>{recognized}</Text>
            {confidence && (
              <Text style={styles.recognizedConfidence}>
                Guven: %{confidence}
              </Text>
            )}
          </View>
        )}
      </View>

      <View style={styles.cameraBottom}>
        <View style={[
          styles.statusBadge,
          statusType === "success" && styles.statusBadgeSuccess,
          statusType === "error" && styles.statusBadgeError,
        ]}>
          <Text style={styles.statusBadgeText}>{status}</Text>
        </View>

        <TouchableOpacity
          style={[styles.captureButton, styles.scanButton, busy && styles.captureButtonDisabled]}
          onPress={handleRecognize}
          disabled={busy}
        >
          <Text style={styles.captureButtonText}>
            {busy ? "Taraniyor..." : "🔍 Tara"}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

// ==================== MAIN APP ====================

export default function App() {
  const [permission, requestPermission] = useCameraPermissions();
  const [screen, setScreen] = useState("home");
  const [currentName, setCurrentName] = useState("");
  const [stats, setStats] = useState({ samples: 0, people: 0, connected: false });

  // Sunucu durumunu kontrol et
  const refreshStats = useCallback(async () => {
    try {
      const data = await apiGetStatus();
      setStats({
        samples: data.registered_faces || 0,
        people: data.unique_people || 0,
        connected: true,
      });
    } catch (err) {
      console.log("Sunucu baglantisi yok:", err.message);
      setStats(prev => ({ ...prev, connected: false }));
    }
  }, []);

  useEffect(() => {
    refreshStats();
    // Her 10 saniyede bir kontrol et
    const interval = setInterval(refreshStats, 10000);
    return () => clearInterval(interval);
  }, [refreshStats]);

  // İzin kontrolü
  if (!permission) {
    return (
      <SafeAreaProvider>
        <SafeAreaView style={styles.container}>
          <View style={styles.loading}>
            <ActivityIndicator size="large" color={COLORS.accent} />
            <Text style={styles.loadingText}>Kamera izinleri kontrol ediliyor...</Text>
          </View>
        </SafeAreaView>
      </SafeAreaProvider>
    );
  }

  if (!permission.granted) {
    return (
      <SafeAreaProvider>
        <SafeAreaView style={styles.container}>
          <View style={styles.loading}>
            <Text style={styles.loadingText}>Kamera izni gerekli.</Text>
            <TouchableOpacity style={styles.primaryButton} onPress={requestPermission}>
              <Text style={styles.primaryButtonText}>Izni Ver</Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </SafeAreaProvider>
    );
  }

  // Ekran yönlendirmesi
  let content;

  switch (screen) {
    case "enterName":
      content = (
        <EnterNameScreen
          onSubmit={(name) => {
            setCurrentName(name);
            setScreen("registerCamera");
          }}
          onBack={() => setScreen("home")}
        />
      );
      break;

    case "registerCamera":
      content = (
        <RegisterCameraScreen
          personName={currentName}
          refreshStats={refreshStats}
          onComplete={() => {
            setCurrentName("");
            setScreen("home");
          }}
          onBack={() => setScreen("home")}
        />
      );
      break;

    case "recognizeCamera":
      content = (
        <RecognizeCameraScreen
          onBack={() => setScreen("home")}
        />
      );
      break;

    default:
      content = (
        <HomeScreen
          stats={stats}
          onRegister={() => setScreen("enterName")}
          onRecognize={() => setScreen("recognizeCamera")}
        />
      );
  }

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
        {content}
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

  // Loading
  loading: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 15,
    color: COLORS.text,
    textAlign: "center",
    fontFamily: BODY_FONT,
  },

  // Background decorations
  bgCircle: {
    position: "absolute",
    width: 260,
    height: 260,
    borderRadius: 130,
    backgroundColor: "#f0d7b7",
    top: -70,
    right: -90,
    opacity: 0.6,
  },
  bgCircleAlt: {
    position: "absolute",
    width: 220,
    height: 220,
    borderRadius: 110,
    backgroundColor: "#cfe3d8",
    bottom: -80,
    left: -90,
    opacity: 0.6,
  },

  // Home Screen
  homeContainer: {
    flex: 1,
  },
  homeContent: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 60,
  },
  homeTitle: {
    fontSize: 36,
    color: COLORS.text,
    fontFamily: TITLE_FONT,
    textAlign: "center",
  },
  homeSubtitle: {
    marginTop: 8,
    fontSize: 15,
    color: COLORS.muted,
    fontFamily: BODY_FONT,
    textAlign: "center",
  },
  statsCard: {
    marginTop: 24,
    padding: 16,
    borderRadius: 14,
    backgroundColor: COLORS.card,
    borderWidth: 1,
    borderColor: COLORS.border,
    alignItems: "center",
  },
  statsText: {
    fontSize: 14,
    color: COLORS.muted,
    fontFamily: BODY_FONT,
  },
  bigButton: {
    marginTop: 24,
    padding: 24,
    borderRadius: 20,
    backgroundColor: COLORS.accent,
    alignItems: "center",
    shadowColor: "#000",
    shadowOpacity: 0.15,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 5,
  },
  bigButtonSecondary: {
    backgroundColor: COLORS.card,
    borderWidth: 2,
    borderColor: COLORS.accent,
  },
  bigButtonIcon: {
    fontSize: 40,
    marginBottom: 8,
  },
  bigButtonText: {
    fontSize: 20,
    color: "#fff",
    fontFamily: TITLE_FONT,
  },
  bigButtonHint: {
    marginTop: 4,
    fontSize: 13,
    color: "rgba(255,255,255,0.8)",
    fontFamily: BODY_FONT,
  },

  // Name Screen
  nameContainer: {
    flex: 1,
  },
  nameContent: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 20,
  },
  backButton: {
    alignSelf: "flex-start",
    paddingVertical: 8,
    paddingHorizontal: 4,
  },
  backButtonText: {
    fontSize: 16,
    color: COLORS.accent,
    fontFamily: BODY_FONT,
  },
  nameTitle: {
    marginTop: 40,
    fontSize: 28,
    color: COLORS.text,
    fontFamily: TITLE_FONT,
    textAlign: "center",
  },
  nameSubtitle: {
    marginTop: 8,
    fontSize: 14,
    color: COLORS.muted,
    fontFamily: BODY_FONT,
    textAlign: "center",
  },
  inputCard: {
    marginTop: 40,
    padding: 20,
    borderRadius: 18,
    backgroundColor: COLORS.card,
    borderWidth: 1,
    borderColor: COLORS.border,
    shadowColor: "#000",
    shadowOpacity: 0.08,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 3,
  },
  nameInput: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 18,
    color: COLORS.text,
    fontFamily: BODY_FONT,
    backgroundColor: "#fffefc",
    textAlign: "center",
  },
  submitButton: {
    marginTop: 20,
    paddingVertical: 14,
    borderRadius: 14,
    backgroundColor: COLORS.accent,
    alignItems: "center",
  },
  submitButtonDisabled: {
    opacity: 0.5,
  },
  submitButtonText: {
    fontSize: 18,
    color: "#fff",
    fontFamily: TITLE_FONT,
  },

  // Camera Screens
  cameraContainer: {
    flex: 1,
    backgroundColor: "#000",
  },
  cameraHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: "rgba(0,0,0,0.6)",
  },
  cameraTitle: {
    flex: 1,
    fontSize: 18,
    color: "#fff",
    fontFamily: TITLE_FONT,
    textAlign: "center",
    marginRight: 60,
  },
  cameraWrapper: {
    flex: 1,
    position: "relative",
  },
  fullCamera: {
    flex: 1,
  },
  recognizedOverlay: {
    position: "absolute",
    bottom: 20,
    left: 20,
    right: 20,
    padding: 16,
    borderRadius: 14,
    backgroundColor: "rgba(34, 197, 94, 0.9)",
    alignItems: "center",
  },
  recognizedName: {
    fontSize: 24,
    color: "#fff",
    fontFamily: TITLE_FONT,
  },
  recognizedConfidence: {
    marginTop: 4,
    fontSize: 14,
    color: "rgba(255,255,255,0.9)",
    fontFamily: BODY_FONT,
  },
  cameraBottom: {
    padding: 20,
    backgroundColor: "rgba(0,0,0,0.6)",
  },
  statusBadge: {
    padding: 12,
    borderRadius: 12,
    backgroundColor: "rgba(255,255,255,0.15)",
    marginBottom: 16,
  },
  statusBadgeSuccess: {
    backgroundColor: "rgba(34, 197, 94, 0.3)",
  },
  statusBadgeError: {
    backgroundColor: "rgba(239, 68, 68, 0.3)",
  },
  statusBadgeText: {
    fontSize: 14,
    color: "#fff",
    fontFamily: BODY_FONT,
    textAlign: "center",
  },
  captureButton: {
    paddingVertical: 16,
    borderRadius: 16,
    backgroundColor: COLORS.accent,
    alignItems: "center",
  },
  scanButton: {
    backgroundColor: "#3b82f6",
  },
  captureButtonDisabled: {
    opacity: 0.5,
  },
  captureButtonText: {
    fontSize: 20,
    color: "#fff",
    fontFamily: TITLE_FONT,
  },

  // Common
  primaryButton: {
    marginTop: 16,
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 14,
    backgroundColor: COLORS.accent,
  },
  primaryButtonText: {
    color: "#fff",
    fontSize: 16,
    fontFamily: TITLE_FONT,
  },
});
