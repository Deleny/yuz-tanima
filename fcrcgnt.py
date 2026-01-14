import sys
import time
import pickle
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog

try:
    import cv2
    import face_recognition
    import numpy as np
    try:
        import dlib
    except ImportError:
        dlib = None
except ImportError as exc:
    missing = str(exc)
    print("Eksik kutuphane:", missing)
    print("Kurulum ornegi: pip install opencv-python face_recognition numpy")
    sys.exit(1)


BASE_DIR = Path(__file__).resolve().parent
ENCODINGS_PATH = BASE_DIR / "encodings.pkl"
IMAGES_DIR = BASE_DIR / "face_data"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

ANGLE_PROMPTS = [
    ("Duz bak", "straight"),
    ("Sola bak", "left"),
    ("Saga bak", "right"),
    ("Yukari bak", "up"),
    ("Asagi bak", "down"),
]

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
DOWNSCALE = 0.25
UPSAMPLE = 0
DETECT_EVERY_N = 3


def select_face_model():
    if dlib is not None and getattr(dlib, "DLIB_USE_CUDA", False):
        return "cnn"
    return "hog"


FACE_MODEL = select_face_model()


def load_encodings():
    if not ENCODINGS_PATH.exists():
        return {"names": [], "encodings": []}
    with ENCODINGS_PATH.open("rb") as handle:
        data = pickle.load(handle)
    if "names" not in data or "encodings" not in data:
        return {"names": [], "encodings": []}
    return data


def save_encodings(data):
    with ENCODINGS_PATH.open("wb") as handle:
        pickle.dump(data, handle)


def safe_name(name):
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in ("_", "-", " "))
    cleaned = cleaned.strip().replace(" ", "_")
    return cleaned or "user"


def open_camera():
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    return cap


def draw_text(frame, text, y=30, color=(0, 255, 0)):
    cv2.putText(
        frame,
        text,
        (10, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        color,
        2,
        cv2.LINE_AA,
    )


def capture_samples(name, status_var):
    cap = open_camera()
    if not cap.isOpened():
        messagebox.showerror("Hata", "Kamera acilamadi.")
        return

    data = load_encodings()
    person_dir = IMAGES_DIR / safe_name(name)
    person_dir.mkdir(parents=True, exist_ok=True)

    captured = 0
    cancelled = False

    status_var.set("Kamera acik. Yuz kaydi basladi.")

    for prompt, tag in ANGLE_PROMPTS:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            locations = face_recognition.face_locations(
                rgb, number_of_times_to_upsample=UPSAMPLE, model=FACE_MODEL
            )
            location = locations[0] if len(locations) == 1 else None
            display = frame.copy()

            if location:
                top, right, bottom, left = location
                cv2.rectangle(display, (left, top), (right, bottom), (0, 255, 0), 2)
            else:
                draw_text(display, "Tek yuz goster", y=60, color=(0, 0, 255))

            draw_text(display, f"{prompt} - C: kaydet, Q: iptal", y=30)
            cv2.imshow("Yuz Kaydi", display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                cancelled = True
                break
            if key == ord("c"):
                if location is None:
                    continue
                encoding = face_recognition.face_encodings(rgb, [location])[0]

                timestamp = time.strftime("%Y%m%d_%H%M%S")
                image_path = person_dir / f"{timestamp}_{tag}.jpg"
                cv2.imwrite(str(image_path), frame)

                data["names"].append(name)
                data["encodings"].append(encoding)
                captured += 1
                break

        if cancelled:
            break

    cap.release()
    cv2.destroyAllWindows()

    if captured > 0:
        save_encodings(data)
        status_var.set(f"Yuz kaydi tamamlandi. {captured} ornek kaydedildi.")
        messagebox.showinfo("Bilgi", "Yuz kaydi tamamlandi.")
    else:
        status_var.set("Yuz kaydi iptal edildi.")


def recognize_face(status_var):
    data = load_encodings()
    if not data["encodings"]:
        messagebox.showinfo("Bilgi", "Once yuz kaydi yapin.")
        return

    cap = open_camera()
    if not cap.isOpened():
        messagebox.showerror("Hata", "Kamera acilamadi.")
        return

    status_var.set("Yuz tanima basladi.")
    recognized = None
    frame_index = 0
    last_faces = []

    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        display = frame.copy()

        if frame_index % DETECT_EVERY_N == 0:
            small = cv2.resize(frame, (0, 0), fx=DOWNSCALE, fy=DOWNSCALE)
            rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

            locations = face_recognition.face_locations(
                rgb_small, number_of_times_to_upsample=UPSAMPLE, model=FACE_MODEL
            )
            encodings = face_recognition.face_encodings(rgb_small, locations)

            last_faces = []
            scale = 1 / DOWNSCALE
            for (top, right, bottom, left), encoding in zip(locations, encodings):
                matches = face_recognition.compare_faces(
                    data["encodings"], encoding, tolerance=0.5
                )
                name = "Bilinmiyor"
                if matches:
                    distances = face_recognition.face_distance(
                        data["encodings"], encoding
                    )
                    best_index = int(np.argmin(distances))
                    if matches[best_index]:
                        name = data["names"][best_index]

                top = int(top * scale)
                right = int(right * scale)
                bottom = int(bottom * scale)
                left = int(left * scale)
                last_faces.append((top, right, bottom, left, name))

                if name != "Bilinmiyor":
                    recognized = name

        for top, right, bottom, left, name in last_faces:
            cv2.rectangle(display, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(
                display,
                name,
                (left, top - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

        draw_text(display, "Q: cikis", y=30)
        cv2.imshow("Yuz Tanima", display)

        if recognized:
            cv2.waitKey(500)
            break

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        frame_index += 1

    cap.release()
    cv2.destroyAllWindows()

    if recognized:
        status_var.set(f"Hosgeldin {recognized}")
        messagebox.showinfo("Hosgeldin", f"Hosgeldin {recognized}")
    else:
        status_var.set("Yuz tanima bitti.")


def main():
    root = tk.Tk()
    root.title("Yuz Tanima")
    root.geometry("360x220")
    root.resizable(False, False)

    status_var = tk.StringVar(value="Hazir.")

    title = tk.Label(root, text="Yuz Tanima", font=("Segoe UI", 16, "bold"))
    title.pack(pady=10)

    status_label = tk.Label(root, textvariable=status_var, wraplength=320)
    status_label.pack(pady=5)

    def on_register():
        name = simpledialog.askstring("Yuz Kaydi", "Isminiz:")
        if not name:
            status_var.set("Isim girilmedi.")
            return
        capture_samples(name.strip(), status_var)

    def on_recognize():
        recognize_face(status_var)

    button_frame = tk.Frame(root)
    button_frame.pack(pady=10)

    register_btn = tk.Button(button_frame, text="Yuz Kaydi", width=15, command=on_register)
    recognize_btn = tk.Button(
        button_frame, text="Yuz Tanima", width=15, command=on_recognize
    )

    register_btn.grid(row=0, column=0, padx=5)
    recognize_btn.grid(row=0, column=1, padx=5)

    root.mainloop()


if __name__ == "__main__":
    main()
