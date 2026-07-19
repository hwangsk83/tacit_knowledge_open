import ezdxf
import math

class DXFGeometryService:
    def __init__(self):
        pass

    def load_dxf(self, file_path: str):
        """
        DXF 도면 파일을 로드합니다.
        """
        try:
            return ezdxf.readfile(file_path)
        except IOError:
            raise FileNotFoundError(f"도면 파일을 찾을 수 없습니다: {file_path}")
        except ezdxf.DXFStructureError as e:
            raise ValueError(f"DXF 도면의 구조가 손상되었습니다: {e}")

    def get_all_circles(self, doc):
        """
        도면 내의 모든 CIRCLE 개체의 속성을 UI용으로 포맷팅하여 반환합니다.
        """
        msp = doc.modelspace()
        circles = []
        for entity in msp.query('CIRCLE'):
            circles.append({
                "handle": entity.dxf.handle,
                "center_x": entity.dxf.center.x,
                "center_y": entity.dxf.center.y,
                "radius": entity.dxf.radius
            })
        return circles

    def find_nearest_entity(self, click_x: float, click_y: float, doc, threshold=10.0):
        """
        사용자가 마우스로 클릭한 2D 좌표와 유클리드 거리가 가장 가까운 CIRCLE 개체를 반환합니다.
        """
        msp = doc.modelspace()
        closest_entity = None
        min_distance = float('inf')

        # 모든 CIRCLE 개체 조회
        for entity in msp.query('CIRCLE'):
            center = entity.dxf.center
            # 유클리드 거리 계산
            distance = math.sqrt((center.x - click_x)**2 + (center.y - click_y)**2)
            if distance < min_distance:
                min_distance = distance
                closest_entity = entity

        # 임계값(Threshold) 이내에 있을 경우에만 개체 데이터 포맷팅하여 반환
        if closest_entity and min_distance <= threshold:
            entity_info = {
                "type": "CIRCLE",
                "center": {"x": closest_entity.dxf.center.x, "y": closest_entity.dxf.center.y},
                "radius": closest_entity.dxf.radius,
                "handle": closest_entity.dxf.handle
            }
            return closest_entity, entity_info, min_distance
            
        return None, None, min_distance
