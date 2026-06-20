import os
import random
from typing import List

class ClipGenerator:
    """
    [L2. The Clip]
    Generates 15s vertical short-form videos from blog content and images.
    """
    
    def __init__(self, output_dir: str = "mbam_nextgen/temp_clips"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def generate_clip(self, image_paths: List[str], text_segments: List[str], output_name: str) -> str:
        """
        Synthesizes images and text into an MP4 file.
        """
        print(f"[Clip] Generating AI Clip from {len(image_paths)} images...")
        
        try:
            from moviepy import ImageSequenceClip
            from PIL import Image, ImageDraw, ImageFont
            import numpy as np
        except ImportError:
            print("[Clip] moviepy or Pillow is not installed. Please install them to use this feature.")
            return ""
            
        if not image_paths:
            print("[Clip] No images provided.")
            return ""

        output_path = os.path.join(self.output_dir, f"{output_name}.mp4")
        
        try:
            processed_images = []
            target_size = (720, 1280) # 9:16 vertical video (optimized for speed)
            
            for i, img_path in enumerate(image_paths):
                # 1. Resize and crop image to 9:16
                with Image.open(img_path) as img:
                    # Convert to RGB if necessary
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                        
                    img_ratio = img.width / img.height
                    target_ratio = target_size[0] / target_size[1]
                    
                    if img_ratio > target_ratio:
                        # Image is wider, crop width
                        new_width = int(img.height * target_ratio)
                        left = (img.width - new_width) / 2
                        img = img.crop((left, 0, left + new_width, img.height))
                    else:
                        # Image is taller, crop height
                        new_height = int(img.width / target_ratio)
                        top = (img.height - new_height) / 2
                        img = img.crop((0, top, img.width, top + new_height))
                        
                    img = img.resize(target_size, Image.Resampling.LANCZOS)
                    
                    # 2. Add text overlay
                    draw = ImageDraw.Draw(img)
                    text = text_segments[i % len(text_segments)] if text_segments else "가게 소식"
                    
                    # Semi-transparent background for text
                    text_bg = Image.new('RGBA', target_size, (0, 0, 0, 0))
                    draw_bg = ImageDraw.Draw(text_bg)
                    draw_bg.rectangle([(0, target_size[1] - 300), (target_size[0], target_size[1])], fill=(0, 0, 0, 150))
                    img.paste(text_bg, (0, 0), text_bg)
                    
                    # Add text (using default font for simplicity, can be improved with specific TTF)
                    # For a real product, a bold Korean font like 'NanumGothicBold.ttf' should be used.
                    # Here we just try to use basic drawing.
                    try:
                        font = ImageFont.truetype("malgun.ttf", 60) # Windows default Korean font
                    except:
                        font = ImageFont.load_default()
                        
                    draw.text((50, target_size[1] - 200), text, font=font, fill=(255, 255, 255))
                    
                    processed_images.append(np.array(img))
                    
            # 3. Create video sequence
            # Create a clip where each image lasts 3 seconds
            clip = ImageSequenceClip(processed_images, durations=[3.0] * len(processed_images))
            
            # 4. Export to MP4
            print(f"[Clip] Writing video to {output_path}...")
            clip.write_videofile(output_path, fps=12, codec="libx264", audio=False, logger=None)
            
            return output_path
            
        except Exception as e:
            print(f"[Clip] Video generation failed: {e}")
            return ""
