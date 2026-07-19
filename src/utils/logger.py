import os
import logging
from logging.handlers import RotatingFileHandler

def get_logger(log_dir="./log", log_file="app.log", max_bytes=500*100, backup_count=5):
    """
    표준 logging 모듈을 사용한 회전 파일 로거를 반환합니다.
    500 라인 기준을 대략 50KB(max_bytes)로 산정하여 회전시킵니다.
    """
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_path = os.path.join(log_dir, log_file)
    logger = logging.getLogger("TacitBridge")
    
    # 이미 핸들러가 추가된 경우 중복 추가 방지 (Streamlit reload 방어)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # RotatingFileHandler: max_bytes 초과 시 backup_count 만큼 파일 보존
        handler = RotatingFileHandler(
            log_path, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8'
        )
        
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        logger.info("LOGGER INITIALIZED (RotatingFileHandler)")
        
    return logger

class TkinterLogHandler(logging.Handler):
    """
    Tkinter Text 위젯과 연동하여 실시간 로그 콘솔을 출력해주는 로깅 핸들러
    """
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        log_entry = self.format(record) + "\n"
        self.text_widget.configure(state='normal')
        self.text_widget.insert('end', log_entry)
        self.text_widget.see('end')
        self.text_widget.configure(state='disabled')
