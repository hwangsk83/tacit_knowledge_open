import ezdxf
import json

class DXFXDataService:
    def __init__(self, app_id="TACIT_BRIDGE"):
        self.app_id = app_id

    def inject_xdata_by_handle(self, doc, handle_id: str, rule_dict: dict) -> bool:
        """
        주어진 Handle ID를 가진 개체에 암묵지 JSON 규칙 데이터를 XData로 주입합니다.
        """
        # 1. AppID 등록 검증
        if self.app_id not in doc.appids:
            doc.appids.new(self.app_id)

        # 2. 핸들 ID로 엔티티db에서 개체 검색
        entity = doc.entitydb.get(handle_id)
        if not entity:
            raise ValueError(f"도면 내에 해당하는 Handle ID를 가진 개체가 없습니다: {handle_id}")

        # 3. JSON 문자열 직렬화
        json_str = json.dumps(rule_dict, ensure_ascii=False)

        # 4. XData 포맷팅 및 주입 (1001: AppID, 1000: ASCII String)
        xdata_tags = [(1001, self.app_id), (1000, json_str)]
        entity.set_xdata(self.app_id, xdata_tags)
        return True

    def get_xdata_by_handle(self, doc, handle_id: str) -> dict:
        """
        주어진 Handle ID를 가진 개체에서 암묵지 JSON 데이터를 복원합니다.
        """
        entity = doc.entitydb.get(handle_id)
        if not entity:
            raise ValueError(f"개체를 찾을 수 없습니다: {handle_id}")

        if not entity.has_xdata(self.app_id):
            return None

        # ezdxf는 get_xdata 호출 시 1001(AppID) 태그를 제외한 1000번대 데이터 태그 리스트만 반환함
        xdata_list = entity.get_xdata(self.app_id)
        if not xdata_list:
            return None

        try:
            json_str = xdata_list[0][1]
            data = json.loads(json_str)
            # 방어적 코드: 만약 리스트 형태로 감싸져 있다면 첫 번째 요소를 반환
            if isinstance(data, list):
                if len(data) > 0:
                    data = data[0]
                else:
                    data = {}
            return data
        except (IndexError, TypeError, json.JSONDecodeError) as e:
            raise ValueError(f"XData 내 JSON 데이터의 구조가 손상되었습니다: {e}")
