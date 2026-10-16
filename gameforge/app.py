"""GameForge local-first PySide6 desktop application."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMainWindow, QMessageBox, QPushButton,
    QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

ROOT = Path.cwd()
OUT = ROOT / "outputs"


def safe_name(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", text.strip()).strip("_")[:64] or "asset"


class Worker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, kind: str, params: dict):
        super().__init__()
        self.kind, self.params = kind, params

    def run(self):
        try:
            if self.kind == "voice":
                from kokoro import KPipeline
                import numpy as np
                import soundfile as sf

                p = self.params
                pipeline = KPipeline(lang_code="a")
                chunks = [
                    audio for _, _, audio in pipeline(
                        p["text"], voice=p["voice"], speed=1.0,
                        split_pattern=r"\n+"
                    )
                ]
                if not chunks:
                    raise RuntimeError("The voice model returned no audio.")
                folder = OUT / "voice"
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / (safe_name(p["name"]) + ".wav")
                i = 2
                while path.exists():
                    path = folder / (safe_name(p["name"]) + f"_{i}.wav")
                    i += 1
                sf.write(path, np.concatenate(chunks), 24000)
            else:
                import torch
                from diffusers import StableDiffusionPipeline

                p = self.params
                if not torch.cuda.is_available():
                    raise RuntimeError("CUDA GPU unavailable. Install CUDA-enabled PyTorch.")
                pipe = StableDiffusionPipeline.from_pretrained(
                    p["model"], torch_dtype=torch.float16,
                    safety_checker=None, requires_safety_checker=False
                )
                pipe.enable_attention_slicing()
                pipe.enable_model_cpu_offload()
                image = pipe(
                    p["prompt"], width=p["size"], height=p["size"],
                    num_inference_steps=25
                ).images[0]
                folder = OUT / "art"
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / (safe_name(p["name"]) + ".png")
                i = 2
                while path.exists():
                    path = folder / (safe_name(p["name"]) + f"_{i}.png")
                    i += 1
                image.save(path)
                del pipe
            self.finished.emit(str(path.resolve()))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class GameForge(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GameForge — AI Game Asset Studio")
        self.resize(1050, 720)
        self.thread = None
        self.worker = None
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        tabs.addTab(self.voice_tab(), "Voice Studio")
        tabs.addTab(self.art_tab(), "Art Studio")
        tabs.addTab(self.library_tab(), "Asset Library")
        self.statusBar().showMessage("Ready — models download on first generation")
        self.setStyleSheet("""
            QWidget { background: #171c29; color: #ecf0ff; font-size: 13px; }
            QLineEdit, QTextEdit, QComboBox, QSpinBox, QListWidget {
                background: #242c3e; border: 1px solid #43516a;
                border-radius: 6px; padding: 7px;
            }
            QPushButton { background: #6559df; padding: 10px 16px;
                border: 0; border-radius: 6px; font-weight: 600; }
            QPushButton:hover { background: #8178f0; }
            QPushButton:disabled { background: #41445a; }
            QTabBar::tab { padding: 13px 20px; }
            QTabBar::tab:selected { background: #323c55; }
        """)

    def voice_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("VOICE STUDIO  •  Generate dialogue for your characters"))
        form = QFormLayout()
        self.voice_name = QLineEdit("hero_intro")
        self.voice_select = QComboBox()
        self.voice_select.addItems([
            "af_heart", "af_bella", "af_nicole", "af_sarah",
            "am_adam", "am_michael", "bf_emma", "bm_george"
        ])
        self.voice_text = QTextEdit()
        self.voice_text.setPlaceholderText("Enter dialogue to generate...")
        self.voice_text.setPlainText("The kingdom may fall, but our courage never will.")
        form.addRow("File name", self.voice_name)
        form.addRow("Voice", self.voice_select)
        form.addRow("Dialogue", self.voice_text)
        layout.addLayout(form)
        self.voice_button = QPushButton("Generate WAV")
        self.voice_button.clicked.connect(self.generate_voice)
        layout.addWidget(self.voice_button)
        layout.addStretch()
        return w

    def art_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("ART STUDIO  •  Generate concept art and game assets"))
        form = QFormLayout()
        self.art_name = QLineEdit("knight_portrait")
        self.model = QLineEdit("runwayml/stable-diffusion-v1-5")
        self.art_prompt = QTextEdit()
        self.art_prompt.setPlainText(
            "Portrait of a medieval fantasy knight, expressive pixel art, "
            "GBA tactics RPG inspired aesthetic, detailed armor, neutral backdrop"
        )
        self.size = QSpinBox()
        self.size.setRange(256, 768)
        self.size.setSingleStep(64)
        self.size.setValue(512)
        form.addRow("File name", self.art_name)
        form.addRow("Diffusers model ID", self.model)
        form.addRow("Prompt", self.art_prompt)
        form.addRow("Image size (square)", self.size)
        layout.addLayout(form)
        self.art_button = QPushButton("Generate PNG")
        self.art_button.clicked.connect(self.generate_art)
        layout.addWidget(self.art_button)
        layout.addWidget(QLabel(
            "Tip: Start at 512 × 512 on 6 GB VRAM. "
            "AI output may require cleanup before use as sprites."
        ))
        layout.addStretch()
        return w

    def library_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("ASSET LIBRARY  •  Generated files"))
        self.files = QListWidget()
        self.files.itemDoubleClicked.connect(
            lambda item: QDesktopServices.openUrl(QUrl.fromLocalFile(item.text()))
        )
        layout.addWidget(self.files)
        buttons = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        open_folder = QPushButton("Open output folder")
        open_folder.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(OUT.resolve())))
        )
        buttons.addWidget(refresh)
        buttons.addWidget(open_folder)
        layout.addLayout(buttons)
        self.refresh()
        return w

    def refresh(self):
        OUT.mkdir(exist_ok=True)
        self.files.clear()
        for path in sorted(OUT.rglob("*")):
            if path.is_file() and path.suffix.lower() in (".wav", ".png"):
                self.files.addItem(str(path.resolve()))

    def generate_voice(self):
        text = self.voice_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Missing dialogue", "Enter dialogue first.")
            return
        self.start_job("voice", {
            "text": text, "voice": self.voice_select.currentText(),
            "name": self.voice_name.text()
        })

    def generate_art(self):
        prompt = self.art_prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Missing prompt", "Enter an art prompt first.")
            return
        self.start_job("art", {
            "prompt": prompt, "model": self.model.text().strip(),
            "size": self.size.value(), "name": self.art_name.text()
        })

    def start_job(self, kind, params):
        self.voice_button.setEnabled(False)
        self.art_button.setEnabled(False)
        self.statusBar().showMessage(f"Generating {kind}… first run may download models")
        self.thread = QThread()
        self.worker = Worker(kind, params)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.job_success)
        self.worker.failed.connect(self.job_failure)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.job_cleanup)
        self.thread.start()

    def job_success(self, path):
        self.statusBar().showMessage(f"Saved: {path}")
        self.refresh()
        QMessageBox.information(self, "Asset generated", f"Saved to:\n{path}")

    def job_failure(self, error):
        self.statusBar().showMessage("Generation failed")
        QMessageBox.critical(self, "Generation error", error)

    def job_cleanup(self):
        self.voice_button.setEnabled(True)
        self.art_button.setEnabled(True)
        self.thread = None
        self.worker = None


def main():
    app = QApplication(sys.argv)
    window = GameForge()
    window.show()
    sys.exit(app.exec())
