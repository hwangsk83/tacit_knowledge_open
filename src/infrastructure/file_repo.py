import os
import shutil

class FileRepository:
    def __init__(self, temp_dir="./temp", log_dir="./log"):
        self.temp_dir = temp_dir
        self.log_dir = log_dir
        self._ensure_directories()

    def _ensure_directories(self):
        """
        필요한 디렉토리 구조를 물리적으로 강제 생성합니다.
        """
        for directory in [self.temp_dir, self.log_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)

    def write_temp_file(self, content: str, filename: str) -> str:
        """
        임시 파일 영역에 데이터를 기록하고 전체 경로를 리턴합니다.
        """
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return file_path

    def delete_file(self, file_path: str):
        """
        안전하게 단일 파일을 제거합니다.
        """
        if os.path.exists(file_path):
            os.remove(file_path)

    def save_output_dxf(self, doc, target_path: str) -> str:
        """
        메타데이터가 추가된 DXF 파일을 지정된 경로에 직접 저장하고 그 경로를 리턴합니다.
        """
        doc.saveas(target_path)
        return target_path
