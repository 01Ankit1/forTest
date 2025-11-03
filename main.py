import json
import uvicorn
import logging
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from fastmcp import FastMCP, Context
from scalekit import ScalekitClient
from scalekit.common.scalekit import TokenValidationOptions

# ---------------------------------------------------------------------------
# LOGGER SETUP
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger("middleware_logger")
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
logger.addHandler(console_handler)
logger.propagate = False

logger.info("[SYSTEM] Logger initialized successfully.")

# ---------------------------------------------------------------------------
# FASTMCP INSTANCE
# ---------------------------------------------------------------------------
mcp = FastMCP("ExpenseTracker")
logger.info("[SYSTEM] FastMCP instance created.")

# ---------------------------------------------------------------------------
# PUBLIC FASTAPI APP (.well-known endpoints)
# ---------------------------------------------------------------------------
public_app = FastAPI()
security = HTTPBearer()
logger.info("[SYSTEM] Public app initialized.")

@public_app.get("/.well-known/oauth-protected-resource/mcp")
async def oauth_protected_resource_metadata():
    """Public metadata endpoint (no auth required)."""
    logger.info("[PUBLIC] Metadata endpoint hit.")
    data = {
        "authorization_servers": [
            "https://paytm.scalekit.dev/resources/res_97420808191740418"
        ],
        "bearer_methods_supported": ["header"],
        "resource": "https://forTest.fastmcp.app/mcp",
        "resource_documentation": "https://forTest.fastmcp.app/mcp/docs",
        "scopes_supported": ["user:read", "user:write"],
    }
    logger.info("[PUBLIC] Returning metadata response.")
    return JSONResponse(content=data)

# ---------------------------------------------------------------------------
# SCALEKIT CLIENT
# ---------------------------------------------------------------------------
_scalekit_client = ScalekitClient(
    "https://paytm.scalekit.dev",
    "m2m_97422068261325572",
    "test_8c5ODRZ6DCsNzOdVSRSxrVja3ccDGdAAQlgbOybPqfAVzBvhngce3NiUNuEssLAQ",
)
logger.info("[SYSTEM] Scalekit client initialized.")

# ---------------------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------------------
class Settings:
    SCALEKIT_ENVIRONMENT_URL = "https://paytm.scalekit.dev"
    SCALEKIT_AUDIENCE_NAME = "https://forTest.fastmcp.app/mcp"
    SCALEKIT_RESOURCE_METADATA_URL = (
        "https://forTest.fastmcp.app/.well-known/oauth-protected-resource/mcp"
    )

settings = Settings()
logger.info("[SYSTEM] Settings configured successfully.")

# ---------------------------------------------------------------------------
# AUTH MIDDLEWARE WITH EXTENSIVE LOGGING
# ---------------------------------------------------------------------------
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        logger.info("=" * 100)
        logger.info(f"[AUTH-MW] --> Entered AuthMiddleware | Method: {request.method} | Path: {request.url.path}")

        # Identify which app is processing
        scope_app = request.scope.get("app")
        logger.info(f"[AUTH-MW] Handling app: {getattr(scope_app, 'title', 'UnknownApp')}")

        # Log request headers
        logger.info(f"[AUTH-MW] Request headers: {dict(request.headers)}")

        # Skip auth for well-known endpoints
        if request.url.path.startswith("/.well-known/"):
            logger.info("[AUTH-MW] Skipping authentication for well-known path.")
            response = await call_next(request)
            logger.info("[AUTH-MW] Exiting middleware (no auth required).")
            logger.info("=" * 100)
            return response

        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                logger.warning("[AUTH-MW] Missing or invalid Authorization header.")
                raise HTTPException(
                    status_code=401, detail="Missing or invalid authorization header"
                )

            token = auth_header.split(" ")[1]
            logger.info(f"[AUTH-MW] Token detected (first 10 chars): {token[:10]}...")

            body_bytes = await request.body()
            body_text = body_bytes.decode("utf-8", errors="ignore") if body_bytes else ""
            logger.info(f"[AUTH-MW] Raw body: {body_text[:300]}")  # truncated for safety

            # Parse JSON body if possible
            try:
                request_data = json.loads(body_text) if body_text else {}
                logger.info(f"[AUTH-MW] Parsed JSON body: {request_data}")
            except Exception as e:
                request_data = {}
                logger.warning(f"[AUTH-MW] Could not parse JSON body: {e}")

            # Token validation setup
            validation_options = TokenValidationOptions(
                issuer=settings.SCALEKIT_ENVIRONMENT_URL,
                audience=[settings.SCALEKIT_AUDIENCE_NAME],
            )

            # Detect if it's a tool call
            is_tool_call = request_data.get("method") == "tools/call"
            if is_tool_call:
                logger.info("[AUTH-MW] Detected a tool call; applying 'search:read' scope requirement.")
                validation_options.required_scopes = ["search:read"]

            # Validate token
            logger.info("[AUTH-MW] Starting token validation...")
            _scalekit_client.validate_token(token, options=validation_options)
            logger.info("[AUTH-MW] ✅ Token validated successfully!")

        except HTTPException as e:
            logger.error(f"[AUTH-MW] ❌ Auth failed: {e.detail}")
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

        except Exception as ex:
            logger.exception(f"[AUTH-MW] ⚠️ Unexpected error: {ex}")
            return JSONResponse(
                status_code=500,
                content={"error": "server_error", "error_description": str(ex)},
            )

        # Process next middleware / route
        response = await call_next(request)

        process_time = (time.time() - start_time) * 1000
        logger.info(f"[AUTH-MW] <-- Exiting AuthMiddleware | Duration: {process_time:.2f} ms | Status: {response.status_code}")
        logger.info("=" * 100)
        return response

# ---------------------------------------------------------------------------
# MCP TOOLS WITH LOGGING
# ---------------------------------------------------------------------------
@mcp.tool()
async def addNumber(a: int, b: int, ctx: Context = None) -> int:
    logger.info(f"[TOOL:addNumber] Called with a={a}, b={b}")
    result = a + b + 10
    logger.info(f"[TOOL:addNumber] Returning result={result}")
    return result

@mcp.tool()
async def tellMeData(ctx: Context = None) -> int:
    logger.info("[TOOL:tellMeData] Called")
    return 10

@mcp.tool()
async def whatISThePSyco(ctx: Context = None) -> int:
    logger.info("[TOOL:whatISThePSyco] Called")
    return 10

# ---------------------------------------------------------------------------
# COMBINED APP CONFIGURATION
# ---------------------------------------------------------------------------
combined = FastAPI(title="ExpenseTracker Combined App")
logger.info("[SYSTEM] Combined app created.")

# Add middleware to combined app
combined.add_middleware(AuthMiddleware)
combined.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # NOTE: restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("[SYSTEM] Middleware attached to combined app.")

# MCP app with its own middleware
mcp_app = mcp.http_app()
mcp_app.add_middleware(AuthMiddleware)
logger.info(f"[DEBUG] MCP app middlewares: {mcp_app.user_middleware}")

# Mount apps
combined.mount("/mcp", mcp_app)
combined.mount("/.well-known", public_app)
logger.info("[SYSTEM] Apps mounted: MCP + Public.")

# ---------------------------------------------------------------------------
# ROOT ENDPOINT
# ---------------------------------------------------------------------------
@combined.get("/")
async def root():
    logger.info("[ROUTE] Root endpoint called.")
    return {
        "status": "ExpenseTracker API is running",
        "docs": "/.well-known/oauth-protected-resource/mcp",
        "message": "Middleware and logging active"
    }

# ---------------------------------------------------------------------------
# STARTUP / SHUTDOWN
# ---------------------------------------------------------------------------
@combined.on_event("startup")
async def startup_event():
    logger.info("[SYSTEM] 🚀 Application startup complete.")
    logger.info(f"[SYSTEM] Combined middlewares: {combined.user_middleware}")

@combined.on_event("shutdown")
async def shutdown_event():
    logger.info("[SYSTEM] 🛑 Application shutdown initiated.")

# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("[SYSTEM] Starting server on port 8002...")
    uvicorn.run(combined, host="0.0.0.0", port=8002, log_level="info")
