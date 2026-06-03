import os
import pytest
from PIL import Image
from mbam_nextgen.services.armor import ImageArmor

@pytest.fixture
def dummy_image(tmp_path):
    # pytest의 내장 tmp_path 픽스처를 사용하여 테스트 후 자동 정리되도록 구성
    img_path = tmp_path / "test_source.jpg"
    dummy = Image.new('RGB', (800, 600), color=(100, 150, 200))
    dummy.save(img_path)
    return str(img_path)

@pytest.fixture
def armor():
    return ImageArmor()

def test_image_wash_changes_hash(armor, dummy_image, tmp_path):
    """이미지 세척 시 원본과 해시값이 100% 달라지는지 검증"""
    original_hash = armor.get_file_hash(dummy_image)
    output_file = str(tmp_path / "washed_test.jpg")
    
    washed_path = armor.wash_image(dummy_image, output_file)
    new_hash = armor.get_file_hash(washed_path)
    
    # Assert: 해시 변경 확인
    assert original_hash != new_hash, "이미지 세척 후에도 해시값이 동일합니다."
    
def test_image_wash_injects_exif(armor, dummy_image, tmp_path):
    """세척된 이미지에 스마트폰 EXIF 데이터(Make, Model)가 주입되었는지 검증"""
    output_file = str(tmp_path / "washed_test_exif.jpg")
    washed_path = armor.wash_image(dummy_image, output_file)
    
    with Image.open(washed_path) as img:
        info = img._getexif()
        assert info is not None, "EXIF 메타데이터가 주입되지 않았습니다."
        
        # 271: Make, 272: Model
        make = info.get(271)
        model = info.get(272)
        
        assert make in ["Samsung", "Apple"], f"알 수 없는 제조사: {make}"
        assert model is not None, "카메라 모델 정보가 누락되었습니다."
