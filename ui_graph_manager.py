# ui_graph_manager.py
import pandas as pd
import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.ticker as ticker

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QListWidget, QAbstractItemView, QPushButton, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPageLayout 
from PyQt5.QtPrintSupport import QPrinter, QPrintPreviewDialog

import db_manager

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

class GraphManager(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.main_win = parent_window  
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        graph_ctrl = QHBoxLayout()
        
        self.data_selector = QListWidget()
        self.data_selector.setSelectionMode(QAbstractItemView.MultiSelection)
        self.data_selector.addItems(db_manager.DATA_LABELS)
        # 초기 선택값으로 실내온도, 외기온도 세팅
        self.data_selector.item(0).setSelected(True)
        self.data_selector.item(1).setSelected(True)
        self.data_selector.itemSelectionChanged.connect(self.update_graph)
        graph_ctrl.addWidget(self.data_selector)
        
        btn_layout = QVBoxLayout()
        self.btn_pdf = QPushButton("📕 그래프 PDF 저장")
        self.btn_pdf.clicked.connect(self.save_graph_to_pdf)
        btn_layout.addWidget(self.btn_pdf)
        graph_ctrl.addLayout(btn_layout)
        
        layout.addLayout(graph_ctrl)
        
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

    def update_graph(self):
        """[UI 기능] 선택된 날짜와 항목들을 db_manager에서 가공하여 차트로 매핑합니다."""
        selected_date = self.main_win.qdate.date().toString("yyyy-MM-dd")
        selected_items = [item.text() for item in self.data_selector.selectedItems()]
        
        self.figure.clear()
        if not selected_items:
            self.canvas.draw()
            return
            
        # 💡 리모델링 핵심: db_manager를 통해 원시 리스트를 수신 후 DataFrame으로 변환
        raw_rows = db_manager.get_graph_data_by_date(selected_date)
        if not raw_rows:
            self.canvas.draw()
            return
            
        df = pd.DataFrame(raw_rows)
        
        ax = self.figure.add_subplot(111)
        for item in selected_items:
            if item in df.columns:
                # 시간축에서 시(Hour) 정보만 파싱하여 트렌드 라인 생성
                df['hour'] = df['log_time'].apply(lambda x: int(x.split(':')[0]))
                ax.plot(df['hour'], df[item], marker='o', label=item)
                
        ax.set_title(f"{selected_date} 부하 분석 트렌드 차트")
        ax.set_xlabel("시간 (시)")
        ax.set_ylabel("측정값")
        ax.xaxis.set_major_locator(ticker.MultipleLocator(2)) # 2시간 단위로 그리드 표현
        ax.grid(True, linestyle='--')
        ax.legend(loc='upper right')
        
        self.figure.tight_layout()
        self.canvas.draw()

    def save_graph_to_pdf(self):
        """[UI 기능] 차트 화면을 가로형 고해상도 PDF 문서로 내려받습니다."""
        selected_date = self.main_win.qdate.date().toString("yyyy-MM-dd")
        default_filename = f"{selected_date}_부하분석그래프.pdf"
        
        filepath, _ = QFileDialog.getSaveFileName(self, "그래프를 PDF로 저장", default_filename, "PDF 문서 (*.pdf)")
        if filepath:
            try:
                printer = QPrinter(QPrinter.HighResolution)
                printer.setPageOrientation(QPageLayout.Landscape)
                printer.setOutputFormat(QPrinter.PdfFormat) 
                printer.setOutputFileName(filepath)         
                
                painter = QPainter()
                painter.begin(printer)
                
                pixmap = self.canvas.grab()
                rect = printer.pageRect(QPrinter.DevicePixel)
                
                size = pixmap.size()
                size.scale(rect.size(), Qt.KeepAspectRatio)
                
                painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
                painter.setWindow(pixmap.rect())
                painter.drawPixmap(0, 0, pixmap)
                painter.end()
                
                QMessageBox.information(self, "저장 완료", f"그래프가 PDF 문서로 정상 저장되었습니다.\n경로: {filepath}")
            except Exception as e:
                QMessageBox.critical(self, "저장 실패", f"PDF 파일 생성 중 치명적 오류 발생:\n{e}")