import json
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from fastmcp import FastMCP, Context
from scalekit import ScalekitClient
from scalekit.common.scalekit import TokenValidationOptions

# ---  FASTMCP INSTANCE  ---
mcp = FastMCP("ExpenseTracker")

# ---  PUBLIC FASTAPI APP FOR WELL-KNOWN ENDPOINTS  ---
public_app = FastAPI()
security = HTTPBearer()


@public_app.get("/.well-known/oauth-protected-resource/mcp")
async def oauth_protected_resource_metadata():
    """Public metadata endpoint (no auth required)."""
    data = {
        "authorization_servers": [
            "https://paytm.scalekit.dev/resources/res_97420808191740418"
        ],
        "bearer_methods_supported": ["header"],
        "resource": "https://forTest.fastmcp.app/mcp",
        "resource_documentation": "https://forTest.fastmcp.app/mcp/docs",
        "scopes_supported": ["user:read", "user:write"],
    }
    return JSONResponse(content=data)


# ---  AUTHENTICATED MCP TOOLS  ---
_scalekit_client = ScalekitClient(
    "https://paytm.scalekit.dev",
    "m2m_97422068261325572",
    "test_8c5ODRZ6DCsNzOdVSRSxrVja3ccDGdAAQlgbOybPqfAVzBvhngce3NiUNuEssLAQ",
)

# ---  SETTINGS PLACEHOLDER  ---
# You used `settings` in your middleware but never defined it.
# Let's define a simple settings class.
class Settings:
    SCALEKIT_ENVIRONMENT_URL = "https://paytm.scalekit.dev"
    SCALEKIT_AUDIENCE_NAME = "https://forTest.fastmcp.app/mcp"
    SCALEKIT_RESOURCE_METADATA_URL = (
        "https://forTest.fastmcp.app/.well-known/oauth-protected-resource/mcp"
    )


settings = Settings()


# ---  AUTH MIDDLEWARE  ---
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/.well-known/"):
            return await call_next(request)

        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=401, detail="Missing or invalid authorization header"
                )

            token = auth_header.split(" ")[1]
            body_bytes = await request.body()

            try:
                request_data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
            except (json.JSONDecodeError, UnicodeDecodeError):
                request_data = {}

            validation_options = TokenValidationOptions(
                issuer=settings.SCALEKIT_ENVIRONMENT_URL,
                audience=[settings.SCALEKIT_AUDIENCE_NAME],
            )

            is_tool_call = request_data.get("method") == "tools/call"
            if is_tool_call:
                validation_options.required_scopes = ["search:read"]

            try:
                _scalekit_client.validate_token(token, options=validation_options)
            except Exception:
                raise HTTPException(status_code=401, detail="Token validation failed")

        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": "unauthorized" if e.status_code == 401 else "forbidden",
                    "error_description": e.detail,
                },
                headers={
                    "WWW-Authenticate": (
                        f'Bearer realm="OAuth", '
                        f'resource_metadata="{settings.SCALEKIT_RESOURCE_METADATA_URL}"'
                    )
                },
            )

        return await call_next(request)


# # ---  TOKEN VALIDATION HELPER  ---
# async def validate_request_token(ctx: Context):
#     if not ctx or not getattr(ctx, "headers", None):
#         raise HTTPException(status_code=401, detail="Missing context headers")
#
#     auth_header = ctx.headers.get("authorization")
#     if not auth_header or not auth_header.startswith("Bearer "):
#         raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
#
#     token = auth_header.split("Bearer ")[1].strip()
#     opts = TokenValidationOptions(verify_signature=True, verify_exp=True, verify_aud=True)
#     _scalekit_client.validate_token(token, options=opts)
#     return True
#

# ---  MCP TOOLS  ---
@mcp.tool()
async def addNumber(a: int, b: int, ctx: Context = None) -> int:
    return a + b + 10


@mcp.tool()
async def tellMeData(ctx: Context = None) -> int:
    return 10


@mcp.tool()
async def whatISThePSyco(ctx: Context = None) -> int:
    return 10


# ---  COMBINE BOTH ASGI APPS  ---
combined = FastAPI()

mcp_app = mcp.http_app()
combined.add_middleware(AuthMiddleware)
combined.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict origins properly
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

combined.mount("/mcp", mcp_app)
combined.mount("", public_app)

if __name__ == "__main__":
    uvicorn.run(combined, host="0.0.0.0", port=8002)
