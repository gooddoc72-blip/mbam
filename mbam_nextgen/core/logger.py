import logging
import sys
import os

def setup_logger(name="MBAM"):
    logger = logging.getLogger(name)
    
    # 중복 핸들러 방지
    if not logger.handlers:
        logger.propagate = False
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 콘솔 출력 (Windows 인코딩 오류 방지를 위해 utf-8 stdout 강제 또는 에러 무시)
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

        class SafeStreamHandler(logging.StreamHandler):
            def emit(self, record):
                try:
                    msg = self.format(record)
                    stream = self.stream
                    if stream is not None:
                        stream.write(msg + self.terminator)
                        self.flush()
                except Exception:
                    try:
                        self.handleError(record)
                    except Exception:
                        pass
            
            def handleError(self, record):
                # 에러 무시 (콘솔이 없거나 인코딩 에러 시 서버 크래시 방지)
                pass

        console_handler = SafeStreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        class SafeFileHandler(logging.FileHandler):
            def handleError(self, record):
                pass
                
        # 파일 출력
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        file_handler = SafeFileHandler(
            os.path.join(log_dir, "mbam_sys.log"), 
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    return logger

# 전역 로거 인스턴스
logger = setup_logger()
