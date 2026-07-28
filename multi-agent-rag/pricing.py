"""AWS Price List Bulk API에서 실시간 요금을 가져오는 모듈.

- Lambda / Fargate: 가격표 파일이 작아서(1~2MB) 계산할 때마다 바로 받아올 수 있다.
  다만 매번 네트워크를 타면 느려지니 1시간짜리 메모리 캐시를 둔다.
- EC2: 전체 가격표가 480MB라(모든 인스턴스 타입 x OS x 테넌시 조합) 계산할 때마다 받을 수 없다.
  그래서 우리가 지원하는 인스턴스 타입 몇 개만 스트리밍으로 걸러서
  data/ec2_price_cache.json에 저장해두고, calculate_cost는 그 캐시만 읽는다.
  캐시가 없거나 24시간이 지났으면 그때 한 번 다시 받아온다(refresh_ec2_prices.py로 수동 실행도 가능).

모든 fetch는 실패하면 None을 반환한다 - tools.py가 하드코딩된 근사치로 폴백한다.
"""
import json
import threading
import time
from pathlib import Path

import ijson
import requests

PRICING_ROOT = "https://pricing.us-east-1.amazonaws.com"
LOCATION = "US East (N. Virginia)"

LAMBDA_FARGATE_CACHE_TTL_SECONDS = 3600  # Lambda/Fargate 메모리 캐시 TTL (1시간)

EC2_CACHE_PATH = Path(__file__).parent / "data" / "ec2_price_cache.json"
EC2_CACHE_MAX_AGE_SECONDS = 24 * 3600
EC2_INSTANCE_TYPES = ["t3.micro", "t3.medium", "m5.large", "m5.xlarge"]

_lambda_cache = {"data": None, "ts": 0.0}
_fargate_cache = {"data": None, "ts": 0.0}
_cache_lock = threading.Lock()


def _get_current_version_url(service_code: str) -> str:
    resp = requests.get(
        f"{PRICING_ROOT}/offers/v1.0/aws/{service_code}/current/region_index.json", timeout=10
    )
    resp.raise_for_status()
    return resp.json()["regions"]["us-east-1"]["currentVersionUrl"]


def _first_ondemand_price(data: dict, sku: str, min_begin_range: str = None) -> float:
    for term in data["terms"].get("OnDemand", {}).get(sku, {}).values():
        for dim in term["priceDimensions"].values():
            if min_begin_range is not None and dim.get("beginRange") != min_begin_range:
                continue
            price = float(dim["pricePerUnit"]["USD"])
            if price > 0:
                return price
    return None


def fetch_lambda_prices() -> dict:
    """{'price_per_request': float, 'price_per_gb_second': float} 또는 실패 시 None."""
    with _cache_lock:
        if _lambda_cache["data"] and time.time() - _lambda_cache["ts"] < LAMBDA_FARGATE_CACHE_TTL_SECONDS:
            return _lambda_cache["data"]

    try:
        version_url = _get_current_version_url("AWSLambda")
        resp = requests.get(f"{PRICING_ROOT}{version_url}", timeout=30)
        resp.raise_for_status()
        data = resp.json()

        price_per_request = None
        price_per_gb_second = None
        for product in data["products"].values():
            attrs = product.get("attributes", {})
            if attrs.get("location") != LOCATION:
                continue
            group = attrs.get("group")
            if group == "AWS-Lambda-Requests" and price_per_request is None:
                price_per_request = _first_ondemand_price(data, product["sku"])
            elif group == "AWS-Lambda-Duration" and price_per_gb_second is None:
                # Tier-1(가장 저렴한 첫 구간, beginRange=="0")만 사용한다.
                price_per_gb_second = _first_ondemand_price(data, product["sku"], min_begin_range="0")

        if price_per_request is None or price_per_gb_second is None:
            return None

        result = {"price_per_request": price_per_request, "price_per_gb_second": price_per_gb_second}
        with _cache_lock:
            _lambda_cache["data"] = result
            _lambda_cache["ts"] = time.time()
        return result
    except Exception:
        return None


def fetch_fargate_prices() -> dict:
    """{'price_per_vcpu_hour': float, 'price_per_gb_hour': float} 또는 실패 시 None."""
    with _cache_lock:
        if _fargate_cache["data"] and time.time() - _fargate_cache["ts"] < LAMBDA_FARGATE_CACHE_TTL_SECONDS:
            return _fargate_cache["data"]

    try:
        version_url = _get_current_version_url("AmazonECS")
        resp = requests.get(f"{PRICING_ROOT}{version_url}", timeout=30)
        resp.raise_for_status()
        data = resp.json()

        price_per_vcpu_hour = None
        price_per_gb_hour = None
        for product in data["products"].values():
            attrs = product.get("attributes", {})
            if attrs.get("location") != LOCATION:
                continue
            usagetype = attrs.get("usagetype", "")
            # ARM/Windows는 제외하고 x86 Linux 기준 단가만 사용한다.
            if usagetype == "USE1-Fargate-vCPU-Hours:perCPU" and price_per_vcpu_hour is None:
                price_per_vcpu_hour = _first_ondemand_price(data, product["sku"])
            elif usagetype == "USE1-Fargate-GB-Hours" and price_per_gb_hour is None:
                price_per_gb_hour = _first_ondemand_price(data, product["sku"])

        if price_per_vcpu_hour is None or price_per_gb_hour is None:
            return None

        result = {"price_per_vcpu_hour": price_per_vcpu_hour, "price_per_gb_hour": price_per_gb_hour}
        with _cache_lock:
            _fargate_cache["data"] = result
            _fargate_cache["ts"] = time.time()
        return result
    except Exception:
        return None


def refresh_ec2_cache() -> dict:
    """EC2 480MB 가격표를 스트리밍으로 훑어서 지원 인스턴스 타입 가격만 뽑아 로컬에 저장한다."""
    version_url = _get_current_version_url("AmazonEC2")
    url = f"{PRICING_ROOT}{version_url}"

    with requests.get(url, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        resp.raw.decode_content = True

        sku_to_instance = {}
        for sku, product in ijson.kvitems(resp.raw, "products"):
            attrs = product.get("attributes", {})
            if (
                attrs.get("location") == LOCATION
                and attrs.get("instanceType") in EC2_INSTANCE_TYPES
                and attrs.get("tenancy") == "Shared"
                and attrs.get("operatingSystem") == "Linux"
                and attrs.get("preInstalledSw") == "NA"
                and attrs.get("capacitystatus") == "Used"
            ):
                sku_to_instance[sku] = attrs["instanceType"]

        prices = {}
        if sku_to_instance:
            for sku, term in ijson.kvitems(resp.raw, "terms.OnDemand"):
                if sku not in sku_to_instance:
                    continue
                for offer_term in term.values():
                    for dim in offer_term["priceDimensions"].values():
                        price = float(dim["pricePerUnit"]["USD"])
                        if price > 0:
                            prices[sku_to_instance[sku]] = price

    EC2_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EC2_CACHE_PATH.write_text(json.dumps({"fetched_at": time.time(), "prices": prices}, indent=2))
    return prices


def fetch_ec2_prices() -> dict:
    """{"t3.micro": 0.0104, ...} 또는 캐시가 없고 실시간 갱신도 실패하면 None."""
    try:
        if EC2_CACHE_PATH.exists():
            cached = json.loads(EC2_CACHE_PATH.read_text())
            if time.time() - cached["fetched_at"] < EC2_CACHE_MAX_AGE_SECONDS:
                return cached["prices"]
        return refresh_ec2_cache()
    except Exception:
        if EC2_CACHE_PATH.exists():
            try:
                return json.loads(EC2_CACHE_PATH.read_text())["prices"]
            except Exception:
                return None
        return None
