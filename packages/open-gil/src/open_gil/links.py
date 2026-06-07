from __future__ import annotations

from urllib.parse import urlencode

from .models import ResolvedPlace, VerificationLinks


def build_verification_links(origin: ResolvedPlace, destination: ResolvedPlace) -> VerificationLinks:
    return VerificationLinks(
        naver_maps=naver_public_route_url(origin, destination),
        kakao_map=kakao_public_route_url(origin, destination),
    )


def naver_public_route_url(origin: ResolvedPlace, destination: ResolvedPlace) -> str:
    params = {
        "slat": f"{origin.lat:.7f}",
        "slng": f"{origin.lon:.7f}",
        "sname": origin.name,
        "dlat": f"{destination.lat:.7f}",
        "dlng": f"{destination.lon:.7f}",
        "dname": destination.name,
        "appname": "open-gil",
    }
    return "nmap://route/public?" + urlencode(params)


def kakao_public_route_url(origin: ResolvedPlace, destination: ResolvedPlace) -> str:
    params = {
        "sp": f"{origin.lat:.7f},{origin.lon:.7f}",
        "ep": f"{destination.lat:.7f},{destination.lon:.7f}",
        "by": "publictransit",
    }
    return "http://m.map.kakao.com/scheme/route?" + urlencode(params, safe=",")

