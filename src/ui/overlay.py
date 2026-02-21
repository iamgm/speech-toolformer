import sys
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

class ModernOverlay(QWidget):
    def __init__(self):
        super().__init__()
        
        # конфиг ui
        self.fixed_width = 500
        self.base_height = 90
        self.margin_x = 30
        self.margin_y = 80
        self.border_radius = 16
        
        # цвета
        self.colors = {
            "idle": QColor("#D2D1D1"),
            "listening": QColor("#FF3333"),
            "processing": QColor("#FFD700"),
            "success": QColor("#00FF00"),
            "chat": QColor("#00BFFF"),
            "error": QColor("#FF00FF")
        }
        self.current_accent = self.colors["idle"]
        
        # флаги
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool | 
            Qt.WindowDoesNotAcceptFocus 
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # КОНТЕНТ
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(20, 15, 20, 15)
        self.setLayout(self.layout)

        # статус
        self.lbl_status = QLabel("READY")
        self.lbl_status.setStyleSheet("""
            color: #DDDDDD; 
            font-weight: 800; 
            font-size: 11px; 
            letter-spacing: 2px;
            text-transform: uppercase;
            background-color: transparent; 
        """)
        self.lbl_status.setAlignment(Qt.AlignRight | Qt.AlignTop)
        self.layout.addWidget(self.lbl_status)

        # Текст
        self.lbl_text = QLabel("...")
        self.lbl_text.setStyleSheet("""
            color: white; 
            font-family: 'Segoe UI', sans-serif;
            font-weight: 600; 
            font-size: 16px;
            background-color: transparent;
        """)
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.layout.addWidget(self.lbl_text)

        # АНИМАЦИИ
        self.anim_opacity = QPropertyAnimation(self, b"windowOpacity")
        self.anim_opacity.setDuration(200)

        # Пульсация
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self._animate_pulse)
        self.pulse_val = 0
        self.pulse_dir = 1

        # драг-н-дроп
        self.dragging = False
        self.drag_pos = QPoint()

        self.resize(self.fixed_width, self.base_height)
        self.move_to_bottom_right()

    def move_to_bottom_right(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.width() - self.width() - self.margin_x
        y = screen.height() - self.height() - self.margin_y
        self.move(x, y)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False

    def _animate_pulse(self):
        self.pulse_val += 8 * self.pulse_dir
        if self.pulse_val >= 100: self.pulse_dir = -1
        if self.pulse_val <= 0:   self.pulse_dir = 1
        self.update() # Вызывает paintEvent

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(2, 2, -2, -2)
        path = QPainterPath()
        path.addRoundedRect(rect, self.border_radius, self.border_radius)

        # фон 
        painter.setBrush(QColor(20, 20, 20, 140)) # Alpha 200/255
        painter.setPen(Qt.NoPen)
        painter.drawPath(path)

        # рамка - glow
        pen = QPen(self.current_accent)
        
        if self.pulse_timer.isActive():
            glow_width = 10.0 + (self.pulse_val / 30.0) 
            glow_alpha = 150 + self.pulse_val          
            color = QColor(self.current_accent)
            color.setAlpha(min(255, int(glow_alpha)))
            pen.setColor(color)
            pen.setWidthF(glow_width)
        else:
            pen.setWidth(3)

        # painter.setStroke(True)  УДАЛЕНО! ЭТО ВЫЗЫВАЛО КРАШ
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    # API
    def update_status(self, text: str, color_hex: str):
        self.lbl_status.setText(text.upper())
        
        # Меняем цвет
        if "Listening" in text:
            self.current_accent = self.colors["listening"]
            if not self.pulse_timer.isActive(): self.pulse_timer.start(30)
        elif "Thinking" in text:
            self.current_accent = self.colors["processing"]
            self.pulse_timer.stop()
        elif "Chat" in text:
            self.current_accent = self.colors["chat"]
            self.pulse_timer.stop()
        elif "Error" in text:
            self.current_accent = self.colors["error"]
            self.pulse_timer.stop()
        elif "Pasting" in text:
            self.current_accent = self.colors["success"]
            self.pulse_timer.stop()
        else:
            self.current_accent = self.colors["idle"]
            self.pulse_timer.stop()
        
        self.update() # Принудительная перерисовка



    def update_text(self, text: str):
        self.lbl_text.setText(text)
        
        # 1. Считаем новую высоту
        # +80 пикселей на отступы и статус
        new_height = max(self.base_height, self.lbl_text.sizeHint().height() + 80)
        
        # 2. Получаем размеры экрана
        screen = QApplication.primaryScreen().availableGeometry()
        
        # 3. АБСОЛЮТНЫЙ РАСЧЕТ ПОЗИЦИИ
        # X = Ширина экрана - Ширина окна - Отступ справа
        target_x = screen.width() - self.fixed_width - self.margin_x
        # Y = Высота экрана - Новая высота окна - Отступ снизу
        target_y = screen.height() - new_height - self.margin_y
        
        # 4. Применяем (только если что-то изменилось)
        if new_height != self.height() or target_y != self.y():
            self.setGeometry(target_x, target_y, self.fixed_width, new_height)
        
        self.repaint()
    def update_text(self, text: str):
        self.lbl_text.setText(text)
        
        # считаем новую высоту
        # +80 пикселей на отступы и статус
        new_height = max(self.base_height, self.lbl_text.sizeHint().height() + 80)
        
        # получаем размеры экрана
        screen = QApplication.primaryScreen().availableGeometry()
        
        # абс. расчет позиции
        # x = ширина экрана - ширина окна - отступ справа
        target_x = screen.width() - self.fixed_width - self.margin_x
        # y = высота экрана - новая высота окна - отступ снизу
        target_y = screen.height() - new_height - self.margin_y
        
        # применяем - только если что-то изменилось
        if new_height != self.height() or target_y != self.y():
            self.setGeometry(target_x, target_y, self.fixed_width, new_height)
        
        self.repaint()
        


    def show_overlay(self):
        # отключаем старые связи анимации
        try:
            self.anim_opacity.finished.disconnect()
        except Exception:
            pass

        # если окно уже видно, не трогаем - защита от мерцания
        if self.isVisible() and self.windowOpacity() > 0.9:
            return

        # сбрасываем текст и размер в исходное состояние
        # self.resize(self.fixed_width, self.base_height)
        
        #  fix  сползания - якорим позицию перед показом
        self.move_to_bottom_right()

        self.setWindowOpacity(0)
        self.show()
        
        self.anim_opacity.setStartValue(0)
        self.anim_opacity.setEndValue(1)
        self.anim_opacity.start()
        
        
    def hide_overlay(self):
        # отключаем старые связи
        try:
            self.anim_opacity.finished.disconnect()
        except Exception:
            pass

        # настраиваем затухание
        self.anim_opacity.setStartValue(1)
        self.anim_opacity.setEndValue(0)
        
        # подключаем скрытие ТОЛЬКО для этого запуска
        self.anim_opacity.finished.connect(self.hide)
        self.anim_opacity.start()


# alias для main.py
OverlayWindow = ModernOverlay

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ModernOverlay()
    w.show_overlay()
    QTimer.singleShot(1000, lambda: w.update_status("Listening...", ""))
    QTimer.singleShot(1000, lambda: w.update_text("Слушаю твою команду..."))
    sys.exit(app.exec())
