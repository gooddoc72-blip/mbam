'use strict';

/**
 * reset_network.js
 * ----------------------------------------------------------------------------
 * 연결된 Android 테스트 기기의 이동통신(모바일) 데이터를
 *   끄기 → 잠시 대기 → 켜기 → 안정화 대기
 * 순서로 토글하여, 실제 기기 환경에서의 '네트워크 전환' 상황을 시뮬레이션한다.
 *
 * 용도: E2E 테스트 사이에 네트워크를 깨끗한 상태로 재초기화하거나,
 *       앱의 재연결/복구 동작을 검증할 때 사용.
 *
 * 사전 조건:
 *   - PC에 adb(Android Platform Tools)가 설치되어 PATH에 등록되어 있을 것
 *   - USB 디버깅이 켜진 테스트 기기 1대가 연결되어 있을 것 (adb devices 로 확인)
 *
 * 실행:  node reset_network.js
 * ----------------------------------------------------------------------------
 */

const { execSync } = require('child_process');

// ─── 설정 ───────────────────────────────────────────────────────────────────
const DISABLE_WAIT_SEC = 3; // 데이터 끈 뒤 대기(초)
const STABILIZE_WAIT_SEC = 7; // 데이터 켠 뒤 네트워크 안정화 대기(초)

// ─── 유틸 ───────────────────────────────────────────────────────────────────
function log(msg) {
  // 비개발자도 터미널에서 진행 상황을 바로 알아볼 수 있도록 명확히 출력
  console.log(`[네트워크 재설정] ${msg}`);
}

/** 동기식 초 단위 대기 (busy-wait, 단순/명확성 우선) */
function sleepSync(seconds) {
  const end = Date.now() + seconds * 1000;
  while (Date.now() < end) {
    // 의도적 블로킹 대기
  }
}

function run(command) {
  // stdio 'pipe' 로 받아서 실패 시 메시지를 사람이 읽기 쉽게 가공
  execSync(command, { stdio: 'pipe' });
}

// ─── 메인 동기식 절차 ────────────────────────────────────────────────────────
function resetNetwork() {
  log('절차를 시작합니다.');

  // 0) 기기 연결 확인
  try {
    const devices = execSync('adb devices', { encoding: 'utf8' });
    const connected = devices
      .split('\n')
      .slice(1)
      .filter((line) => line.trim().endsWith('\tdevice'));
    if (connected.length === 0) {
      log('⚠️  연결된 기기를 찾지 못했습니다. (adb devices 결과 없음)');
      log('    USB 연결과 USB 디버깅 허용 여부를 확인해 주세요.');
      process.exit(1);
    }
    log(`연결된 기기 ${connected.length}대 확인 완료.`);
  } catch (e) {
    log('❌ adb 명령을 실행할 수 없습니다. adb 설치 및 PATH 등록을 확인해 주세요.');
    log(`    상세: ${e.message}`);
    process.exit(1);
  }

  // 1) 모바일 데이터 끄기
  log('① 모바일 데이터를 끕니다 (svc data disable) ...');
  run('adb shell svc data disable');
  log('   → 모바일 데이터 OFF 완료.');

  // 2) 대기
  log(`② ${DISABLE_WAIT_SEC}초 대기합니다 ...`);
  sleepSync(DISABLE_WAIT_SEC);

  // 3) 모바일 데이터 켜기
  log('③ 모바일 데이터를 다시 켭니다 (svc data enable) ...');
  run('adb shell svc data enable');
  log('   → 모바일 데이터 ON 완료.');

  // 4) 네트워크 안정화 대기
  log(`④ 네트워크 안정화를 위해 ${STABILIZE_WAIT_SEC}초 대기합니다 ...`);
  sleepSync(STABILIZE_WAIT_SEC);

  log('✅ 네트워크 재설정 절차가 완료되었습니다.');
}

// 다른 스크립트(예: qa_test.js)에서 require 해서 쓸 수 있도록 export
module.exports = { resetNetwork };

// 직접 실행한 경우에만 절차 수행
if (require.main === module) {
  try {
    resetNetwork();
    process.exit(0);
  } catch (e) {
    log(`❌ 절차 도중 오류가 발생했습니다: ${e.message}`);
    process.exit(1);
  }
}
