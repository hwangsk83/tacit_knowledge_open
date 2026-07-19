import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.widgets import RectangleSelector
import os
import json
import logging
import threading

from services.geometry_service import DXFGeometryService
from services.xdata_service import DXFXDataService
from services.gemini_service import GeminiAPIService
from infrastructure.file_repo import FileRepository
from utils.logger import get_logger, TkinterLogHandler

class TacitBridgeGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TacitBridge-DXF (Design Know-how Viewer)")
        self.root.geometry("1400x850")
        
        self.logger = get_logger()
        self.repo = FileRepository()
        self.geom_service = DXFGeometryService()
        self.xdata_service = DXFXDataService()
        
        self.doc, self.circles = None, []
        self.selected_handles = set()
        self.heritage_handles = set()
        self.original_filename = "drawing.dxf"
        self.selector, self.ctrl_pressed = None, False
        
        ttk.Style().theme_use('clam')
        self.create_widgets()
        self.setup_logging()
        
        for k in ["<KeyPress-Control_L>", "<KeyPress-Control_R>"]: self.root.bind(k, lambda e: self.set_ctrl(True))
        for k in ["<KeyRelease-Control_L>", "<KeyRelease-Control_R>"]: self.root.bind(k, lambda e: self.set_ctrl(False))
        self.logger.info("데스크톱 GUI 프로그램 및 설계 노하우 뷰어 가동됨.")

    def set_ctrl(self, val):
        self.ctrl_pressed = val

    def setup_logging(self):
        gui_handler = TkinterLogHandler(self.log_display)
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
        gui_handler.setFormatter(formatter)
        logging.getLogger("TacitBridge").addHandler(gui_handler)

    def create_widgets(self):
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        left_frame = ttk.LabelFrame(main_pane, text="📐 2D CAD 도면 형상 (클릭 토글 / Ctrl 드래그 다중 스냅 / 녹색 실선: 설계 노하우 내장)")
        main_pane.add(left_frame, weight=5)
        
        self.fig, self.ax = plt.subplots(figsize=(8, 8))
        self.fig.patch.set_facecolor('#f0f0f0') 
        self.canvas = FigureCanvasTkAgg(self.fig, master=left_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=2)
        
        file_box = ttk.LabelFrame(right_frame, text="📁 DXF 파일 로드")
        file_box.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(file_box, text="도면 로드 (Load DXF)", command=self.load_dxf_file).pack(fill=tk.X, padx=5, pady=5)
        
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tab_inject = ttk.Frame(self.notebook)
        self.notebook.add(tab_inject, text="💡 설계 노하우 주입")
        
        api_box = ttk.LabelFrame(tab_inject, text="🔑 Gemini API 설정")
        api_box.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(api_box, text="API Key:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.api_key_entry = ttk.Entry(api_box, show="*", width=30)
        self.api_key_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        env_key = os.environ.get("GEMINI_API_KEY", "")
        if env_key: self.api_key_entry.insert(0, env_key)
            
        self.info_box = ttk.LabelFrame(tab_inject, text="📍 선택된 원형 개체 정보 (다중 선택 가능)")
        self.info_box.pack(fill=tk.X, padx=5, pady=5)
        self.lbl_handle = ttk.Label(self.info_box, text="Handle: 선택 없음", font=("Arial", 10, "bold"))
        self.lbl_handle.pack(anchor='w', padx=5, pady=2)
        self.lbl_center = ttk.Label(self.info_box, text="중심 좌표: -")
        self.lbl_center.pack(anchor='w', padx=5, pady=2)
        self.lbl_radius = ttk.Label(self.info_box, text="반경: -")
        self.lbl_radius.pack(anchor='w', padx=5, pady=2)
        
        comment_box = ttk.LabelFrame(tab_inject, text="💡 제조 설계 노하우 의견 입력")
        comment_box.pack(fill=tk.X, padx=5, pady=5)
        self.comment_text = tk.Text(comment_box, height=5)
        self.comment_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.btn_compile_save = ttk.Button(comment_box, text="💾 분석 결과 주입 및 도면 저장 (Analyze & Save)", command=self.compile_and_save)
        self.btn_compile_save.pack(fill=tk.X, padx=5, pady=5)
        
        result_box = ttk.LabelFrame(tab_inject, text="📜 주입된 설계 노하우 정보")
        result_box.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.json_display = ScrolledText(result_box, height=12, state='disabled')
        self.json_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tab_validate = ttk.Frame(self.notebook)
        self.notebook.add(tab_validate, text="📜 설계 노하우 조회")
        ttk.Label(tab_validate, text="도면에 영구 보존된 설계 노하우(XData) 목록입니다.\n더블 클릭 시 해당 원형 개체로 자동 스냅(Snap)합니다.", justify=tk.LEFT).pack(anchor='w', padx=10, pady=5)
        
        cols = ("Handle", "Actual", "Rationale")
        self.tree_violations = ttk.Treeview(tab_validate, columns=cols, show="headings", height=15)
        for col, width, anchor in [("Handle", 100, 'center'), ("Actual", 100, 'center'), ("Rationale", 300, 'w')]:
            self.tree_violations.heading(col, text=col if col != "Rationale" else "설계 노하우 (Rationale)")
            self.tree_violations.column(col, width=width, anchor=anchor)
        self.tree_violations.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree_violations.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        bottom_frame = ttk.LabelFrame(self.root, text="📝 실시간 시스템 트레이스 로그")
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)
        self.log_display = ScrolledText(bottom_frame, height=5, state='disabled')
        self.log_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def log_info(self, msg):
        self.logger.info(msg)

    def load_dxf_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("DXF Files", "*.dxf")])
        if not file_path: return
        self.original_filename = os.path.basename(file_path)
        self.log_info(f"도면 로딩 시도: {self.original_filename}")
        
        try:
            self.doc = self.geom_service.load_dxf(file_path)
            self.circles = self.geom_service.get_all_circles(self.doc)
            self.selected_handles.clear()
            self.log_info(f"도면 로드 완료. CIRCLE 수: {len(self.circles)}개")
            
            self.scan_dxf_heritage()
            self.redraw_dxf()
            self.update_selection_ui()
            if not self.circles: messagebox.showwarning("경고", "도면에 원(CIRCLE) 개체가 존재하지 않습니다.")
        except Exception as e:
            messagebox.showerror("에러", f"도면 로드에 실패했습니다:\n{e}")
            self.logger.error(f"도면 로드 실패: {e}")

    def scan_dxf_heritage(self):
        self.heritage_handles.clear()
        for item in self.tree_violations.get_children(): self.tree_violations.delete(item)
        if not self.doc: return
            
        heritage_count = 0
        for c in self.circles:
            handle = c['handle']
            try:
                rules = self.xdata_service.get_xdata_by_handle(self.doc, handle)
                if rules:
                    self.heritage_handles.add(handle)
                    rationale = rules.get("rationale", "주입된 설계 지식 노하우")
                    self.tree_violations.insert("", tk.END, values=(handle, f"{c['radius']:.2f}", rationale))
                    heritage_count += 1
            except Exception as e:
                self.logger.error(f"설계 노하우 스캔 실패 (Handle: {handle}): {e}")
                
        if heritage_count > 0:
            self.log_info(f"📜 설계 노하우 스캔 완료: 설계 노하우가 깃든 개체 {heritage_count}개가 확인되었습니다. (녹색 실선 표시)")
            self.notebook.select(1)
        else:
            self.log_info("도면 내에 내장된 설계 노하우(XData) 정보가 없습니다.")

    def on_tree_select(self, event):
        selected_items = self.tree_violations.selection()
        if not selected_items: return
        item_values = self.tree_violations.item(selected_items[0], "values")
        if item_values:
            handle = item_values[0]
            self.selected_handles = {handle}
            self.log_info(f"설계 노하우 개체 선택 스냅: Handle={handle} | 설계 의도(Rationale): {item_values[2]}")
            self.update_selection_ui()
            self.redraw_dxf()

    def on_select(self, eclick, erelease):
        if not self.doc or eclick.xdata is None or erelease.xdata is None: return
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        
        if dx < 1.0 and dy < 1.0:
            _, nearest_info, _ = self.geom_service.find_nearest_entity(x1, y1, self.doc)
            if nearest_info:
                handle = nearest_info["handle"]
                if self.ctrl_pressed:
                    self.selected_handles.remove(handle) if handle in self.selected_handles else self.selected_handles.add(handle)
                    self.log_info(f"개체 선택 토글: {handle}")
                else:
                    self.selected_handles = {handle}
                    self.log_info(f"개체 단일 선택: {handle}")
            elif not self.ctrl_pressed:
                self.selected_handles.clear()
                self.log_info("선택 해제 완료.")
        else:
            xmin, xmax = min(x1, x2), max(x1, x2)
            ymin, ymax = min(y1, y2), max(y1, y2)
            box_selected = [c['handle'] for c in self.circles if xmin <= c['center_x'] <= xmax and ymin <= c['center_y'] <= ymax]
            if box_selected:
                if self.ctrl_pressed:
                    self.selected_handles.update(box_selected)
                    self.log_info(f"영역 드래그 누적 추가 완료: {len(box_selected)}개 개체 추가됨.")
                else:
                    self.selected_handles = set(box_selected)
                    self.log_info(f"영역 드래그 선택 완료: {len(box_selected)}개 개체 선택됨.")
            else:
                self.log_info("드래그 영역 내에 원형 개체가 없습니다.")
        self.update_selection_ui()
        self.redraw_dxf()

    def display_formatted_xdata(self, xdata_dict):
        self.json_display.configure(state='normal')
        self.json_display.delete("1.0", tk.END)
        if not xdata_dict:
            self.json_display.insert(tk.END, "[설계 노하우 정보가 없습니다.]")
            self.json_display.configure(state='disabled')
            return
        rationale = xdata_dict.get("rationale", xdata_dict.get("description", "제시된 설계 의도가 없습니다."))
        self.json_display.insert(tk.END, f"📌 설계 의도 (Rationale):\n{rationale}\n\n")
        params = xdata_dict.get("parameters", xdata_dict.get("parameter", {}))
        if params:
            self.json_display.insert(tk.END, f"⚙️ 적용된 제약 조건 파라미터:\n")
            for k, v in params.items(): self.json_display.insert(tk.END, f"  • {k}: {v}\n")
        else:
            self.json_display.insert(tk.END, f"⚙️ 제약 조건 파라미터 정보 없음.\n")
        self.json_display.configure(state='disabled')

    def update_selection_ui(self):
        if not self.selected_handles:
            self.lbl_handle.configure(text="Handle: 선택 없음", font=("Arial", 10, "bold"))
            self.lbl_center.configure(text="중심 좌표: -")
            self.lbl_radius.configure(text="반경: -")
            self.json_display.configure(state='normal')
            self.json_display.delete("1.0", tk.END)
            self.json_display.insert(tk.END, "[선택된 개체가 없습니다. 도면 영역을 클릭하거나 드래그하여 선택하세요.]\n\n(Tip: Ctrl 키를 누른 상태에서 클릭/드래그 시 복수 선택이 누적됩니다.)")
            self.json_display.configure(state='disabled')
            return

        if len(self.selected_handles) == 1:
            handle = list(self.selected_handles)[0]
            c_info = next((c for c in self.circles if c['handle'] == handle), None)
            if c_info:
                self.lbl_handle.configure(text=f"Handle: {handle} (단일 선택)", font=("Arial", 10, "bold"))
                self.lbl_center.configure(text=f"중심 좌표: ({c_info['center_x']:.2f}, {c_info['center_y']:.2f})")
                self.lbl_radius.configure(text=f"반경: {c_info['radius']:.2f}")
                existing_xdata = self.xdata_service.get_xdata_by_handle(self.doc, handle)
                self.display_formatted_xdata(existing_xdata)
        else:
            self.lbl_handle.configure(text=f"Handle: 다중 선택됨 ({len(self.selected_handles)}개)", font=("Arial", 10, "bold"))
            radii = [c['radius'] for c in self.circles if c['handle'] in self.selected_handles]
            handles_str = ", ".join(list(self.selected_handles)[:5]) + ("..." if len(self.selected_handles) > 5 else "")
            self.lbl_center.configure(text=f"선택된 Handles: {handles_str}")
            self.lbl_radius.configure(text=f"반경 범위: {min(radii):.2f} ~ {max(radii):.2f}")
            first_handle = list(self.selected_handles)[0]
            existing_xdata = self.xdata_service.get_xdata_by_handle(self.doc, first_handle)
            self.json_display.configure(state='normal')
            self.json_display.delete("1.0", tk.END)
            self.json_display.insert(tk.END, f"[다중 선택 모드 - 총 {len(self.selected_handles)}개 개체 일괄 처리]\n\n")
            if existing_xdata:
                self.json_display.insert(tk.END, f"대표 개체({first_handle}) 노하우 정보:\n")
                self.json_display.configure(state='disabled')
                self.display_formatted_xdata(existing_xdata)
            else:
                self.json_display.insert(tk.END, "기존 데이터 없음. 설계 의견 입력 후 분석 및 저장을 진행하세요.")
                self.json_display.configure(state='disabled')

    def redraw_dxf(self):
        self.ax.clear()
        for line in self.doc.modelspace().query('LINE'):
            self.ax.plot([line.dxf.start.x, line.dxf.end.x], [line.dxf.start.y, line.dxf.end.y], color="grey", alpha=0.5, linewidth=1)
        
        for c in self.circles:
            handle = c['handle']
            is_sel, has_hr = handle in self.selected_handles, handle in self.heritage_handles
            color, lw = ("red", 2.5) if is_sel else (("green", 2.0) if has_hr else ("blue", 1.0))
            self.ax.add_patch(plt.Circle((c['center_x'], c['center_y']), c['radius'], color=color, fill=False, linewidth=lw))
            
        self.ax.set_aspect('equal', adjustable='datalim')
        self.ax.grid(True, linestyle="--", alpha=0.5)
        self.fig.tight_layout() 
        self.canvas.draw()
        
        self.selector = RectangleSelector(self.ax, self.on_select, useblit=True, button=[1], minspanx=5, minspany=5, spancoords='data', interactive=True)

    def compile_and_save(self):
        if not self.doc or not self.selected_handles:
            messagebox.showwarning("경고", "먼저 도면 파일을 열고 마우스 드래그 혹은 클릭으로 개체를 선택해 주세요.")
            return
        comment = self.comment_text.get("1.0", tk.END).strip()
        if not comment:
            messagebox.showwarning("경고", "설계 노하우 의견을 입력하세요.")
            return
        api_key = self.api_key_entry.get().strip() or os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            messagebox.showerror("에러", "Gemini API 키가 입력되지 않았습니다. 환경변수 GEMINI_API_KEY 혹은 설정 패널을 확인해 주세요.")
            return
            
        self.btn_compile_save.configure(state='disabled')
        self.log_info(f"Gemini API 호출 및 설계 노하우 분석 컴파일을 시작합니다. (비동기 수행)")
        selected_entities = [c for c in self.circles if c['handle'] in self.selected_handles]
        
        def run():
            try:
                api_service = GeminiAPIService(api_key=api_key)
                rule_json = api_service.compile_constraint(comment, selected_entities)
                self.root.after(0, self.on_analysis_success_and_save, rule_json)
            except Exception as e:
                self.root.after(0, self.on_analysis_error, str(e))
        threading.Thread(target=run, daemon=True).start()

    def on_analysis_success_and_save(self, rule_json):
        self.btn_compile_save.configure(state='normal')
        if isinstance(rule_json, list):
            rule_json = rule_json[0] if len(rule_json) > 0 else {}
        self.display_formatted_xdata(rule_json)
        
        try:
            injected_count = 0
            for handle in self.selected_handles:
                if self.xdata_service.inject_xdata_by_handle(self.doc, handle, rule_json): injected_count += 1
            self.log_info(f"총 {injected_count}개 개체에 XData 주입 완료. 저장 다이얼로그를 오픈합니다.")
            
            default_out = self.original_filename
            if not default_out.startswith("augmented_"): default_out = f"augmented_{default_out}"
            save_path = filedialog.asksaveasfilename(initialfile=default_out, defaultextension=".dxf", filetypes=[("DXF Files", "*.dxf")])
            if not save_path:
                self.log_info("저장이 취소되었습니다.")
                return
                
            output_path = self.repo.save_output_dxf(self.doc, save_path)
            self.original_filename = os.path.basename(output_path)
            
            self.scan_dxf_heritage()
            self.redraw_dxf()
            self.update_selection_ui()
            
            messagebox.showinfo("성공", f"설계 노하우가 총 {injected_count}개 개체에 주입 및 저장 완료되었습니다!\n경로: {output_path}")
            self.log_info(f"도면 일괄 저장 및 설계 노하우 목록 갱신 완료: {output_path}")
        except Exception as e:
            messagebox.showerror("에러", f"도면 주입 및 저장 중 오류 발생:\n{e}")
            self.logger.error(f"주입/저장 실패 에러: {e}")

    def on_analysis_error(self, err_msg):
        self.btn_compile_save.configure(state='normal')
        messagebox.showerror("분석 실패", f"Gemini API 분석 실패:\n{err_msg}")
        self.logger.error(f"분석 실패 에러: {err_msg}")

if __name__ == "__main__":
    root = tk.Tk()
    app = TacitBridgeGUI(root)
    root.mainloop()
