"""내레이션 생성 — Supertonic-3 (오픈소스, 로컬 실행, 한국어)

실행: 레포 루트에서  .venv/Scripts/python video/narration.py [목소리=F1]
출력: video/audio/narr_NN.wav, video/timeline.js (장면 시작·길이·자막)
- SPEECH: TTS가 읽을 문장 (숫자를 한글로 풀어 씀)
- SUB: 화면 자막 (숫자는 아라비아 숫자, story/logic.md 값 그대로)
"""
import json
import sys
import wave
from pathlib import Path

import numpy as np
from supertonic import TTS

HERE = Path(__file__).resolve().parent
OUT = HERE / "audio"
VOICE = sys.argv[1] if len(sys.argv) > 1 else "F1"

# (장면 최소 길이 초, 자막, 읽을 문장)
SCENES = [
    (12, "2029년, 노원구 하계1동. 아침빵과 쫀득 디저트를 반반 파는 빵집을 열면, 한 달에 632만 원이 남습니다.",
     "이천이십구 년, 노원구 하계일동. 아침빵과 쫀득 디저트를 반반 파는 빵집을 열면, 한 달에 육백삼십이만 원이 남습니다."),
    (10, "왜 하계동일까요? 서울 352개 동을 수요, 미래 변화, 경쟁, 수익성 네 가지로 점수 매겼습니다.",
     "왜 하계동일까요? 서울 삼백오십이 개 동을, 수요, 미래 변화, 경쟁, 수익성, 네 가지로 점수 매겼습니다."),
    (15, "5위 창4동, 4위 효창동, 3위 상계9동, 2위 월계2동, 그리고 1위 하계1동. 가중치를 천 번 흔들어도 986번 1위였습니다.",
     "오 위 창사동, 사 위 효창동, 삼 위 상계구동, 이 위 월계이동, 그리고 일 위, 하계일동. 가중치를 천 번 흔들어도, 구백팔십육 번 일 위였습니다."),
    (13, "의외로 상위 세 곳 모두 노원입니다. 빵집 수는 서울 중간값의 절반인데, 한 곳 매출은 1.6배, 매년 10%씩 늘고 있죠.",
     "의외로 상위 세 곳 모두 노원입니다. 빵집 수는 서울 중간값의 절반인데, 한 곳의 매출은 일 점 육 배, 매년 십 퍼센트씩 늘고 있죠."),
    (8, "2027년 동북선 개통, 2028년과 2029년엔 6천여 세대가 입주합니다. 손님은 더 늘어납니다.",
     "이천이십칠 년 동북선 개통, 이천이십팔 년과 이천이십구 년엔 육천여 세대가 입주합니다. 손님은 더 늘어납니다."),
    (12, "하계동 빵집 매출의 4분의 1이 아침에 나오고, 서울 빵집의 60대 이상 손님 비중은 두 배가 됐습니다. 그래서 아침엔 빵, 오후엔 디저트.",
     "하계동 빵집 매출의 사분의 일이 아침에 나오고, 서울 빵집의 육십 대 이상 손님 비중은 두 배가 됐습니다. 그래서 아침엔 빵, 오후엔 디저트."),
    (15, "디저트 유행은 점점 짧아집니다. 관심이 반으로 줄기까지 크로플 163일, 탕후루 54일, 두쫀쿠는 보름. 그래서 시즌 한정 메뉴를 6~8주마다 바꿉니다.",
     "디저트 유행은 점점 짧아집니다. 관심이 반으로 줄기까지, 크로플 백육십삼 일, 탕후루 오십사 일, 두쫀쿠는 보름. 그래서 시즌 한정 메뉴를 육 주에서 팔 주마다 바꿉니다."),
    (10, "공식은 하나. 익숙한 빵에 떡의 쫀득함, 잘랐을 때 보이는 단면, 그리고 하루 한정.",
     "공식은 하나. 익숙한 빵에 떡의 쫀득함, 잘랐을 때 보이는 단면, 그리고 하루 한정."),
    (15, "월 매출 2,452만 원에서 재료비, 인건비, 임대료를 빼면 632만 원. 하루 32명이면 본전, 22개월이면 투자금을 돌려받습니다.",
     "월 매출 이천사백오십이만 원에서 재료비, 인건비, 임대료를 빼면 육백삼십이만 원. 하루 서른두 명이면 본전, 이십이 개월이면 투자금을 돌려받습니다."),
    (10, "2029년, 빵이 더 팔리기 시작한 동네에서 시작합니다.",
     "이천이십구 년, 빵이 더 팔리기 시작한 동네에서 시작합니다."),
]
LEAD = 0.6   # 장면 시작 후 말하기 전 여백(초)
TAIL = 0.9   # 말 끝난 뒤 여백(초)


def save_wav(path, audio, sr):
    pcm = np.clip(audio, -1, 1)
    pcm = (pcm * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def main():
    OUT.mkdir(exist_ok=True)
    tts = TTS(model="supertonic-3")
    style = tts.get_voice_style(VOICE)
    sr = tts.sample_rate
    t, scenes = 0.0, []
    for i, (min_len, sub, speech) in enumerate(SCENES, 1):
        wav, dur = tts.synthesize(speech, voice_style=style, lang="ko", total_steps=16, speed=1.0)
        audio = np.asarray(wav, dtype=np.float32).reshape(-1)
        secs = len(audio) / sr
        save_wav(OUT / f"narr_{i:02d}.wav", audio, sr)
        length = max(min_len, LEAD + secs + TAIL)
        scenes.append({"n": i, "start": round(t, 3), "dur": round(length, 3),
                       "speechStart": round(t + LEAD, 3), "speechDur": round(secs, 3), "sub": sub})
        print(f"{i:02d} 말 {secs:5.2f}초 / 장면 {length:5.2f}초")
        t += length
    (HERE / "timeline.js").write_text(
        "// narration.py가 생성 — 직접 고치지 말 것\nwindow.TIMELINE = "
        + json.dumps({"total": round(t, 3), "voice": VOICE, "scenes": scenes}, ensure_ascii=False, indent=1)
        + ";\n", encoding="utf-8")
    print(f"총 {t:.1f}초, 목소리 {VOICE}")


if __name__ == "__main__":
    main()
