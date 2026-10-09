"""Reference for the Agent One API (aos-backend, port 8000): forward /finance/api/* to the AOF service.

The Agent One API stays the one front door. It checks the BAM sign-on as it does for its own routes,
then calls AOF on the internal network with the signed-in user and the shared proxy secret. AOF
(AOF_TRUSTED_PROXY_SECRET set) refuses any request that did not come this way.

Adapt it to the existing route, if the Agent One API already serves /finance/api (the SSO bridge):
- replace `current_user` with the dependency our other routes use;
- register the router where the other routers are registered.

Settings on the Agent One API: AOF_API_URL (for example http://aof-backend.internal:8300) and
AOF_TRUSTED_PROXY_SECRET (the same value as on the AOF service, from the secrets store).
"""

import os

import httpx
from fastapi import APIRouter, Depends, Request, Response

from api.auth.sso import current_user  # <- the dependency our other routes use

router = APIRouter()
_TIMEOUT = httpx.Timeout(120.0, connect=5.0)
_KEEP = ("content-type", "content-disposition", "cache-control")


@router.api_route("/finance/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def forward_to_aof(path: str, request: Request, user=Depends(current_user)) -> Response:
    headers = {
        "X-AOF-User": user.user_id,  # <- the field our user object uses for the bank id
        "X-AOF-Proxy-Secret": os.environ["AOF_TRUSTED_PROXY_SECRET"],
    }
    if "content-type" in request.headers:
        headers["content-type"] = request.headers["content-type"]
    async with httpx.AsyncClient(base_url=os.environ["AOF_API_URL"], timeout=_TIMEOUT) as client:
        r = await client.request(request.method, f"/api/{path}", params=request.query_params,
                                 content=await request.body(), headers=headers)
    return Response(r.content, r.status_code, headers={k: v for k, v in r.headers.items() if k.lower() in _KEEP})
