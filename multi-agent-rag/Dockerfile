FROM python:3.9-slim

WORKDIR /app

# 의존성만 먼저 복사해서 설치 - 코드만 바뀌고 requirements.txt가 안 바뀌면
# 이 레이어가 캐시돼서 다음 빌드가 훨씬 빨라진다.
COPY requirements.txt .
# sentence-transformers가 딸려오는 torch를 그냥 두면 기본으로 GPU(CUDA) 빌드를 설치하는데,
# 여기엔 엔비디아 GPU 라이브러리가 수 GB 붙어있다 - 우리 서버는 GPU가 없어서(CPU 추론만 함)
# 전부 낭비. requirements.txt를 설치하기 전에 CPU 전용 torch를 먼저 깔아두면, 그 다음
# sentence-transformers가 torch를 요구해도 "이미 설치돼 있다"고 보고 GPU 버전을 안 받아온다.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# 나머지 코드 복사 (.dockerignore에 적은 건 제외됨)
COPY . .

EXPOSE 8000
EXPOSE 8501

# 컨테이너 시작할 때마다 벡터DB부터 확인(이미 최신이면 건너뜀, build_vectordb.py의
# fingerprint 캐싱 로직) 하고 나서 서버를 띄운다.
# docker-compose.yml의 ui 서비스는 이 CMD 대신 streamlit 실행 명령으로 덮어써서 같은
# 이미지를 재사용한다 (이미지를 따로 안 만들어도 됨).
CMD ["sh", "-c", "python build_vectordb.py && uvicorn app:app --host 0.0.0.0 --port 8000"]
