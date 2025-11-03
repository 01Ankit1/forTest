from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastmcp import FastMCP, Context
from scalekit import ScalekitClient
from scalekit.common.scalekit import TokenValidationOptions

# ---  FASTMCP INSTANCE  ---
mcp = FastMCP("ExpenseTracker")

# ---  PUBLIC FASTAPI APP FOR WELL-KNOWN ENDPOINTS  ---
public_app = FastAPI()

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

async def validate_request_token(ctx: Context):
    if ctx is None or not getattr(ctx, "headers", None):
        raise HTTPException(status_code=401, detail="Missing context headers")
    auth_header = ctx.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth_header.split("Bearer ")[1].strip()
    opts = TokenValidationOptions(verify_signature=True, verify_exp=True, verify_aud=True)
    _scalekit_client.validate_token(token, options=opts)
    return True

@mcp.tool()
async def addNumber(a: int, b: int, ctx: Context = None) -> int:
    await validate_request_token(ctx)
    return a + b + 10

@mcp.tool()
async def tellMeData(ctx: Context = None) -> int:
    await validate_request_token(ctx)
    return 10

@mcp.tool()
async def whatISThePSyco(ctx: Context = None) -> int:
    await validate_request_token(ctx)
    return 10

# ---  COMBINE BOTH ASGI APPS  ---
# streamable_http_app() -> deprecated
# use http_app() instead, and mount it directly
combined = FastAPI()

mcp_app = mcp.http_app()  # ✅ new API replaces streamable_http_app()

# Mount correctly
combined.mount("/mcp", mcp_app)      # MCP routes (protected)
combined.mount("", public_app)       # Public routes

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(combined, host="0.0.0.0", port=8002)
