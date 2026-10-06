"""이미지 세탁소 — 일반 사용자용 경로.

왜 별도 라우터인가
    세탁 기능의 실제 구현은 settings.py 에 있는데, settings 라우터는 통째로
    `verify_admin` 으로 마운트돼 있다(관리자 전용 항목들이 섞여 있어서다).
    그런데 설치형(카페 전용판)은 로그인이 없어 자동 발급 토큰의 role 이 'advertiser' 라
    이미지 세탁소의 모든 호출이 403 으로 막혔다 — 기능이 통째로 안 됐다.

    구현을 옮겨 적으면 두 벌이 되어 한쪽만 고치는 사고가 난다.
    그래서 같은 처리 함수를 '로그인만 요구하는' 이 라우터에 다시 매달아 준다.

경로
    /api/image-wash/upload            (구 /api/settings/wash-upload)
    /api/image-wash/library           (구 /api/settings/wash-library)
    /api/image-wash/library/save
    /api/image-wash/library/stage
    /api/image-wash/library/{filename}
"""

from fastapi import APIRouter

from . import settings as _s

router = APIRouter(prefix="/api/image-wash", tags=["Image Wash"])

# settings.py 의 처리 함수를 그대로 재사용한다(구현은 한 곳에만 둔다).
router.add_api_route("/upload", _s.wash_upload_endpoint, methods=["POST"],
                     summary="이미지 세탁(업로드)")
router.add_api_route("/library", _s.wash_library_list, methods=["GET"],
                     summary="내 이미지 보관함 목록")
router.add_api_route("/library/save", _s.wash_library_save, methods=["POST"],
                     summary="세탁한 이미지를 보관함에 저장")
router.add_api_route("/library/stage", _s.wash_library_stage, methods=["POST"],
                     summary="보관함 이미지를 발행용 폴더로 복사")
router.add_api_route("/library/{filename}", _s.wash_library_delete, methods=["DELETE"],
                     summary="보관함 이미지 삭제")
