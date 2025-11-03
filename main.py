import json
import uvicorn
import logging
import time
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.routing import APIRoute

from fastmcp import FastMCP, Context
from scalekit import ScalekitClient
from scalekit.common.scalekit import TokenValidationOptions

# --------------------- Logging Setup ---------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("middleware_logger")

# --------------------- MCP + Scalekit Setup ---------------------
mcp = FastMCP("ExpenseTracker",stateless_http=True)

_scalekit_client = ScalekitClient(
    "https://paytm.scalekit.dev",
    "m2m_97422068261325572",
    "test_8c5ODRZ6DCsNzOdVSRSxrVja3ccDGdAAQlgbOybPqfAVzBvhngce3NiUNuEssLAQ",
)

class Settings:
    SCALEKIT_ENVIRONMENT_URL = "https://paytm.scalekit.dev"
    SCALEKIT_AUDIENCE_NAME = "https://forTest.fastmcp.app"
    SCALEKIT_RESOURCE_METADATA_URL = "https://forTest.fastmcp.app/.well-known/oauth-protected-resource"

settings = Settings()

# --------------------- Auth Middleware ---------------------
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.info("=" * 100)
        logger.info(f"[AUTH-MW] Incoming: {request.method} {request.url.path}")

        if ".well-known" in request.url.path :
            return await call_next(request)

        try:
            auth_header = request.headers.get("authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                logger.warning("[AUTH-MW] Missing Authorization header.")
                raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")

            token = auth_header.split("Bearer ")[1].strip()
            logger.info(f"[AUTH-MW] Token prefix: {token[:10]}...")

            validation_opts = TokenValidationOptions(
                issuer=settings.SCALEKIT_ENVIRONMENT_URL,
                audience=[settings.SCALEKIT_AUDIENCE_NAME],
            )
            _scalekit_client.validate_access_token(token, options=validation_opts)
            logger.info("[AUTH-MW] ✅ Token validated OK.")

        except Exception as e:
            logger.exception("[AUTH-MW] Token validation failed.")
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "description": str(e)},
            )

        response = await call_next(request)
        logger.info(f"[AUTH-MW] Completed with status {response.status_code}")
        logger.info("=" * 100)
        return response

app = FastAPI(title="test")

# Middlewares
app.middleware("http")(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["WWW-Authenticate"],
    max_age=86400,
)
# --------------------- MCP Tools ---------------------
@mcp.tool()
async def addNumber(a: int, b: int, ctx: Context = None):
    logger.info(f"[TOOL:addNumber] a={a}, b={b}")
    return a + b + 10

@mcp.tool()
async def tellMeData(ctx: Context = None):
    logger.info("[TOOL:tellMeData] Called.")
    return 10

@mcp.tool()
async def whatISThePSyco(ctx: Context = None):
    logger.info("[TOOL:whatISThePSyco] Called.")
    return 10

@app.get("/.well-known/oauth-protected-resource")
async def oauth_meta():
    logger.info("[PUBLIC] OAuth metadata requested.")
    return {
        "authorization_servers": ["https://paytm.scalekit.dev/resources/res_97420808191740418"],
        "bearer_methods_supported": ["header"],
        "resource": "https://forTest.fastmcp.app",
        "scopes_supported": ["user:read", "user:write"],
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
    }


# Instead of mounting mcp_app, wrap it
mcp_app = mcp.http_app(path="/")
app.mount("/", mcp_app)

# Public metadata



def main():
    """Main entry point for the MCP server."""
    logger.info(f"Server running on http://0.0.0.0:{8080} (MCP at /)")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="debug")

if __name__ == "__main__":
    main()