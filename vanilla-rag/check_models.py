"""이 API 키로 사용 가능한 임베딩 모델 목록을 출력한다."""
import config

for m in config.client.models.list():
    if "embedContent" in (m.supported_actions or []):
        print(m.name)
