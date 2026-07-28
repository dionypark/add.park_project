"""EC2 온디맨드 요금 캐시를 갱신하는 스크립트.

EC2 전체 요금표는 480MB라 calculate_cost가 호출될 때마다 받을 수 없어서,
우리가 지원하는 인스턴스 타입(t3.micro, t3.medium, m5.large, m5.xlarge)만
뽑아서 data/ec2_price_cache.json에 저장해둔다.

캐시는 24시간이 지나면 calculate_cost 호출 시 자동으로 갱신되지만,
최신 상태를 미리 보장해두고 싶으면 이 스크립트를 직접 실행하면 된다.

실행: python refresh_ec2_prices.py
"""
from pricing import refresh_ec2_cache

if __name__ == "__main__":
    print("EC2 요금표(480MB)를 스트리밍으로 받아오는 중... 시간이 좀 걸릴 수 있습니다.")
    prices = refresh_ec2_cache()
    print("완료. data/ec2_price_cache.json에 저장됨:")
    for instance_type, price in prices.items():
        print(f"  {instance_type}: ${price}/hour")
