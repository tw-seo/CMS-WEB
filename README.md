# K-Safety CMS WEB

K-Safety 관제용 컨트롤타워 서버입니다.  
카메라, 계정, 이벤트, 뷰어 권한, 영상 분배(MediaMTX) 정보를 한 곳에서 관리하고, 메인/서브 뷰어에 필요한 설정과 갱신 신호를 내려주는 역할을 합니다.

## 1. 컨트롤타워에서 하는 일

이 프로젝트는 크게 아래 역할을 담당합니다.

- CMS API 서버
  - 계정, 카메라, 이벤트, 인터락, 부저, SMS 등 설정/조회 API 제공
- 뷰어 권한 관리
  - 어떤 계정이 어떤 카메라를 볼 수 있는지 관리
- 영상 분배 연동
  - 원본 RTSP를 MediaMTX 쪽 분배 주소로 매핑
  - HLS / WebRTC / RTSP 주소 발급 지원
- 실시간 갱신 알림
  - 카메라 설정 변경, 이벤트 발생, 계정 변경 등을 뷰어 쪽에 전달
- 상태 감시
  - MediaMTX watchdog / registry를 통해 스트림 상태 확인

## 2. 주요 구성

### `web`
Django 기반 CMS 서버입니다.

- 포트: `10515 -> 8000`
- API 문서: `/api/docs`
- 주요 기능:
  - CMS 설정 API
  - 계정/권한 API
  - 이벤트 API
  - MediaMTX 연동 API

### `db`
PostgreSQL 데이터베이스입니다.

- 내부 기본 포트: `5432`
- 외부 기본 포트: `15432`

### `mediamtx`
영상 분배 서버입니다.

- RTSP 분배: `10314`
- HLS: `8888`
- WebRTC HTTP: `8889`
- MediaMTX Control API: `9997`

## 3. 실행 방법

### 기본 실행

```bash
cd /home/twseo/projects/K-Safety-CMS-WEB
docker-compose --env-file .env.prod up -d --build
```

### 종료

```bash
cd /home/twseo/projects/K-Safety-CMS-WEB
docker-compose --env-file .env.prod down
```

### 마이그레이션

```bash
cd /home/twseo/projects/K-Safety-CMS-WEB
docker-compose --env-file .env.prod exec web python manage.py makemigrations
docker-compose --env-file .env.prod exec web python manage.py migrate
```

### 로그 확인

```bash
cd /home/twseo/projects/K-Safety-CMS-WEB
docker-compose --env-file .env.prod logs -f web
docker-compose --env-file .env.prod logs -f mediamtx
```

## 4. 접속 정보

- CMS API: `http://서버IP:10515/api/`
- API 문서: `http://서버IP:10515/api/docs`
- HLS: `http://서버IP:8888/{stream_path}/index.m3u8`
- WebRTC: `http://서버IP:8889/{stream_path}/whep`
- RTSP: `rtsp://서버IP:10314/{stream_path}`

## 5. 주요 설정값

설정 파일: [.env.prod](/home/twseo/projects/K-Safety-CMS-WEB/.env.prod)

### 데이터베이스

- `POSTGRES_DB`
  - 사용할 DB 이름
- `POSTGRES_USER`
  - DB 계정
- `POSTGRES_PASSWORD`
  - DB 비밀번호
- `POSTGRES_PORT_EXTERNAL`
  - 외부에서 접속할 PostgreSQL 포트

### CMS / 기본 운영

- `MODE`
  - 운영 모드 구분 값
- `NAME`
  - 사이트 이름
- `CMS_IP`
  - 현재 CMS 서버 외부 접근 주소
- `CMS_PORT`
  - CMS 기본 포트
- `NEED_AUTH`
  - CMS API 인증 강제 여부

### 뷰어 연동

- `VIEWER_IP`
  - 메인 뷰어 또는 뷰어 측 기본 주소
- `VIEWER_PORT`
  - 뷰어 기본 포트
- `VIEWER_REALTIME_ENABLED`
  - 실시간 갱신 WebSocket 사용 여부
- `VIEWER_REALTIME_HOST`
  - 실시간 서버 bind 주소
- `VIEWER_REALTIME_PORT`
  - 실시간 갱신 포트
- `VIEWER_REALTIME_PATH`
  - 실시간 갱신 WebSocket 경로
- `VIEWER_NOTIFY_TARGETS`
  - 설정 변경/이벤트 발생 시 알림을 보낼 뷰어 대상

### DL 연동

- `DL_IP`
  - DL 서버 주소
- `DL_PORT`
  - DL 제어 포트
- `DL_VIDEO_PORT`
  - DL 영상 관련 포트

### MediaMTX 연동

- `MTX_API_BASE`
  - Django가 MediaMTX Control API에 붙을 주소
- `MTX_API_PORT`
  - MediaMTX API 포트
- `PUBLIC_HOST`
  - 뷰어가 실제로 접근할 스트림 공개 주소
  - HLS / WebRTC / RTSP 주소 생성 시 사용
- `MTX_RTSP_PORT`
  - RTSP 공개 포트
- `MTX_WATCH_DOG`
  - MediaMTX 상태 감시 사용 여부
- `TOKEN_AUTH_ENABLED`
  - 스트림 URL 토큰 인증 사용 여부
- `MTX_CONFIG_FILE`
  - 사용할 MediaMTX 설정 파일
  - 예: `mediamtx-dev.yml`, `mediamtx-true.yml`

## 6. MediaMTX 설정 파일 의미

- `mediamtx-dev.yml`
  - 개발용
  - 내부 인증이 느슨한 편이라 테스트용으로 사용
- `mediamtx-true.yml`
  - HTTP auth 기반 운영용
  - Django의 `/api/mediamtx/media/auth`와 연동
- `mediamtx-false.yml`
  - 인증 없이 단순 동작 확인할 때 사용하는 설정

현재 실제 사용 파일은 `.env.prod`의 `MTX_CONFIG_FILE` 값으로 결정됩니다.

## 7. 운영 시 가장 먼저 확인할 값

실제 설치/운영에서 우선 확인할 값은 아래입니다.

1. `PUBLIC_HOST`
2. `MTX_CONFIG_FILE`
3. `VIEWER_NOTIFY_TARGETS`
4. `VIEWER_REALTIME_PORT`
5. `DL_IP`, `DL_PORT`, `DL_VIDEO_PORT`
6. `POSTGRES_PASSWORD`

특히 `PUBLIC_HOST`가 잘못되면 뷰어에서 HLS / WebRTC / RTSP 접속 주소가 틀어질 수 있습니다.

## 8. 빠른 점검 포인트

### CMS가 뜨는지 확인

```bash
curl http://127.0.0.1:10515/api/docs
```

### MediaMTX API 확인

```bash
curl http://127.0.0.1:9997/v3/serverinfos/get
```

### HLS 확인

```bash
curl http://127.0.0.1:8888/{stream_path}/index.m3u8
```

## 9. 참고

- 주요 API 라우트: [config/urls.py](/home/twseo/projects/K-Safety-CMS-WEB/config/urls.py)
- MediaMTX API: [apps/mediamtx/api/mediamtx.py](/home/twseo/projects/K-Safety-CMS-WEB/apps/mediamtx/api/mediamtx.py)
- Docker 구성: [docker-compose.yml](/home/twseo/projects/K-Safety-CMS-WEB/docker-compose.yml)
